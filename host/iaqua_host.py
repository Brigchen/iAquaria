#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
iAqua PC 上位机
- WebSocket 连接固件 ws://<ip>/ws（默认尝试 iaqua.local）
- 实时曲线：水温 / pH / ORP / TDS×2 / 水位（pyqtgraph）
- 数据记录：SQLite（iaqua.db），可导出 CSV
- 远程控制：执行器 手动开/关/自动、投喂、配置批量下发、重启
运行:  python iaqua_host.py [ws://192.168.x.x/ws]
"""
import sys
import os
import json
import time
import sqlite3
import csv
from collections import deque
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QTabWidget, QTableWidget,
    QTableWidgetItem, QGroupBox, QMessageBox, QFileDialog, QHeaderView,
    QStatusBar,
)
from PySide6.QtNetwork import (
    QAbstractSocket, QNetworkAccessManager, QNetworkRequest, QNetworkReply,
    QNetworkProxy,
)
from PySide6.QtWebSockets import QWebSocket

import pyqtgraph as pg

METRICS = [  # key, 中文名, 单位, 颜色
    ("temp", "水温", "℃", "#f59e0b"),
    ("ph", "pH", "", "#2dd4bf"),
    ("orp", "ORP", "mV", "#a78bfa"),
    ("tds1", "TDS(滤前)", "ppm", "#60a5fa"),
    ("tds2", "TDS(滤后)", "ppm", "#34d399"),
    ("lux", "光照", "lx", "#facc15"),
    ("lvl", "水位", "%", "#f472b6"),
]
MAXPTS = 7200  # 1Hz × 2h
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "iaqua.db")

_MISSING = object()  # 配置表新增项（旧值不存在）的哨兵


def parse_tel(msg: dict):
    """tel 帧数据段解析（供自检与主流程共用）"""
    d = msg.get("d", {})
    out = {}
    for k, _, _, _ in METRICS:
        if k in d:
            out[k] = float(d[k])
    out["act"] = d.get("act", [])
    out["man"] = d.get("man", [])
    out["rev"] = d.get("rev", 0)
    out["rssi"] = d.get("rssi", 0)
    out["up"] = d.get("up", 0)
    out["heap"] = d.get("heap", 0)
    return out


class Recorder:
    """SQLite 记录器：10s 批量落盘"""

    COLS = ["ts"] + [m[0] for m in METRICS]

    def __init__(self, path):
        self.buf = []
        self.n_total = 0
        self.keys = [m[0] for m in METRICS]
        new = not os.path.exists(path)
        self.db = sqlite3.connect(path)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS log ("
            "ts REAL PRIMARY KEY, temp REAL, ph REAL, orp REAL,"
            " tds1 REAL, tds2 REAL, lux REAL, lvl REAL)")
        # 旧库迁移：METRICS 新增字段时自动补列（旧数据该列为空）
        cols = {r[1] for r in self.db.execute("PRAGMA table_info(log)")}
        for k in self.keys:
            if k not in cols:
                self.db.execute("ALTER TABLE log ADD COLUMN %s REAL" % k)
                print("数据库迁移：新增 %s 列" % k)
        # 清理已废弃字段（485 模组温度、TDS 模组温度均无对外数据源）
        for legacy in ("tt1", "tt2", "mtemp"):
            if legacy in cols:
                self.db.execute("ALTER TABLE log DROP COLUMN %s" % legacy)
                print("数据库迁移：删除废弃 %s 列" % legacy)
        self.db.commit()
        if new:
            print("新建数据库", path)

    def add(self, sample):
        # 时间戳由记录器统一打（tel 帧本身无 ts 字段）
        self.buf.append([time.time()] + [sample.get(k) for k in self.keys])
        self.n_total += 1

    def flush(self):
        if not self.buf:
            return
        self.db.executemany(
            "INSERT OR REPLACE INTO log (%s) VALUES (%s)"
            % (",".join(self.COLS), ",".join("?" * len(self.COLS))), self.buf)
        self.db.commit()
        self.buf.clear()

    def count(self):
        return self.db.execute("SELECT COUNT(*) FROM log").fetchone()[0]

    def export_csv(self, path):
        self.flush()
        cur = self.db.execute(
            "SELECT %s FROM log ORDER BY ts" % ",".join(self.COLS))
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["time"] + [m[1] for m in METRICS])
            for row in cur:
                w.writerow([datetime.fromtimestamp(row[0]).strftime(
                    "%Y-%m-%d %H:%M:%S")] + list(row[1:]))


class MainWindow(QMainWindow):
    def __init__(self, url):
        super().__init__()
        self.setWindowTitle("iAqua 上位机")
        self.resize(1100, 760)
        # 统一应用 logo（与 App 各端同源，相对本文件定位保证换机可用）
        logo = Path(__file__).resolve().parent / "logo.png"
        if logo.exists():
            self.setWindowIcon(QIcon(str(logo)))

        # ---- 数据结构 ----
        self.t = {k: deque(maxlen=MAXPTS) for k, _, _, _ in METRICS}
        self.y = {k: deque(maxlen=MAXPTS) for k, _, _, _ in METRICS}
        self.act, self.man = [False] * 5, [False] * 5
        self.rev = 0
        self.cfg = {}
        self.rec = Recorder(DB_PATH)

        # ---- 摄像头快照轮询 ----
        self.cam_base = ""
        self.cam_on = False
        self.cam_busy = False
        self.nam = QNetworkAccessManager(self)
        # 局域网直连：禁用系统代理（系统代理会导致 "Proxy type is invalid"）
        self.nam.setProxy(QNetworkProxy(QNetworkProxy.ProxyType.NoProxy))
        self.nam.finished.connect(self._cam_done)

        # ---- WebSocket ----
        self.ws = QWebSocket()
        self.ws.setProxy(QNetworkProxy(QNetworkProxy.ProxyType.NoProxy))
        self.ws.connected.connect(self.on_connected)
        self.ws.disconnected.connect(self.on_disconnected)
        self.ws.textMessageReceived.connect(self.on_msg)
        self.ws.errorOccurred.connect(self.on_error)
        self.url = url

        # ---- UI ----
        self._build_ui()

        # ---- 定时器 ----
        self.plot_timer = QTimer(self)  # 曲线刷新
        self.plot_timer.timeout.connect(self.update_plots)
        self.plot_timer.start(1000)
        self.flush_timer = QTimer(self)  # 落盘
        self.flush_timer.timeout.connect(self._flush)
        self.flush_timer.start(10000)
        self.recon_timer = QTimer(self)  # 断线重连
        self.recon_timer.timeout.connect(self._reconnect)
        self.recon_timer.setInterval(3000)
        self.cam_timer = QTimer(self)  # 摄像头快照轮询
        self.cam_timer.timeout.connect(self._cam_fetch)
        self.cam_timer.start(1000)

        self._connect()

    # ================= UI 构建 =================
    def _build_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)

        # 连接栏
        bar = QHBoxLayout()
        bar.addWidget(QLabel("设备地址"))
        self.edUrl = QLineEdit(self.url)
        self.edUrl.setMinimumWidth(260)
        bar.addWidget(self.edUrl)
        self.btnConn = QPushButton("连接")
        self.btnConn.clicked.connect(self.toggle_conn)
        bar.addWidget(self.btnConn)
        self.cbRec = QComboBox()
        self.cbRec.addItems(["记录: 开", "记录: 关"])
        bar.addWidget(self.cbRec)
        self.btnCsv = QPushButton("导出 CSV")
        self.btnCsv.clicked.connect(self.export_csv)
        bar.addWidget(self.btnCsv)
        bar.addStretch(1)
        root.addLayout(bar)

        tabs = QTabWidget()
        root.addWidget(tabs, 1)

        # ---- Tab1 实时曲线 ----
        pg.setConfigOptions(antialias=False, background="#10161d",
                            foreground="#7d8b9c")
        self.plots = {}
        pw = pg.GraphicsLayoutWidget()
        tabs.addTab(pw, "实时曲线")
        prior = None
        last = len(METRICS) - 1
        for i, (k, name, unit, color) in enumerate(METRICS):
            # 每个图都挂时间轴（x 为 Unix 秒）；仅最后一行显示刻度数字，避免重复
            ax = pg.DateAxisItem(orientation="bottom")
            p = pw.addPlot(row=i, col=0, axisItems={"bottom": ax})
            p.setLabel("left", f"{name} {unit}")
            p.showGrid(x=True, y=True, alpha=0.25)
            p.setMouseEnabled(x=False, y=False)
            p.hideButtons()
            if i != last:
                p.getAxis("bottom").setStyle(showValues=False)
            if prior:
                p.setXLink(prior)
            prior = p
            c = p.plot(pen=pg.mkPen(color, width=2))
            self.plots[k] = (p, c)

        # ---- Tab2 视频快照 ----
        tabCam = QWidget()
        vlay = QVBoxLayout(tabCam)
        cbar = QHBoxLayout()
        self.lbCamUrl = QLabel("未配置（配置表 cam.url 填摄像头基地址）")
        self.btnCam = QPushButton("停止")
        self.btnCam.setEnabled(False)
        self.btnCam.clicked.connect(self._toggle_cam)
        cbar.addWidget(self.lbCamUrl, 1)
        cbar.addWidget(self.btnCam)
        vlay.addLayout(cbar)
        self.lbCam = QLabel("未配置摄像头")
        self.lbCam.setMinimumSize(560, 360)
        self.lbCam.setAlignment(Qt.AlignCenter)
        self.lbCam.setStyleSheet(
            "background:#0a0f14;color:#7d8b9c;border-radius:8px;")
        vlay.addWidget(self.lbCam, 1)
        tabs.addTab(tabCam, "视频")

        # ---- Tab3 控制与配置 ----
        tab2 = QWidget()
        lay = QHBoxLayout(tab2)
        tabs.addTab(tab2, "控制与配置")

        left = QVBoxLayout()
        gbAct = QGroupBox("执行器控制")
        ga = QGridLayout(gbAct)
        self.actBtns = {}
        for r, (idx, name) in enumerate([(0, "CO2 电磁阀"), (2, "水族灯"),
                                         (3, "加热棒"), (4, "补水泵")]):
            lb = QLabel(name)
            st = QLabel("—")
            st.setMinimumWidth(70)
            bOn = QPushButton("开")
            bOff = QPushButton("关")
            bAuto = QPushButton("自动")
            bOn.clicked.connect(lambda _, i=idx: self.send({"cmd": "ctrl", "ch": self._chname(i), "on": True}))
            bOff.clicked.connect(lambda _, i=idx: self.send({"cmd": "ctrl", "ch": self._chname(i), "on": False}))
            bAuto.clicked.connect(lambda _, i=idx: self.send({"cmd": "ctrl", "ch": self._chname(i), "mode": "auto"}))
            ga.addWidget(lb, r, 0)
            ga.addWidget(st, r, 1)
            ga.addWidget(bOn, r, 2)
            ga.addWidget(bOff, r, 3)
            ga.addWidget(bAuto, r, 4)
            self.actBtns[idx] = st
        bFeed = QPushButton("投喂一次")
        bFeed.clicked.connect(lambda: self.send({"cmd": "feed"}))
        ga.addWidget(bFeed, 5, 0, 1, 2)
        bReboot = QPushButton("重启设备")
        bReboot.clicked.connect(self._reboot)
        ga.addWidget(bReboot, 5, 3, 1, 2)
        left.addWidget(gbAct)

        gbWifi = QGroupBox("WiFi（保存后设备重启生效）")
        gw = QGridLayout(gbWifi)
        self.edSsid = QLineEdit()
        self.edPass = QLineEdit()
        self.edPass.setEchoMode(QLineEdit.Password)
        gw.addWidget(QLabel("SSID"), 0, 0)
        gw.addWidget(self.edSsid, 0, 1)
        gw.addWidget(QLabel("密码"), 1, 0)
        gw.addWidget(self.edPass, 1, 1)
        bWifi = QPushButton("保存")
        bWifi.clicked.connect(self._save_wifi)
        gw.addWidget(bWifi, 2, 1)
        left.addWidget(gbWifi)
        left.addStretch(1)

        right = QVBoxLayout()
        right.addWidget(QLabel("配置表（双击修改，点「应用修改」批量下发；"
                               "含 RS485 寄存器映射 regs.*）"))
        self.tbl = QTableWidget(0, 2)
        self.tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tbl.setHorizontalHeaderLabels(["路径", "值"])
        right.addWidget(self.tbl, 1)
        hb = QHBoxLayout()
        bApply = QPushButton("应用修改")
        bApply.clicked.connect(self._apply_cfg)
        bReload = QPushButton("重新读取")
        bReload.clicked.connect(lambda: self.send({"cmd": "cfg"}))
        bAdd = QPushButton("＋ 新增项")
        bAdd.setToolTip("新增配置表中没有的路径，如 regs.tds.map.tt1.scale")
        bAdd.clicked.connect(self._add_cfg_row)
        hb.addWidget(bApply)
        hb.addWidget(bReload)
        hb.addWidget(bAdd)
        right.addLayout(hb)
        lay.addLayout(left, 4)
        lay.addLayout(right, 6)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("未连接")
        self.setCentralWidget(central)

    @staticmethod
    def _chname(i):
        return ["co2", "feed", "light", "heater", "pump"][i]

    # ================= 连接 =================
    def _connect(self):
        url = self.edUrl.text().strip()
        if url and not url.startswith("ws"):
            url = "ws://" + url + ("/ws" if not url.endswith("/ws") else "")
            self.edUrl.setText(url)
        self.statusBar().showMessage("连接中 " + url)
        self.ws.open(QUrl(url))

    def toggle_conn(self):
        if self.ws.state() == QAbstractSocket.ConnectedState:
            self.ws.close()
        else:
            self._connect()

    def _reconnect(self):
        if self.ws.state() == QAbstractSocket.UnconnectedState:
            self._connect()

    def on_connected(self):
        self.recon_timer.stop()
        self.statusBar().showMessage("已连接 " + self.edUrl.text())
        self.btnConn.setText("断开")
        self.send({"cmd": "cfg"})

    def on_disconnected(self):
        self.btnConn.setText("连接")
        self.statusBar().showMessage("已断开，3s 后自动重连")
        self.recon_timer.start()

    def on_error(self, err):
        # 连接失败/通信错误：显示具体原因（DNS 解析失败、连接被拒、超时等）
        if err == QAbstractSocket.SocketError.HostNotFoundError:
            msg = ("找不到主机 " + self.edUrl.text() +
                   "（.local 域名需 Bonjour 支持；建议改用设备 IP，"
                   "如 ws://192.168.x.x/ws 或 ws://192.168.4.1/ws）")
        else:
            msg = self.ws.errorString() or str(err)
        self.statusBar().showMessage("连接失败: " + msg, 10000)

    # ================= 消息 =================
    def send(self, obj):
        if self.ws.state() == QAbstractSocket.ConnectedState:
            self.ws.sendTextMessage(json.dumps(obj))

    def on_msg(self, text):
        try:
            m = json.loads(text)
        except json.JSONDecodeError:
            return
        ev = m.get("ev")
        if ev == "tel":
            self._on_tel(m)
        elif ev == "cfg":
            self.cfg = m.get("cfg", {})
            self.rev = self.cfg.get("rev", 0)
            self._fill_table()
            self.edSsid.setText(self.cfg.get("wifi", {}).get("ssid", ""))
            self._on_cfg_cam()
        elif ev == "ack":
            ok = m.get("ok")
            msg = m.get("msg", "")
            self.statusBar().showMessage(("成功: " if ok else "失败: ") + msg, 8000)
            if ok and "WiFi" in msg:
                QMessageBox.information(self, "iAqua", "WiFi 已保存，设备将重启")

    def _on_tel(self, m):
        s = parse_tel(m)
        now = time.time()
        for k, _, _, _ in METRICS:
            if k in s:
                self.t[k].append(now)
                self.y[k].append(s[k])
        if "act" in s:
            self.act = s["act"]
            self._render_act()
        self.rev = s.get("rev", self.rev)
        if self.cbRec.currentIndex() == 0:  # 记录开关
            self.rec.add(s)
        vals = "  ".join(f"{n}={s.get(k, '--')}" for k, n, _, _ in METRICS[:3])
        self.statusBar().showMessage(f"已连接 · {vals}")

    # ================= 曲线 =================
    def update_plots(self):
        for k, (_, curve) in self.plots.items():
            curve.setData(list(self.t[k]), list(self.y[k]))

    # ================= 摄像头 =================
    def _on_cfg_cam(self):
        base = (self.cfg.get("cam") or {}).get("url") or ""
        base = base.strip().rstrip("/")
        if base == self.cam_base:
            return
        self.cam_base = base
        if base:
            self.lbCamUrl.setText("摄像头: " + base)
            self.lbCam.setText("连接摄像头…")
            self.btnCam.setEnabled(True)
            if not self.cam_on:
                self.cam_on = True
                self.btnCam.setText("停止")
        else:
            self.lbCamUrl.setText("未配置（配置表 cam.url 填摄像头基地址）")
            self.lbCam.setText("未配置摄像头")
            self.cam_on = False
            self.btnCam.setEnabled(False)
            self.btnCam.setText("停止")

    def _toggle_cam(self):
        self.cam_on = not self.cam_on
        self.btnCam.setText("停止" if self.cam_on else "开始")

    def _cam_fetch(self):
        if not (self.cam_on and self.cam_base and not self.cam_busy):
            return
        self.cam_busy = True
        self.nam.get(QNetworkRequest(QUrl(self.cam_base + "/capture")))

    def _cam_done(self, reply):
        reply.deleteLater()
        self.cam_busy = False
        if not self.cam_on:
            return
        if reply.error() != QNetworkReply.NoError:
            self.lbCam.setText("摄像头离线（%s）" % reply.errorString())
            return
        pm = QPixmap()
        if pm.loadFromData(reply.readAll()):
            self.lbCam.setPixmap(pm.scaled(
                self.lbCam.size(), Qt.KeepAspectRatio,
                Qt.SmoothTransformation))

    # ================= 控制与配置 =================
    def _render_act(self):
        names = ["CO2 电磁阀", "喂食器", "水族灯", "加热棒", "补水泵"]
        for idx, st in self.actBtns.items():
            a, m = self.act[idx], self.man[idx]
            st.setText(("自动·" if not m else "手动·") + ("开" if a else "关"))

    def _flatten(self, d, prefix=""):
        rows = []
        for k, v in d.items():
            p = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                rows += self._flatten(v, p)
            else:
                rows.append((p, v))
        return rows

    def _fill_table(self):
        self.tbl.setRowCount(0)
        for p, v in self._flatten(self.cfg):
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            i0 = QTableWidgetItem(p)
            i0.setFlags(i0.flags() & ~Qt.ItemIsEditable)
            self.tbl.setItem(r, 0, i0)
            self.tbl.setItem(r, 1, QTableWidgetItem(json.dumps(v) if isinstance(v, bool) else str(v)))

    def _add_cfg_row(self):
        """追加一行可编辑的空白配置项（用于配置表里尚未存在的路径）。"""
        r = self.tbl.rowCount()
        self.tbl.insertRow(r)
        self.tbl.setItem(r, 0, QTableWidgetItem(""))
        self.tbl.setItem(r, 1, QTableWidgetItem(""))
        self.tbl.editItem(self.tbl.item(r, 0))

    @staticmethod
    def _parse_cfg_value(raw, old):
        """按旧值类型解析；新增项（old 为 _MISSING）尝试 JSON（数字/bool），否则按字符串。"""
        txt = raw.strip()
        if old is not _MISSING:
            if isinstance(old, bool):
                return {"true": True, "false": False}.get(txt.lower(), old)
            if isinstance(old, (int, float)):
                return float(txt) if ("." in txt or "e" in txt.lower()) else int(txt)
            return txt
        # 新增路径：优先按 JSON 解析（0.1 / 2 / true / {...}），失败则字符串
        try:
            return json.loads(txt)
        except (ValueError, json.JSONDecodeError):
            return txt

    def _apply_cfg(self):
        sets = []
        for r in range(self.tbl.rowCount()):
            p = self.tbl.item(r, 0).text().strip()
            if not p:
                continue
            raw = self.tbl.item(r, 1).text()
            # 沿路径在当前 cfg 中找旧值；找不到说明是新增项
            old, cur, found = _MISSING, self.cfg, True
            for k in p.split("."):
                if isinstance(cur, dict) and k in cur:
                    cur = cur[k]
                else:
                    found = False
                    break
            if found:
                old = cur
            try:
                v = self._parse_cfg_value(raw, old)
            except ValueError:
                continue
            if not found or v != old:
                sets.append({"path": p, "value": v})
        if not sets:
            self.statusBar().showMessage("没有修改", 4000)
            return
        self.send({"cmd": "cfg.setMany", "sets": sets, "rev": self.rev})
        self.statusBar().showMessage(f"下发 {len(sets)} 项修改…", 8000)

    def _save_wifi(self):
        ssid = self.edSsid.text().strip()
        if not ssid:
            QMessageBox.warning(self, "iAqua", "SSID 不能为空")
            return
        self.send({"cmd": "wifi", "ssid": ssid, "pass": self.edPass.value() if hasattr(self.edPass, "value") else self.edPass.text()})

    def _reboot(self):
        if QMessageBox.question(self, "iAqua", "确认重启设备?") == QMessageBox.Yes:
            self.send({"cmd": "reboot"})

    # ================= 记录 =================
    def _flush(self):
        self.rec.flush()

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "导出 CSV", os.path.join(os.path.dirname(DB_PATH), "iaqua_export.csv"),
            "CSV (*.csv)")
        if not path:
            return
        try:
            self.rec.export_csv(path)
            self.statusBar().showMessage("已导出 " + path, 10000)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "导出失败", str(e))

    def closeEvent(self, e):
        self.rec.flush()
        self.ws.close()
        super().closeEvent(e)


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else "ws://iaqua.local/ws"
    app = QApplication(sys.argv)
    w = MainWindow(url)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
