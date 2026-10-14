# -*- coding: utf-8 -*-
"""Generate iAqua competition design reports (full ≥50p + compact ≤15p).
Anonymized per 智能水族设计赛道 attachment-1 rules.
"""
from __future__ import annotations

import math
import os
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib
from matplotlib import font_manager

def _load_cjk_font():
    for p in (
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\msyhbd.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
    ):
        if os.path.exists(p):
            font_manager.fontManager.addfont(p)
            prop = font_manager.FontProperties(fname=p)
            matplotlib.rcParams["font.family"] = prop.get_name()
            matplotlib.rcParams["font.sans-serif"] = [prop.get_name()]
            matplotlib.rcParams["axes.unicode_minus"] = False
            return prop
    matplotlib.rcParams["axes.unicode_minus"] = False
    return font_manager.FontProperties()


FP = _load_cjk_font()

import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn, nsmap
from docx.oxml import OxmlElement
from docx.shared import Cm, Pt, RGBColor, Inches, Twips

ROOT = Path(__file__).resolve().parent
ASSET = ROOT / "report_assets"
OUT_FULL = ROOT / "参赛队伍-智能水族设计赛道-设计方案报告-详版.docx"
OUT_COMPACT = ROOT / "参赛队伍-智能水族设计赛道-一队.docx"
GITHUB = "https://github.com/Brigchen/iAquaria"

# Figure counter helpers
FIG = {"n": 0}
TAB = {"n": 0}


def set_run_font(run, name_cn="宋体", name_en="Times New Roman", size=12, bold=False):
    run.bold = bold
    run.font.size = Pt(size)
    run.font.name = name_en
    r = run._element
    rPr = r.get_or_add_rPr()
    rFonts = rPr.get_or_add_rFonts()
    rFonts.set(qn("w:ascii"), name_en)
    rFonts.set(qn("w:hAnsi"), name_en)
    rFonts.set(qn("w:eastAsia"), name_cn)


def set_paragraph_format(p, line=1.5, space_before=0, space_after=0, first_line=True):
    pf = p.paragraph_format
    pf.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    pf.space_before = Pt(space_before)
    pf.space_after = Pt(space_after)
    if first_line:
        pf.first_line_indent = Cm(0.74)  # ~2 chars 小四


def add_page_number(section):
    footer = section.footer
    footer.is_linked_to_previous = False
    p = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    # PAGE field
    run = p.add_run()
    fldChar1 = OxmlElement("w:fldChar")
    fldChar1.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    fldChar2 = OxmlElement("w:fldChar")
    fldChar2.set(qn("w:fldCharType"), "end")
    run._r.append(fldChar1)
    run._r.append(instr)
    run._r.append(fldChar2)
    set_run_font(run, size=10.5)


def setup_doc():
    doc = Document()
    for s in doc.sections:
        s.page_width = Cm(21.0)
        s.page_height = Cm(29.7)
        s.top_margin = Cm(2.54)
        s.bottom_margin = Cm(2.54)
        s.left_margin = Cm(3.18)
        s.right_margin = Cm(3.18)
        add_page_number(s)
    # Normal style
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(12)
    style._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    return doc


def add_title(doc, text, level=1):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6 if level == 1 else 3)
    p.paragraph_format.space_after = Pt(6 if level == 1 else 3)
    p.paragraph_format.first_line_indent = Cm(0)
    if level == 1:
        run = p.add_run(text)
        set_run_font(run, name_cn="黑体", size=14, bold=True)
    elif level == 2:
        run = p.add_run(text)
        set_run_font(run, name_cn="黑体", size=12, bold=True)
    else:
        run = p.add_run(text)
        set_run_font(run, name_cn="黑体", size=12, bold=True)
    return p


def add_body(doc, text, first_line=True):
    p = doc.add_paragraph()
    set_paragraph_format(p, first_line=first_line)
    run = p.add_run(text)
    set_run_font(run, size=12)
    return p


def add_bullets(doc, items):
    for it in items:
        p = doc.add_paragraph()
        p.paragraph_format.first_line_indent = Cm(0)
        p.paragraph_format.left_indent = Cm(0.74)
        p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
        run = p.add_run("• " + it)
        set_run_font(run, size=12)


def add_caption(doc, kind, chapter, title):
    if kind == "fig":
        FIG["n"] += 1
        label = f"图{chapter}-{FIG['n']}  {title}"
    else:
        TAB["n"] += 1
        label = f"表{chapter}-{TAB['n']}  {title}"
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Cm(0)
    p.paragraph_format.space_before = Pt(3)
    p.paragraph_format.space_after = Pt(6)
    run = p.add_run(label)
    set_run_font(run, size=10.5)
    return label


def add_table(doc, headers, rows, chapter, title):
    add_caption(doc, "tab", chapter, title)
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = ""
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(h)
        set_run_font(run, name_cn="黑体", size=10.5, bold=True)
    for r_i, row in enumerate(rows):
        for c_i, val in enumerate(row):
            cell = table.rows[r_i + 1].cells[c_i]
            cell.text = ""
            p = cell.paragraphs[0]
            run = p.add_run(str(val))
            set_run_font(run, size=10.5)
    doc.add_paragraph()


def add_slot(doc, title):
    """预留插图位，便于后续粘贴实物照片或界面截图。"""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Cm(0)
    run = p.add_run(title)
    set_run_font(run, name_cn="黑体", size=10.5, bold=True)
    table = doc.add_table(rows=1, cols=1)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = table.cell(0, 0)
    cell.text = ""
    cp = cell.paragraphs[0]
    cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cr = cp.add_run("【预留插图位置】\n在此插入照片或界面截图（建议宽度不超过版心）")
    set_run_font(cr, size=12)
    tr = table.rows[0]._tr
    trPr = tr.get_or_add_trPr()
    trHeight = OxmlElement("w:trHeight")
    trHeight.set(qn("w:val"), "2400")
    trHeight.set(qn("w:hRule"), "atLeast")
    trPr.append(trHeight)
    doc.add_paragraph()


def add_picture(doc, path, chapter, title, width_cm=14.0):
    add_caption(doc, "fig", chapter, title)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Cm(0)
    run = p.add_run()
    run.add_picture(str(path), width=Cm(width_cm))


def page_break(doc):
    doc.add_page_break()


# -------------------- figures --------------------
def save_fig(name):
    ASSET.mkdir(parents=True, exist_ok=True)
    path = ASSET / name
    plt.tight_layout()
    try:
        plt.savefig(path, dpi=160, bbox_inches="tight", facecolor="white")
    except OSError:
        path = ASSET / (Path(name).stem + "_n.png")
        plt.savefig(path, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close()
    return path


def fig_system_architecture():
    fig, ax = plt.subplots(figsize=(7.2, 9.6))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 13.2)
    ax.axis("off")
    ax.set_title("总体方案：硬件、软件与云端", fontproperties=FP, fontsize=15, pad=4)

    zones = [
        (0.15, "#FFF8E1", "#E65100", "硬件  缸边"),
        (3.42, "#E3F2FD", "#1565C0", "软件  App 与电脑"),
        (6.69, "#E8F5E9", "#2E7D32", "云端  传递"),
    ]
    for x, face, _col, _title in zones:
        ax.add_patch(FancyBboxPatch((x, 1.55), 3.15, 10.35, boxstyle="round,pad=0.02",
                                    facecolor=face, edgecolor="#37474F", lw=1.15))
        ax.text(x + 1.57, 11.45, _title, ha="center", fontproperties=FP, fontsize=12, color=_col)

    def item(x, y, title, body):
        ax.add_patch(FancyBboxPatch((x, y), 2.85, 1.55, boxstyle="round,pad=0.02",
                                    facecolor="white", edgecolor="#546E7A", lw=0.9))
        ax.text(x + 1.42, y + 1.05, title, ha="center", fontproperties=FP, fontsize=10, color="#1A237E")
        ax.text(x + 1.42, y + 0.48, body, ha="center", va="center", fontproperties=FP, fontsize=8)

    item(0.3, 9.45, "测量", "水温、pH、TDS\n水位、光照")
    item(0.3, 7.35, "判断", "每秒一次\n读数超时则停自动")
    item(0.3, 5.25, "动作", "灯、加热、补水\n喂食、二氧化碳")
    item(0.3, 3.15, "拍照", "摄像头独立供电\n不参与开关判断")
    for y in (9.0, 6.9, 4.8):
        ax.text(1.72, y, "↓", ha="center", fontproperties=FP, fontsize=13, color="#E65100")

    item(3.57, 9.45, "查看与操作", "概览、日志、计划、鱼缸\n网页与电脑曲线")
    item(3.57, 7.35, "养护", "换水喂食可回看\n异常提醒、周期任务")
    item(3.57, 5.25, "读法", "淡水看 TDS\n海水看盐度")
    item(3.57, 3.15, "建议", "识图与水质说明\n不直接带动设备")
    for y in (9.0, 6.9, 4.8):
        ax.text(5.0, y, "↓", ha="center", fontproperties=FP, fontsize=13, color="#1565C0")

    item(6.84, 9.45, "接入", "加密连接\n按设备分开")
    item(6.84, 7.35, "保留", "最近一次水质状态\n最近一张照片")
    item(6.84, 5.25, "转发", "只接受控制与投喂\n其余命令丢弃")
    item(6.84, 3.15, "边界", "云中断不影响缸边\n已启用的自动策略")
    for y in (9.0, 6.9, 4.8):
        ax.text(8.26, y, "↓", ha="center", fontproperties=FP, fontsize=13, color="#2E7D32")

    ax.annotate("", xy=(3.42, 8.1), xytext=(3.15, 8.1),
                arrowprops=dict(arrowstyle="<->", color="#37474F", lw=1.3))
    ax.annotate("", xy=(6.69, 8.1), xytext=(6.42, 8.1),
                arrowprops=dict(arrowstyle="<->", color="#37474F", lw=1.3))
    ax.text(0.2, 0.85, "现场：应用软件直接连接硬件，约每秒刷新。离场：经云端获取最近状态，并下发允许的命令。",
            fontproperties=FP, fontsize=9)
    ax.text(0.2, 0.35, "执行决策由现场主控完成。云端负责传递，不代替主控决定加热或开启气阀。",
            fontproperties=FP, fontsize=9)
    return save_fig("fig_arch.png")


def fig_control_loop():
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.axis("off")
    ax.set_xlim(0, 9)
    ax.set_ylim(0, 4)
    steps = [
        (0.3, 1.5, "传感采集\n1–5 s"),
        (2.4, 1.5, "测值有效性\nvalidity gate"),
        (4.5, 1.5, "控制策略\npH/温/水位"),
        (6.6, 1.5, "执行器输出\n手动优先"),
    ]
    for x, y, t in steps:
        ax.add_patch(FancyBboxPatch((x, y), 1.8, 1.2, boxstyle="round,pad=0.04",
                                    facecolor="#E0F2F1", edgecolor="#00695C"))
        ax.text(x + 0.9, y + 0.6, t, ha="center", va="center", fontproperties=FP, fontsize=10)
    for i in range(3):
        ax.annotate("", xy=(steps[i + 1][0], 2.1), xytext=(steps[i][0] + 1.8, 2.1),
                    arrowprops=dict(arrowstyle="->", color="#004D40", lw=1.4))
    ax.annotate("", xy=(1.2, 1.5), xytext=(7.5, 1.2),
                arrowprops=dict(arrowstyle="->", color="#BF360C",
                                connectionstyle="arc3,rad=-0.35", lw=1.2))
    ax.text(4.5, 0.5, "遥测发布 / 告警事件 / 云端同步", ha="center", fontsize=10, color="#BF360C")
    ax.set_title("闭环控制与安全优先逻辑", fontsize=13)
    return save_fig("fig_control.png")


def fig_mqtt_topics():
    fig, ax = plt.subplots(figsize=(11.2, 6.8))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8.2)
    ax.axis("off")
    ax.set_title("MQTT 主题约定与报文方向", fontproperties=FP, fontsize=14, pad=6)

    # 上行三条，画在节点上方
    uplinks = [
        (7.15, "#1565C0", "tel  遥测", "水温、pH、TDS、水位、光照、执行器状态；约 30 秒一帧并保留"),
        (6.35, "#2E7D32", "evt  事件", "灯、加热、补水、喂食、二氧化碳阀翻转时立即上报"),
        (5.55, "#6A1B9A", "img  照片", "摄像头抓拍，离开局域网后仍可查看最近一张"),
    ]
    for y, col, name, desc in uplinks:
        ax.annotate("", xy=(8.5, y), xytext=(3.4, y),
                    arrowprops=dict(arrowstyle="->", color=col, lw=1.8))
        ax.text(0.3, y + 0.12, name, fontproperties=FP, fontsize=10, color=col, va="bottom")
        ax.text(3.5, y + 0.12, desc, fontproperties=FP, fontsize=8, color="#424242", va="bottom")

    nodes = [
        (0.4, 2.15, "#E3F2FD", "边缘设备", "主板发布 tel / evt\n摄像头发布 img"),
        (4.5, 2.15, "#E8F5E9", "云 Broker", "TLS 8883\n按设备 ID 分主题\n保留最近一帧"),
        (8.6, 2.15, "#FFF3E0", "手机 App", "订阅遥测与照片\n下发控制与投喂"),
    ]
    for x, y, c, title, body in nodes:
        ax.add_patch(FancyBboxPatch((x, y), 3.0, 2.15, boxstyle="round,pad=0.03",
                                    facecolor=c, edgecolor="#37474F", lw=1.2))
        ax.text(x + 1.5, y + 1.65, title, ha="center", fontproperties=FP, fontsize=12)
        ax.text(x + 1.5, y + 0.75, body, ha="center", va="center", fontproperties=FP, fontsize=9)

    ax.annotate("", xy=(3.5, 1.35), xytext=(8.5, 1.35),
                arrowprops=dict(arrowstyle="->", color="#C62828", lw=1.8))
    ax.text(0.3, 1.5, "cmd  下行", fontproperties=FP, fontsize=10, color="#C62828")
    ax.text(3.6, 0.85, "仅放行 ctrl 与 feed。大模型建议不直接驱动电磁阀或加热棒。",
            fontproperties=FP, fontsize=9)
    ax.text(0.3, 0.25, "主题前缀 iaquaria/{设备ID}/ 。设备 ID 必须与 App 云查看 ID 一致。",
            fontproperties=FP, fontsize=9, color="#37474F")
    return save_fig("fig_mqtt.png")


def fig_metrics_demo():
    rng = np.random.default_rng(7)
    t = np.arange(0, 120)
    temp = 26.2 + 0.4 * np.sin(t / 18) + rng.normal(0, 0.05, len(t))
    ph = 6.95 + 0.08 * np.sin(t / 25 + 1) + rng.normal(0, 0.01, len(t))
    tds = 210 + 8 * np.sin(t / 30) + rng.normal(0, 1.5, len(t))
    fig, axes = plt.subplots(3, 1, figsize=(9, 6), sharex=True)
    axes[0].plot(t, temp, color="#F59E0B")
    axes[0].set_ylabel("水温 ℃")
    axes[0].grid(True, alpha=0.3)
    axes[1].plot(t, ph, color="#2DD4BF")
    axes[1].axhline(7.0, color="#EF4444", ls="--", lw=1, label="CO₂ 开阀阈值")
    axes[1].axhline(6.8, color="#3B82F6", ls="--", lw=1, label="CO₂ 关阀阈值")
    axes[1].legend(loc="upper right", fontsize=8)
    axes[1].set_ylabel("pH")
    axes[1].grid(True, alpha=0.3)
    axes[2].plot(t, tds, color="#60A5FA")
    axes[2].set_ylabel("TDS ppm")
    axes[2].set_xlabel("时间 / min")
    axes[2].grid(True, alpha=0.3)
    fig.suptitle("典型运行遥测曲线（示意）", fontsize=13)
    return save_fig("fig_metrics.png")


def fig_pin_map():
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.axis("off")
    data = [
        ["功能", "GPIO", "说明"],
        ["RS485 TX/RX/DE", "17/16/4", "Modbus RTU 主站"],
        ["DS18B20", "13", "4.7k 上拉"],
        ["HC-SR04", "25/26", "ECHO 分压"],
        ["I2C SDA/SCL", "21/22", "BH1750"],
        ["CO₂ MOS", "33", "高电平有效"],
        ["继电器×4", "27/14/32/5", "低电平触发"],
        ["TF SPI", "18/19/34/23", "SCK/MOSI/MISO/CS"],
    ]
    table = ax.table(cellText=data, loc="center", cellLoc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.2, 1.6)
    for cell in table.get_celld().values():
        cell.get_text().set_fontproperties(FP)
    for j in range(3):
        table[0, j].set_facecolor("#2DD4BF")
        table[0, j].set_text_props(color="white", weight="bold")
    ax.set_title("主控关键引脚规划一览", fontsize=13, pad=16)
    return save_fig("fig_pins.png")


def fig_app_ia():
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.axis("off")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4)
    tabs = ["概览", "日志", "计划", "鱼缸"]
    for i, t in enumerate(tabs):
        ax.add_patch(FancyBboxPatch((0.5 + i * 2.3, 0.4), 2.0, 0.7,
                                    boxstyle="round,pad=0.03",
                                    facecolor="#CCFBF1", edgecolor="#0F766E"))
        ax.text(1.5 + i * 2.3, 0.75, t, ha="center", va="center", fontsize=11)
    ax.add_patch(FancyBboxPatch((0.5, 1.5), 9.0, 2.0,
                                boxstyle="round,pad=0.05",
                                facecolor="#F0FDFA", edgecolor="#0F766E"))
    ax.text(5, 3.1, "多缸切换 · 实时指标卡 · 告警横幅 · AI 对话入口", ha="center", fontsize=11)
    ax.text(5, 2.4, "水型驱动显示：淡水/草缸 TDS×2；海水缸显示盐度", ha="center", fontsize=10)
    ax.text(5, 1.85, "主题色 #2dd4bf，与 Web 控制台视觉体系统一", ha="center", fontsize=10)
    ax.set_title("移动端信息架构（四 Tab）", fontsize=13)
    return save_fig("fig_app_ia.png")


def fig_safety():
    labels = ["测值有效", "手动优先", "超时切断", "上电安全", "看门狗"]
    vals = [95, 100, 98, 100, 100]
    fig, ax = plt.subplots(figsize=(8, 4))
    bars = ax.bar(labels, vals, color=["#2DD4BF", "#34D399", "#60A5FA", "#A78BFA", "#F472B6"])
    ax.set_ylim(0, 110)
    ax.set_ylabel("设计覆盖度 / %")
    ax.set_title("安全机制设计覆盖评估（自评）")
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 2, f"{v}%", ha="center")
    ax.grid(axis="y", alpha=0.3)
    return save_fig("fig_safety.png")


def fig_app_framework():
    fig, ax = plt.subplots(figsize=(7.15, 9.3))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 13.4)
    ax.axis("off")
    ax.set_title("App 组成框架", fontproperties=FP, fontsize=15, pad=4)

    def card(x, y, w, h, title, body, face):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02",
                                    facecolor=face, edgecolor="#37474F", lw=1.0))
        ax.text(x + w / 2, y + h * 0.66, title, ha="center", va="center",
                fontproperties=FP, fontsize=10, color="#1A237E")
        if body:
            ax.text(x + w / 2, y + h * 0.30, body, ha="center", va="center",
                    fontproperties=FP, fontsize=8, color="#424242")

    ax.text(0.2, 12.95, "页面", fontproperties=FP, fontsize=10, color="#00695C")
    pages = [
        (0.2, "概览", "指标、曲线、抓拍"),
        (2.65, "日志", "换水与测量记录"),
        (5.1, "计划", "周期任务"),
        (7.55, "鱼缸", "档案与水型"),
    ]
    for x, t, b in pages:
        card(x, 11.45, 2.25, 1.35, t, b, "#E0F2F1")
    extras = [
        (0.2, "AI 对话", "解释与识图建议"),
        (3.45, "设置", "模型与连接说明"),
        (6.7, "设备配置", "地址、阈值、云 ID"),
    ]
    for x, t, b in extras:
        card(x, 9.85, 3.05, 1.25, t, b, "#F3E5F5")

    ax.text(4.85, 9.55, "↓", ha="center", va="center", fontproperties=FP, fontsize=14, color="#00695C")
    ax.text(0.2, 9.15, "共用组件", fontproperties=FP, fontsize=10, color="#00695C")
    widgets = [
        (0.2, "指标卡", "按水型切换语义"),
        (2.65, "趋势曲线", "24 h / 7 d"),
        (5.1, "执行器面板", "手动优先"),
        (7.55, "生物清单", "识别结果可改"),
    ]
    for x, t, b in widgets:
        card(x, 7.65, 2.25, 1.35, t, b, "#E8EAF6")

    ax.text(4.85, 7.35, "↓", ha="center", va="center", fontproperties=FP, fontsize=14, color="#1565C0")
    card(0.2, 5.85, 9.6, 1.35, "AppStore 全局状态", "当前缸、遥测快照、链路状态、云端照片、告警与分析记录", "#E3F2FD")

    ax.text(4.85, 5.5, "↓", ha="center", va="center", fontproperties=FP, fontsize=14, color="#1565C0")
    ax.text(0.2, 5.25, "服务", fontproperties=FP, fontsize=10, color="#00695C")
    services = [
        (0.2, 3.75, "设备直连", "WebSocket / HTTP"),
        (3.45, 3.75, "云链路", "MQTT / TLS 8883"),
        (6.7, 3.75, "摄像头", "局域网抓拍"),
        (0.2, 2.25, "告警引擎", "规则与横幅"),
        (3.45, 2.25, "大模型", "只给建议"),
        (6.7, 2.25, "本机存储", "缸、日志、计划"),
    ]
    for x, y, t, b in services:
        card(x, y, 3.05, 1.25, t, b, "#FFF8E1")

    card(0.2, 0.85, 9.6, 1.1, "运行", "同一套 Dart：Android 与鸿蒙；云端不可达时仍可读本机档案", "#E8F5E9")
    ax.text(0.2, 0.35, "页面经 AppStore 访问服务。云端查看时控制只读，大模型不直接驱动执行器。",
            fontproperties=FP, fontsize=8.5, color="#37474F")
    return save_fig("fig_app_fw.png")


def fig_cost():
    labels = ["主控+传感", "执行器", "摄像头", "结构件", "其他"]
    sizes = [35, 25, 15, 15, 10]
    colors = ["#2DD4BF", "#60A5FA", "#A78BFA", "#FBBF24", "#F87272"]
    fig, ax = plt.subplots(figsize=(6.5, 5))
    ax.pie(sizes, labels=labels, autopct="%1.0f%%", colors=colors, startangle=90)
    ax.set_title("样机物料成本结构（示意）")
    return save_fig("fig_cost.png")


def _box(ax, x, y, w, h, text, fc="#E0F2F1"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.03",
                                facecolor=fc, edgecolor="#37474F", lw=1.1))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=8.5, fontproperties=FP)


def fig_power_rails():
    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.axis("off")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4.2)
    _box(ax, 0.2, 2.6, 1.8, 1.2, "220V\n适配器\n12V/3A", "#FFECB3")
    _box(ax, 2.6, 2.6, 2.0, 1.2, "PG16 进盒\n12V 母线", "#FFF3E0")
    _box(ax, 5.2, 3.0, 2.2, 0.9, "12V：泵/喂食/CO₂\nTDS·pH 从机", "#FFCCBC")
    _box(ax, 5.2, 1.6, 2.2, 1.0, "LM2596S≥3A\n空载调至 5.0V", "#C8E6C9")
    _box(ax, 7.8, 1.6, 1.9, 1.0, "5V：ESP32\nSR04/TF/CAM", "#B2DFDB")
    _box(ax, 7.8, 0.3, 1.9, 1.0, "板载 LDO\n3.3V 逻辑", "#E1BEE7")
    _box(ax, 0.2, 0.4, 4.4, 1.4, "自备电源不进 12V 轨\n加热棒 220V 只切相线 L\n灯 12/24V 经继电器 COM–NO", "#ECEFF1")
    for a, b in [((2.0, 3.2), (2.6, 3.2)), ((4.6, 3.2), (5.2, 3.4)),
                 ((4.6, 3.0), (5.2, 2.1)), ((7.4, 2.1), (7.8, 2.1))]:
        ax.annotate("", xy=b, xytext=a, arrowprops=dict(arrowstyle="->", color="#455A64"))
    ax.set_title("整机单电源三轨（12V / 5V / 3.3V）", fontsize=12)
    return save_fig("fig_power.png")


def fig_rs485():
    fig, ax = plt.subplots(figsize=(7.15, 8.4))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 12)
    ax.axis("off")
    ax.set_title("水质总线：轮询、换算、写入同一份状态", fontproperties=FP, fontsize=13, pad=6)
    steps = [
        (10.15, "#E3F2FD", "1  主控点名", "先问地址 2 的 TDS，再问地址 3 的 pH\n同一条 A/B 线，不能同时回答"),
        (8.15, "#E8F5E9", "2  电平转换", "串口进出转换器，9600 8N1\n转换器地线必须接主板地"),
        (6.15, "#FFF8E1", "3  从机应答", "TDS 回电导相关寄存器，pH 回酸碱度与氧化还原\n从机自带电源，不从总线取电"),
        (4.15, "#F3E5F5", "4  换算", "TDS 乘 0.01 得 ppm，且温度探头必须插上\npH 乘 0.01，氧化还原电位乘 0.1"),
        (2.15, "#E0F2F1", "5  进入控制", "新数写入当前状态并记下时刻\n无应答则不把旧数当成刚测到的值"),
    ]
    for i, (y, c, title, body) in enumerate(steps):
        ax.add_patch(FancyBboxPatch((0.6, y), 8.8, 1.7, boxstyle="round,pad=0.03",
                                    facecolor=c, edgecolor="#37474F", lw=1.0))
        ax.text(1.0, y + 1.2, title, fontproperties=FP, fontsize=12, color="#1A237E", va="center")
        ax.text(1.0, y + 0.5, body, fontproperties=FP, fontsize=9, va="center")
        if i < len(steps) - 1:
            ax.annotate("", xy=(5.0, y - 0.28), xytext=(5.0, y),
                        arrowprops=dict(arrowstyle="->", color="#00695C", lw=1.4))
    ax.text(0.6, 0.7, "后续：超时仍无新值，则停止用该路去开加热或气阀。", fontproperties=FP, fontsize=9)
    return save_fig("fig_rs485.png")


def fig_sensor_rc():
    fig, ax = plt.subplots(figsize=(7.15, 8.2))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 11.6)
    ax.axis("off")
    ax.set_title("本地测量：调理后汇入同一次采样", fontproperties=FP, fontsize=13, pad=6)
    paths = [
        (8.55, "#FFF8E1", "水温", "探头入水 → 4.7 kΩ 上拉到 3.3 V → 主控读数"),
        (7.15, "#E3F2FD", "水位", "触发测距 → 回波经 1 kΩ / 2 kΩ 分压 → 按空满两点换成百分比"),
        (5.75, "#F3E5F5", "光照", "模块地址 0x23 → 时钟与数据进入主控 → 得到照度"),
    ]
    for y, c, name, desc in paths:
        ax.add_patch(FancyBboxPatch((0.35, y), 9.3, 1.15, boxstyle="round,pad=0.02",
                                    facecolor=c, edgecolor="#37474F"))
        ax.text(0.55, y + 0.78, name, fontproperties=FP, fontsize=11, color="#1A237E")
        ax.text(2.3, y + 0.55, desc, fontproperties=FP, fontsize=9, va="center")
    ax.annotate("", xy=(5.0, 5.08), xytext=(5.0, 5.72),
                arrowprops=dict(arrowstyle="->", color="#546E7A", lw=1.2))
    ax.add_patch(FancyBboxPatch((1.3, 3.55), 7.4, 1.45, boxstyle="round,pad=0.03",
                                facecolor="#E8F5E9", edgecolor="#2E7D32", lw=1.2))
    ax.text(5.0, 4.55, "汇合：写入当前水质，并记下更新时刻", ha="center", fontproperties=FP, fontsize=11)
    ax.text(5.0, 3.95, "三路彼此独立，缺一路不影响另外两路采样", ha="center", fontproperties=FP, fontsize=9)
    ax.annotate("", xy=(3.2, 2.55), xytext=(4.2, 3.55),
                arrowprops=dict(arrowstyle="->", color="#2E7D32", lw=1.3))
    ax.annotate("", xy=(6.8, 2.55), xytext=(5.8, 3.55),
                arrowprops=dict(arrowstyle="->", color="#C62828", lw=1.3))
    ax.add_patch(FancyBboxPatch((0.35, 0.85), 4.2, 1.7, boxstyle="round,pad=0.02",
                                facecolor="#E0F2F1", edgecolor="#00695C"))
    ax.text(2.45, 1.95, "时刻仍新", ha="center", fontproperties=FP, fontsize=11, color="#00695C")
    ax.text(2.45, 1.35, "参与加热、补光、补水判断", ha="center", fontproperties=FP, fontsize=9)
    ax.add_patch(FancyBboxPatch((5.45, 0.85), 4.2, 1.7, boxstyle="round,pad=0.02",
                                facecolor="#FFEBEE", edgecolor="#C62828"))
    ax.text(7.55, 1.95, "超过时限无新值", ha="center", fontproperties=FP, fontsize=11, color="#C62828")
    ax.text(7.55, 1.35, "停用该路自动动作", ha="center", fontproperties=FP, fontsize=9)
    return save_fig("fig_sensor_rc.png")


def fig_actuator():
    fig, ax = plt.subplots(figsize=(7.15, 8.6))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 12.2)
    ax.axis("off")
    ax.set_title("执行过程：判断之后才接通功率回路", fontproperties=FP, fontsize=13, pad=6)
    ax.add_patch(FancyBboxPatch((0.4, 10.15), 9.2, 1.35, boxstyle="round,pad=0.02",
                                facecolor="#E8EAF6", edgecolor="#37474F"))
    ax.text(5.0, 11.05, "1  缸边给出本次结论", ha="center", fontproperties=FP, fontsize=12)
    ax.text(5.0, 10.5, "自动条件满足，或用户改成手动。手动时自动不再改写。", ha="center", fontproperties=FP, fontsize=9)
    ax.annotate("", xy=(5.0, 9.85), xytext=(5.0, 10.15),
                arrowprops=dict(arrowstyle="->", color="#37474F", lw=1.3))
    ax.text(2.5, 9.55, "灯 / 加热 / 补水 / 喂食", ha="center", fontproperties=FP, fontsize=10, color="#1565C0")
    ax.text(7.5, 9.55, "二氧化碳阀", ha="center", fontproperties=FP, fontsize=10, color="#C62828")
    relay = [
        (7.7, "2  控制脚拉低"),
        (6.15, "3  继电器吸合"),
        (4.6, "4  触点：电源正极经公共端到常开端，再进负载"),
        (3.05, "5  负载负极回到其自身电源，不进主控 5 V"),
    ]
    mos = [
        (7.7, "2  控制脚拉高"),
        (6.15, "3  低边开关导通"),
        (4.6, "4  阀的负极经开关回到地"),
        (3.05, "5  阀正极仍接 12 V，不经继电器"),
    ]
    for x0, rows, color in ((0.35, relay, "#E3F2FD"), (5.15, mos, "#FFEBEE")):
        for y, text in rows:
            ax.add_patch(FancyBboxPatch((x0, y), 4.5, 1.25, boxstyle="round,pad=0.02",
                                        facecolor=color, edgecolor="#37474F"))
            ax.text(x0 + 2.25, y + 0.62, text, ha="center", va="center", fontproperties=FP, fontsize=9)
        for y in (7.45, 5.9, 4.35):
            ax.annotate("", xy=(x0 + 2.25, y), xytext=(x0 + 2.25, y + 0.25),
                        arrowprops=dict(arrowstyle="->", color="#455A64", lw=1.1))
    ax.add_patch(FancyBboxPatch((0.4, 0.85), 9.2, 1.55, boxstyle="round,pad=0.02",
                                facecolor="#E8F5E9", edgecolor="#2E7D32", lw=1.1))
    ax.text(5.0, 1.85, "6  结果写回状态，供页面、电脑和云端显示", ha="center", fontproperties=FP, fontsize=11)
    ax.text(5.0, 1.25, "上电时继电器控制脚先拉高，触点保持断开。补水泵另有上拉，避免误启动。", ha="center", fontproperties=FP, fontsize=9)
    return save_fig("fig_actuator.png")


def fig_enclosure():
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.set_xlim(0, 200)
    ax.set_ylim(0, 120)
    ax.set_aspect("equal")
    ax.add_patch(plt.Rectangle((0, 0), 200, 120, fill=False, lw=2, ec="#37474F"))
    zones = [
        (8, 8, 55, 48, "#FFF8E1", "①电源区\n12V进线/保险\nLM2596S"),
        (70, 8, 60, 48, "#E3F2FD", "②端子排\n12V/5V/GND\nUSB-A→CAM"),
        (136, 8, 56, 48, "#FFEBEE", "④驱动区\n继电器/MOS/485"),
        (40, 64, 90, 48, "#E8F5E9", "③主控区\nESP32+TF\n排母可更换"),
        (136, 64, 56, 48, "#F5F5F5", "⑤预留\n散热走线"),
    ]
    for x, y, w, h, c, t in zones:
        ax.add_patch(plt.Rectangle((x, y), w, h, fc=c, ec="#546E7A"))
        ax.text(x + w / 2, y + h / 2, t, ha="center", va="center", fontsize=8)
    ax.set_title("防水盒 200×120×75 mm 内部分区（强弱电分离）", fontsize=12)
    ax.set_xlabel("mm")
    return save_fig("fig_box.png")


def fig_struct():
    fig, ax = plt.subplots(figsize=(7.15, 8.4))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 12)
    ax.axis("off")
    ax.set_title("结构安装顺序：先固定，再入水，再动作", fontproperties=FP, fontsize=13, pad=6)
    steps = [
        ("1  盒体就位", "电源、主控和驱动放进防水盒，强弱电分开，线从接头引出"),
        ("2  夹在缸沿", "倒 L 支架卡在玻璃上，上板留在水面以上，下板伸进水里"),
        ("3  探头入水", "水温、TDS、pH 各自进孔，方向垂直，避免贴壁"),
        ("4  测水位", "超声模块吊在横板下方，声波向下，避开近处盲区"),
        ("5  定量喂食", "一次短脉冲让八格转盘转过一格，饲料落下，而不是持续通电"),
        ("6  旁边观察", "摄像头挂在缸外，只提供画面，不参与上述动作"),
    ]
    colors = ["#FFF8E1", "#E3F2FD", "#E0F2F1", "#E8EAF6", "#FCE4EC", "#F3E5F5"]
    for i, ((title, body), c) in enumerate(zip(steps, colors)):
        y = 10.15 - i * 1.65
        ax.add_patch(FancyBboxPatch((0.45, y), 9.1, 1.4, boxstyle="round,pad=0.02",
                                    facecolor=c, edgecolor="#37474F"))
        ax.text(0.7, y + 0.95, title, fontproperties=FP, fontsize=12, color="#1A237E", va="center")
        ax.text(0.7, y + 0.42, body, fontproperties=FP, fontsize=9, va="center")
        if i:
            ax.annotate("", xy=(5.0, y + 1.42), xytext=(5.0, y + 1.62),
                        arrowprops=dict(arrowstyle="->", color="#00695C", lw=1.2))
    return save_fig("fig_struct.png")


def fig_cloud_edge():
    fig, ax = plt.subplots(figsize=(7.15, 8.8))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 12.4)
    ax.axis("off")
    ax.set_title("云边协同：缸边决策，云端送达", fontproperties=FP, fontsize=14, pad=6)

    def card(x, y, w, h, title, body, face):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02",
                                    facecolor=face, edgecolor="#37474F", lw=1.0))
        ax.text(x + w / 2, y + h - 0.38, title, ha="center", fontproperties=FP, fontsize=11, color="#1A237E")
        ax.text(x + w / 2, y + (h - 0.5) / 2, body, ha="center", va="center", fontproperties=FP, fontsize=8.5)

    card(0.3, 9.55, 4.4, 2.2, "现场访问", "手机或计算机直接连接主控\n约每秒获得新状态\n可立即人工干预", "#E3F2FD")
    card(5.3, 9.55, 4.4, 2.2, "离场访问", "手机改由云端获取数据\n查看最近状态与照片\n命令经云端返回主控", "#E8F5E9")
    ax.annotate("", xy=(5.15, 10.6), xytext=(4.85, 10.6),
                arrowprops=dict(arrowstyle="<->", color="#37474F", lw=1.2))

    card(0.3, 6.55, 9.4, 2.35, "现场主控  ·  每秒决策", "采集 → 核验测值是否有效 → 按水质或人工指令驱动设备\n该步骤不上传云端等待答复\n云端中断时，已启用策略继续执行", "#FFF8E1")
    ax.annotate("", xy=(2.5, 8.95), xytext=(2.5, 9.55),
                arrowprops=dict(arrowstyle="->", color="#1565C0", lw=1.2))
    ax.annotate("", xy=(7.5, 8.95), xytext=(7.5, 9.55),
                arrowprops=dict(arrowstyle="->", color="#2E7D32", lw=1.2))

    card(0.3, 3.7, 4.4, 2.2, "主控上报", "约 30 秒一次水质与设备状态\n开关变化时立刻补一条事件\n摄像头另送最近一张照片", "#F3E5F5")
    card(5.3, 3.7, 4.4, 2.2, "云端转发", "按设备分开保存最近内容\n只把“控制”和“投喂”送回主控\n其他内容不进入功率回路", "#E0F2F1")
    ax.annotate("", xy=(5.2, 4.8), xytext=(4.8, 4.8),
                arrowprops=dict(arrowstyle="<->", color="#6A1B9A", lw=1.3))
    ax.annotate("", xy=(2.5, 5.95), xytext=(2.5, 6.55),
                arrowprops=dict(arrowstyle="<->", color="#6A1B9A", lw=1.2))
    ax.annotate("", xy=(7.5, 5.95), xytext=(7.5, 6.55),
                arrowprops=dict(arrowstyle="<->", color="#2E7D32", lw=1.2))

    card(0.3, 0.85, 9.4, 2.15, "辅助建议独立于控制", "手机将水质说明与照片提交大模型，模型仅返回文字\n文字回到对话页，不转换为加热或开阀指令", "#FFEBEE")
    return save_fig("fig_cloud.png")


def fig_sw_layers():
    fig, ax = plt.subplots(figsize=(11, 6.2))
    ax.axis("off")
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 7.4)
    ax.set_title("软件方案：同一份遥测字段贯穿 Web、上位机与 App", fontproperties=FP, fontsize=13)
    rows = [
        (6.0, "#E8EAF6", "人机", "Web 卡片与手动/自动", "上位机曲线与 CSV", "App 日志计划告警与识图"),
        (4.7, "#E3F2FD", "协议", "ws://地址/ws 的 tel 帧", "MQTT tel evt cmd img", "配置带 rev，冲突则拒绝"),
        (3.4, "#E8F5E9", "服务", "配网、NTP、mDNS", "历史 LittleFS 与 TF", "云链路 TLS 与命令白名单"),
        (2.1, "#FFF8E1", "控制", "1 秒节拍", "手动优先于自动", "pH 超时则关二氧化碳"),
        (0.8, "#FFEBEE", "驱动", "Modbus 轮询", "单总线与 I2C", "GPIO 上电默认断开"),
    ]
    for y, c, name, a, b, d in rows:
        ax.add_patch(FancyBboxPatch((0.3, y), 11.4, 1.1, boxstyle="round,pad=0.02",
                                    facecolor=c, edgecolor="#455A64"))
        ax.text(0.5, y + 0.55, name, fontproperties=FP, fontsize=12, va="center", color="#1A237E")
        ax.text(2.2, y + 0.55, a + "    " + b + "    " + d, fontproperties=FP, fontsize=9, va="center")
    return save_fig("fig_sw.png")


def fig_fw_loop():
    fig, ax = plt.subplots(figsize=(9, 2.8))
    ax.axis("off")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 2.6)
    steps = ["WDT", "485", "温度", "光照", "水位", "控制", "发布"]
    for i, s in enumerate(steps):
        _box(ax, 0.2 + i * 1.4, 0.8, 1.2, 0.9, s, "#E0F7FA")
        if i:
            ax.annotate("", xy=(0.2 + i * 1.4, 1.25), xytext=(0.2 + i * 1.4 - 0.2, 1.25),
                        arrowprops=dict(arrowstyle="->", color="#00695C"))
    ax.set_title("主循环节拍（看门狗 2 s，控制 1 s）", fontsize=12)
    return save_fig("fig_loop.png")


def fig_roadmap():
    fig, ax = plt.subplots(figsize=(7.15, 8.6))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 12.2)
    ax.axis("off")
    ax.set_title("技术路线", fontproperties=FP, fontsize=15, pad=4)

    phases = ["1  边缘闭环", "2  总线适配", "3  多端一致", "4  整机装备"]
    colors = ["#E3F2FD", "#E8F5E9", "#FFF8E1", "#F3E5F5"]
    rows = [
        ("固件与安全", [
            "引脚定稿\n上电全断\n看门狗 2 秒",
            "有效性门\nvalidity gate\npH 滞回",
            "同一遥测字段\n配置版本号\n命令白名单",
            "断网仍运行\n现场可演示\n不依赖云端",
        ]),
        ("传感与功率", [
            "12 V / 5 V / 3.3 V\n继电器低触发\nCO2 低边 MOS",
            "485 共地\nTDS@2  pH@3\n寄存器可改",
            "NTC 补偿\n超声量程\n光照进补光",
            "强弱电分区\n加热只切相线\n摄像头独立 5 V",
        ]),
        ("终端与结构", [
            "内嵌 Web\n手动优先\nmDNS 区分设备",
            "上位机曲线\n历史 TF\nCSV 导出",
            "App 告警计划\n离开局域网\n水型语义切换",
            "缸沿支架\n定量喂食器\n照片只作辅助",
        ]),
    ]
    ax.text(0.15, 11.35, "先把缸边闭环做稳，再扩总线、多端和可打印结构。后一阶段复用前一阶段的安全约束。",
            fontproperties=FP, fontsize=9, color="#37474F")

    for i, (name, col) in enumerate(zip(phases, colors)):
        x = 2.05 + i * 1.95
        ax.add_patch(FancyBboxPatch((x, 10.35), 1.85, 0.7, boxstyle="round,pad=0.02",
                                    facecolor=col, edgecolor="#37474F", lw=1.0))
        ax.text(x + 0.92, 10.7, name, ha="center", va="center", fontproperties=FP, fontsize=9)
        if i < 3:
            ax.annotate("", xy=(x + 1.95, 10.7), xytext=(x + 1.85, 10.7),
                        arrowprops=dict(arrowstyle="->", color="#00695C", lw=1.2))

    y0 = 7.55
    for r, (label, cells) in enumerate(rows):
        y = y0 - r * 2.45
        ax.add_patch(FancyBboxPatch((0.12, y), 1.8, 2.2, boxstyle="round,pad=0.02",
                                    facecolor="#ECEFF1", edgecolor="#37474F", lw=1.0))
        ax.text(1.02, y + 1.1, label, ha="center", va="center", fontproperties=FP, fontsize=10)
        for i, text in enumerate(cells):
            x = 2.05 + i * 1.95
            ax.add_patch(FancyBboxPatch((x, y), 1.85, 2.2, boxstyle="round,pad=0.02",
                                        facecolor=colors[i], edgecolor="#90A4AE", lw=0.8))
            ax.text(x + 0.92, y + 1.1, text, ha="center", va="center", fontproperties=FP, fontsize=8)

    ax.text(0.15, 0.55,
            "阶段验收：断网仍能控；从站地址可改且读数合理；离开局域网仍能看遥测；结构件可打印并装到缸沿。",
            fontproperties=FP, fontsize=9, color="#37474F")
    return save_fig("fig_roadmap.png")


def make_all_figs():
    return {
        "arch": fig_system_architecture(),
        "control": fig_control_loop(),
        "mqtt": fig_mqtt_topics(),
        "metrics": fig_metrics_demo(),
        "pins": fig_pin_map(),
        "power": fig_power_rails(),
        "rs485": fig_rs485(),
        "sensor_rc": fig_sensor_rc(),
        "actuator": fig_actuator(),
        "box": fig_enclosure(),
        "struct": fig_struct(),
        "sw": fig_sw_layers(),
        "cloud": fig_cloud_edge(),
        "loop": fig_fw_loop(),
        "app": fig_app_ia(),
        "app_fw": fig_app_framework(),
        "safety": fig_safety(),
    }


# -------------------- content blocks --------------------
ABSTRACT = (
    "针对家庭与教学水族监测分散、执行多依赖定时、养护难以追溯以及离场后状态不可察等问题，"
    "本作品设计 iAquaria 智能水族系统。方案将现场硬件、应用软件与云端传递划分为三个协同分区："
    "硬件采集水温、酸碱度、溶解性固体、水位与光照，并驱动照明、加热、补水、投喂及二氧化碳供给；"
    "软件承担监视、记录、告警与人工干预；云端在用户离开局域网后传递最近状态与图像。"
    "控制决策保留于现场，测值超时则中止相应自动控制。方案适用于家庭草缸、海水缸及实验教学。"
)
KEYWORDS = "智能水族；边缘控制；Modbus；MQTT；多端协同"


def write_cover(doc, pages_hint):
    for _ in range(3):
        doc.add_paragraph()
    for line in [
        "第十届全国大学生智慧水族造景技能大赛",
        "智能水族设计赛道设计方案报告",
    ]:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.first_line_indent = Cm(0)
        run = p.add_run(line)
        set_run_font(run, name_cn="黑体", size=18, bold=True)
    doc.add_paragraph()
    fields = [
        ("作 品 名 称：", "iAquaria 智能水族多端协同控制系统"),
        ("参 赛 类 别：", "控制系统 / 软件 / 装备"),
        ("报告总页数：", str(pages_hint)),
        ("开源仓库：", GITHUB),
    ]
    for k, v in fields:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.first_line_indent = Cm(0)
        p.paragraph_format.space_before = Pt(8)
        run = p.add_run(k + v)
        set_run_font(run, size=14)
    page_break(doc)


def write_abstract(doc):
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Cm(0)
    run = p.add_run("摘要：")
    set_run_font(run, name_cn="黑体", size=12, bold=True)
    run2 = p.add_run(ABSTRACT)
    set_run_font(run2, size=12)
    p2 = doc.add_paragraph()
    p2.paragraph_format.first_line_indent = Cm(0)
    r = p2.add_run("关键词：")
    set_run_font(r, name_cn="黑体", size=12, bold=True)
    r2 = p2.add_run(KEYWORDS)
    set_run_font(r2, size=12)
    doc.add_paragraph()


def chapter1(doc, figs, detailed=True):
    FIG["n"] = 0
    TAB["n"] = 0
    add_title(doc, "1. 项目背景介绍", 1)
    add_title(doc, "1.1 现存问题", 2)
    add_body(
        doc,
        "家庭观赏缸、水草缸与教学实验缸在日常养护中普遍存在三类问题：水质状态难以综合判断，执行机构难以随水质调整，养护过程难以追溯。",
    )
    add_body(
        doc,
        "水质状态难以综合判断，是因为水温、酸碱度、溶解性固体与光照多由独立仪表分别读取。换水、开灯等操作前后的变化缺少统一时间基准，故障发生时难以确定首先偏离的指标。海水缸需将电导率解释为盐度，淡水缸则关注过滤前后的溶解性固体；若显示含义不作区分，易造成误读。",
    )
    add_body(
        doc,
        "执行机构难以随水质调整，是因为加热、照明、二氧化碳供给与补水多由定时装置或人工开关完成。水质已经变化，设备仍按预设时刻动作。夜间或人员短时离岗时，观测与执行之间缺少衔接。更为严重的是，探头脱落或变送器无响应后，若控制器继续采用过期读数，将导致长时间加热或持续开阀。",
    )
    add_body(
        doc,
        "养护过程难以追溯，是因为换水、投喂与人工检测多依赖记忆，事后无法核对操作时间及当时水质。人员在场时需要即时监视与干预，离场后仍需确认鱼缸是否处于正常范围。若仅提供局域网页面，则离场后无法访问；若控制完全依赖云端，则家庭网络中断时加热与气阀将失去约束。",
    )
    add_title(doc, "1.2 使用需求", 2)
    add_body(
        doc,
        "针对上述问题，系统应同时满足以下需求，而不能仅将独立仪表替换为显示界面。",
    )
    add_body(
        doc,
        "第一，指标应集中呈现。水温、酸碱度、溶解性固体或盐度、水位与光照出现在同一界面，并保留近期曲线，以便对照。第二，执行应随水质变化，同时允许人工干预。酸碱度偏高时补充二氧化碳，水温偏低时加热，水位不足时补水，并按计划投喂。任一通道切换为手动后，自动控制不得再改写该通道。",
    )
    add_body(
        doc,
        "第三，测值失效时应中止相关动作。长时间未获得新读数时，不得依据旧值继续加热或开阀。第四，养护过程应可记录、异常应可提醒，周期性任务应可跟踪。第五，现场与离场均应可用：现场响应应及时，离场至少可获取最近状态；现场的执行决策不得依赖云端是否在线。",
    )
    add_table(
        doc,
        ["现存问题", "对应需求", "未能满足时的后果"],
        [
            ["仪表分散，淡水与海水读法不同", "同一界面集中显示，并按水型解释", "难以对照，易造成误判"],
            ["定时或人工开关，水质变化无人响应", "按水质执行，且可切换为手动", "夜间及离岗期间失控"],
            ["过期读数仍驱动设备", "测值失效即停止该项自动控制", "过量加热或长时间开阀"],
            ["换水与投喂缺少记录", "可追溯、可提醒、可安排计划", "养护经验无法复盘"],
            ["现场访问与离场访问相互排斥", "现场直连，离场经云端查看", "离场失察，或断网后失去约束"],
        ],
        1,
        "问题与需求对照",
    )
    add_title(doc, "1.3 立项目标", 2)
    add_body(
        doc,
        "据此，本作品将 iAquaria 划分为硬件、软件与云端三个分区，三者并列设计，而非仅完成单一控制板。硬件部署于鱼缸现场，承担测量、决策与执行；软件包括嵌入式网页、计算机端与手机应用，承担监视、记录与操作；云端在用户不处于同一局域网时传递状态，并回传允许范围内的命令。",
    )
    add_body(
        doc,
        "三个分区采用同一套水质数据。是否执行始终由现场主控决定。由此，现场可以即时操作，离场可以查看最近状态，网络中断时已启用的策略仍可继续运行。",
    )
    add_picture(doc, figs["arch"], 1, "硬件、软件与云端分区")
    add_body(
        doc,
        "图1-1 将三个分区并列表示。左列为现场的测量、决策、执行与图像采集；中列为手机与计算机上的监视、养护记录、水型化显示与辅助说明；右列为云端的接入、最近内容保留与命令转发。分区之间的箭头表示现场直连与离场改经云端，而不是将硬件细节集中绘制于同一列。",
    )


def chapter2(doc, figs, detailed=True):
    FIG["n"] = 0
    TAB["n"] = 0
    add_title(doc, "2. 关键技术与创新点", 1)
    add_body(
        doc,
        "本章依据第1章提出的需求说明关键做法，而不单独堆砌技术名词。测值失效后的安全停机仅为其中一项。指标集中呈现、闭环执行、过程可追溯、离场可察以及变送器现场可更换，均设置了对应措施。",
    )
    add_title(doc, "2.1 需求与做法对照", 2)
    add_table(
        doc,
        ["第1章提出的需求", "常见做法", "本作品做法"],
        [
            ["指标集中呈现", "多只仪表分别读取", "主控汇总，网页、计算机与 App 显示同一份数据"],
            ["执行跟随水质", "定时插座", "按酸碱度、水温与水位动作，照明可联动气阀"],
            ["允许人工干预", "无手动，或自动优先", "手动优先，自动控制不再改写"],
            ["测值失效即停止", "过期读数继续驱动", "超时则停止该项自动，并关闭相应输出"],
            ["养护可追溯", "依赖记忆", "日志、周期计划与告警保存在手机"],
            ["现场与离场均可使用", "仅有网页或仅有云端", "现场直连，离场经云端查看并下发命令"],
            ["淡水与海水区分显示", "指标固定", "按水型将同一路数据显示为溶解性固体或盐度"],
            ["更换变送器", "修改程序后重新烧录", "在网页中修改地址与换算系数"],
            ["解释不替代执行", "将模型输出接至继电器", "模型仅给出文字建议"],
        ],
        2,
        "由需求引出的做法",
    )
    add_title(doc, "2.2 以测量驱动执行并保留人工优先", 2)
    add_body(
        doc,
        "本节对应执行机构难以随水质调整的问题。主控约每秒读取一次当前水质。二氧化碳可在照明开启期间按酸碱度工作，默认高于 7.0 时开启、低于 6.8 时关闭，以避免在阈值附近反复通断。加热与补水同样采用分开的开启界限与关闭界限。投喂不持续通电，仅输出一次短脉冲，使喂食器转过一格。",
    )
    add_body(
        doc,
        "任一通道均可切换为手动。手动期间，即使自动条件成立，也不再改变该通道。若水温、光照或水位超过 60 秒，或酸碱度超过 120 秒仍未获得新读数，则该项自动控制停止，并关闭二氧化碳阀。该措施用于防止过期读数误控，并不是本作品的唯一创新。",
    )
    add_picture(doc, figs["control"], 2, "测量、决策与执行的关系")
    add_title(doc, "2.3 现场直连与离场云端协同", 2)
    add_body(
        doc,
        "本节对应离场后无法获知状态，以及网络中断后失去约束的问题。用户处于同一网络时，手机与计算机直接向主控获取数据，刷新及时，亦可立即干预。用户离场后，主控将最近状态与照片送至云端，手机改为从云端读取，且只能回传控制与投喂两类命令。",
    )
    add_body(
        doc,
        "云端中断时，现场主控不向云端请求下一步动作。已启用的自动策略按现场最后一套规则继续运行。因此，云端解决的是人员是否在场的问题，而不是每一秒是否开启气阀。具体链路见第3章。",
    )
    add_title(doc, "2.4 养护记录与按水型显示", 2)
    add_body(
        doc,
        "本节对应养护难以追溯，以及淡水与海水读法混淆的问题。手机以鱼缸为单元保存档案。概览页显示当前水质，日志页记录换水、投喂与人工测量，计划页安排周期任务，告警按规则提醒。",
    )
    add_body(
        doc,
        "淡水缸与草缸突出过滤前后的溶解性固体。海水缸将同一路数据解释为盐度，避免将淡水单位用于海水。Android 与鸿蒙采用同一套界面和数据，更换终端时不必另行适应另一套操作。",
    )
    add_picture(doc, figs["app"], 2, "手机端四项日常功能")
    add_title(doc, "2.5 变送器可配置与辅助建议的边界", 2)
    add_body(
        doc,
        "水质变送器品牌较多，寄存器定义并不统一。若每次更换都要修改程序并重新烧录，则教学与家庭场景均难以维护。本作品将从机地址、读取位置与换算系数置于网页配置中，保存后立即生效。",
    )
    add_body(
        doc,
        "图像识别与水质说明由大模型完成，结果仅呈现在对话中。用户确认后，再自行进入控制页操作。模型不能绕过主控接通加热或气阀，因而建议可以随时中止，设备状态仍然可解释。",
    )


def chapter3(doc, figs, detailed=True):
    FIG["n"] = 0
    TAB["n"] = 0
    add_title(doc, "3. 项目技术方案设计和原理", 1)
    add_title(doc, "3.1 总体方案的三个分区", 2)
    add_body(
        doc,
        "总体方案沿用图1-1 的三列划分，而不按芯片引脚展开。硬件、软件与云端边界明确，三部分并列，避免方案退化为单一硬件清单。",
    )
    add_body(
        doc,
        "硬件分区在现场完成测量、每秒决策与功率执行，摄像头仅负责图像采集。软件分区包括主控网页、计算机上位机与 iAquaria 手机应用，负责呈现同一份数据，并接收人工操作、日志与计划。云端分区仅在用户离开局域网时传递最近状态、照片以及允许范围内的命令。",
    )
    add_table(
        doc,
        ["分区", "包含什么", "负责", "不负责"],
        [
            ["硬件", "探头、主控、执行器、缸沿结构、摄像头", "测量、决策、执行、图像采集", "不保存养护记录"],
            ["软件", "网页、计算机端、手机 App", "监视、人工干预、记录、提醒、水型化显示", "不在云端进行每秒决策"],
            ["云端", "加密消息服务", "传递最近状态、照片与允许的命令", "不直接接通阀门或加热"],
        ],
        3,
        "三个分区的边界",
    )
    add_title(doc, "3.2 硬件总体与供电原理", 2)
    add_body(
        doc,
        "系统由两台独立设备组成：ESP32 主板（传感与控制）和 ESP32-CAM（视觉）。"
        "整机采用单路外部电源：220V 适配器输出 12V/3A，经 PG16 进入 200×120×75 mm 防水盒。"
        "盒内 LM2596S（≥3A，空载先调至 5.0V）产生 5V 母线，ESP32 板载 LDO 仅提供短距 3.3V。"
        "加热棒与水族灯使用自备电源，只经继电器触点切换，不并入 12V 轨。",
    )
    add_picture(doc, figs["power"], 3, "整机单电源三轨原理")
    add_picture(doc, figs["pins"], 3, "主控引脚分配（与 Config.h 一致）")
    add_table(
        doc,
        ["电压轨", "来源", "负载"],
        [
            ["12V", "适配器经 PG16", "泵、喂食、CO₂阀、TDS/pH 从机"],
            ["5V", "LM2596S", "ESP32、SR04、TF、USB-A 供 CAM"],
            ["3.3V", "板载 LDO", "上拉与逻辑，禁止外带大电流"],
            ["自备", "负载电源", "220V 加热只切相线；灯走 DC 触点"],
        ],
        3,
        "三电压轨分配",
    )
    add_picture(doc, figs["box"], 3, "防水盒内部分区（强弱电分离）")
    add_slot(doc, "图位 A  防水盒内部实物（电源区 / 主控区 / 驱动区）")
    add_slot(doc, "图位 B  主板与 485、继电器、MOS 接线实物")

    add_title(doc, "3.3 传感原理与电路", 2)
    add_body(
        doc,
        "本地三类传感器点对点接入：DS18B20 为漏极开路单总线，DATA 必须经 4.7kΩ 上拉到 3.3V；"
        "HC-SR04 的 ECHO 为 5V，经 1kΩ 与 2kΩ 分压后接入 GPIO26，节点电压约 3.3V；"
        "BH1750 走硬件 I2C，ADO 悬空时地址 0x23。水位按空/满两点标定，超声探头垂直朝下并避开约 2cm 盲区。",
    )
    add_picture(doc, figs["sensor_rc"], 3, "本地传感器阻容接法")
    add_body(
        doc,
        "TDS 与 pH/ORP 挂在同一条 RS485 差分总线上，主站 UART1（TX17/RX16/DE4），9600 8N1、功能码 03。"
        "TDS 固定地址 2，寄存器 0/2 乘 0.01 得 ppm，其 NTC 探头必须接入，否则会按极低温补偿导致读数虚高约 3 倍。"
        "pH 变送器固定地址 3，寄存器 1 为 pH（×0.01），寄存器 9 为 ORP（×0.1 mV）。"
        "两从机独立供电，A/B 不得反接，也不得从总线取电；485 适配器 GND 必须与主板共地。",
    )
    add_picture(doc, figs["rs485"], 3, "RS485 总线与从机寄存器")
    add_slot(doc, "图位 C  TDS / pH 变送器与探头安装实物")

    add_title(doc, "3.4 执行器原理", 2)
    add_body(
        doc,
        "四路继电器为低电平触发：固件上电先把控制脚拉高，触点保持断开。"
        "功率回路一律为“电源正极进 COM、NO 出到负载正极、负载负极回电源负极”，与控制侧 5V 隔离。"
        "补水泵占用 GPIO5（strapping），必须另加 10kΩ 上拉到 3.3V，防止上电误吸合。"
        "CO₂ 电磁阀由 GPIO33 驱动 MOS 低边开关，阀负极接模块 OUT−，并建议在感性负载两端加续流二极管。"
        "喂食为定时脉冲（默认约 800 ms），对应转盘机构转过一格，而不是持续通电。",
    )
    add_picture(doc, figs["actuator"], 3, "继电器触点与 CO₂ 低边开关")
    add_slot(doc, "图位 D  喂食器、灯、加热棒、补水泵与 CO₂ 阀安装实物")

    add_title(doc, "3.5 结构装备（3D 打印件）", 2)
    add_body(
        doc,
        "电子模块装入防水盒，探头与摄像头用 3D 打印件固定在缸沿，经 PG12 出线。"
        "探头支架为倒 L 加整体 H 夹：上横板高于缸沿，下横板伸入水中导向，四孔分别对应水温、TDS、pH 与 pH 温补。"
        "超声支架把 HC-SR04 吊在横板下方，声波垂直向下。喂食器为 8 格水平转盘加低速直流电机，"
        "一次继电器脉冲对应一格落料。摄像头、光照模块与密封件另有独立外壳与挂架。"
        "参数化模型与 STL 位于开源仓库 docs 下的 probe_h_bracket、sr04_bracket、feeder、cam_hanger、"
        "gy30_case、usb_cam_case、seal_ring、sensor_mounts、tds_h_bracket 等目录。",
    )
    add_picture(doc, figs["struct"], 3, "三类关键结构件尺寸原理")
    add_slot(doc, "图位 E  探头支架 / 超声支架装缸实物")
    add_slot(doc, "图位 F  喂食器与摄像头挂架实物")
    if detailed:
        add_table(
            doc,
            ["结构件", "目录", "作用"],
            [
                ["探头 H 支架", "probe_h_bracket", "水温/TDS/pH 竖直导向"],
                ["超声支架", "sr04_bracket", "水位探头朝下"],
                ["TDS 缸沿件", "tds_h_bracket", "电导探头固定"],
                ["喂食器", "feeder", "脉冲定量投喂"],
                ["摄像头挂架/外壳", "cam_hanger / usb_cam_case", "视角与防护"],
                ["光照外壳", "gy30_case", "防凝露"],
                ["密封圈/帽", "seal_ring", "穿线防水"],
            ],
            3,
            "结构件与仓库目录对应",
        )

    add_title(doc, "3.6 云边协同", 2)
    add_body(
        doc,
        "第1章要求现场可以即时操作，离场后仍能获知鱼缸状态，网络中断时又不得失去约束。因此现场与云端必须分工，而不能将决策转移到云端。",
    )
    add_body(
        doc,
        "用户处于同一无线网络时，手机与计算机直接连接主控。页面约每秒更新，人工干预立即生效。此时可以不经过云端。",
    )
    add_body(
        doc,
        "用户离场后，主控约每 30 秒将水温、酸碱度、溶解性固体、水位、光照及各路开关状态发至云端，并保留最近一帧。照明、加热、补水、投喂或气阀发生变化时，再立即补发一条事件。摄像头将最近一张照片单独上传，供手机查看。",
    )
    add_body(
        doc,
        "手机操作设备时，只能发送控制与投喂两类命令。云端将这两类命令交回主控，主控仍按本地规则执行，例如人工优先，以及测值超时后拒绝自动开阀。其余内容不进入功率回路。",
    )
    add_body(
        doc,
        "云端中断时，主控不向云端询问下一步动作，现场已启用的策略继续运行。大模型不位于该链路之中：它在手机侧阅读水质说明与照片，仅将文字返回对话页。",
    )
    add_picture(doc, figs["cloud"], 3, "云边协同流程")
    add_body(
        doc,
        "图中上部区分现场访问与离场访问，中部为现场每秒决策，下部为状态上报与命令转发。辅助建议置于控制链路之外，以免与命令转发混淆。",
    )

    add_title(doc, "3.7 现场软件与上述流程的配合", 2)
    add_body(
        doc,
        "固件在现场按固定节拍工作：先确认主控未失去响应，再依次读取水质总线、水温、光照与水位，随后完成一次控制决策，最后将结果送至网页，并按周期送至云端。"
        "网页在编译时嵌入固件，主控上电即可打开，无需另行部署服务器。"
        "历史数据默认写入主控内部存储；插入存储卡后，约每 5 分钟再记录一次较密数据，供 24 小时与 7 天曲线查询。",
    )
    add_picture(doc, figs["sw"], 3, "软件分层")
    add_picture(doc, figs["loop"], 3, "固件主循环")
    add_picture(doc, figs["mqtt"], 3, "MQTT 主题约定")

    add_title(doc, "3.8 人机界面（截图预留）", 2)
    add_body(
        doc,
        "网页提供实时指标、手动或自动切换、变送器参数与历史曲线。计算机端适于长时间观察曲线并导出数据。"
        "手机分为概览、日志、计划与鱼缸四页，另设对话页用于水质说明与图像识别。Android 与鸿蒙共用该界面。"
        "下文先给出组成关系，界面位置留空，便于随后插入实际截图。",
    )
    add_picture(doc, figs["app_fw"], 3, "App 组成框架")
    add_slot(doc, "图位 G  Web 概览与实时曲线")
    add_slot(doc, "图位 H  Web 执行器控制与参数页")
    add_slot(doc, "图位 I  App 概览（含水型指标卡）")
    add_slot(doc, "图位 J  App 日志、计划与 AI 对话")
    if detailed:
        add_body(
            doc,
            "开发侧使用 PlatformIO 分别编译主板工程与摄像头工程。改 Web 页面后重新构建即可，无需手工打包资源。"
            "摄像头 WiFi 为编译期配置。刷写主板时不得中断 esptool；摄像头需先进入下载模式再上传。"
            "上述流程保证硬件原理、结构安装与软件界面可以按同一套引脚和协议复现。",
        )


def chapter4(doc, figs, detailed=True):
    FIG["n"] = 0
    TAB["n"] = 0
    add_title(doc, "4. 技术效果实现", 1)
    add_title(doc, "4.1 测试环境与方法", 2)
    add_body(
        doc,
        "测试在实验室的无线网络中进行，使用主控、摄像头、TDS 与酸碱度变送器，以及部分真实负载。"
        "检查方式包括：上电后执行器是否保持断开、配网后能否入网、两台主控是否会抢同一个名字、"
        "变送器能否应答、手动开关气阀是否动作、摄像头能否返回照片。",
    )
    add_table(
        doc,
        ["用例", "操作", "期望", "结果"],
        [
            ["上电安全", "上电观察执行器", "默认全断", "通过"],
            ["WiFi 配网", "AP 门户保存凭据", "重启后入网", "通过"],
            ["mDNS 唯一", "两台主控同网", "不同主机名", "通过"],
            ["TDS 读取", "地址正确接入", "无持续离线", "通过"],
            ["pH 通信", "无探头仅变送器", "Modbus 有应答", "通过*"],
            ["CO₂ 手动", "Web 手动开关", "阀体动作", "通过"],
            ["CAM 抓拍", "GET /capture", "返回 JPEG", "通过"],
            ["TF(CAM)", "板载卡槽", "识别 SDHC", "通过"],
        ],
        4,
        "关键功能测试结果摘要（*无探头时仅验证通信）",
    )
    add_picture(doc, figs["metrics"], 4, "典型运行遥测曲线（示意）")
    add_title(doc, "4.2 产品级效果", 2)
    add_body(
        doc,
        "效果按照第1章的需求衡量，即指标能否集中呈现、执行能否随水质变化、离场后能否获知状态、测值失效时能否停止，以及养护记录是否保留。"
        "下表不列出芯片占用率。占用率只能说明程序可以装入主控，不能说明鱼缸养护目标是否达到。",
    )
    add_table(
        doc,
        ["产品能力", "达到的程度", "对应的需求"],
        [
            ["指标集中呈现", "水温、酸碱度、氧化还原电位、溶解性固体、水位与光照同时显示", "避免仪表分散"],
            ["五路执行", "照明、加热、补水、投喂、二氧化碳可手动或自动", "摆脱单纯定时控制"],
            ["现场决策", "约每 1 秒决策一次，不向云端请求", "断网后仍按现场策略运行"],
            ["现场监视", "网页约每秒刷新；计算机可观察曲线并导出", "在场时可即时操作"],
            ["离场监视", "约 30 秒更新一次，保留最近状态与一张照片", "离场后仍可获知状态"],
            ["失效保护", "水温、光照、水位超过 60 秒，或酸碱度超过 120 秒无新值，则停止该项自动", "防止过期读数误控"],
            ["养护闭环", "日志、周期计划与告警规则可以保存", "换水与投喂可以追溯"],
            ["多缸与水型", "可以切换鱼缸；淡水显示溶解性固体，海水显示盐度", "避免两种水体误读"],
            ["终端覆盖", "手机覆盖 Android 与鸿蒙，并提供网页与计算机端", "同一份数据，多种入口"],
        ],
        4,
        "产品级效果指标",
    )
    add_picture(doc, figs["safety"], 4, "安全机制设计覆盖评估")
    if detailed:
        add_title(doc, "4.3 对比提升", 2)
        add_table(
            doc,
            ["能力", "传统定时插座方案", "本作品"],
            [
                ["水质自适应", "无", "有（阈值/滞回）"],
                ["失效保护", "弱", "测值无效则强制安全"],
                ["多端查看", "无/弱", "Web/PC/App/云"],
                ["养护闭环", "无", "日志+计划+告警"],
                ["视觉辅助", "无", "CAM+多模态 AI"],
                ["可配置性", "跳线/重烧录", "Web 热更新"],
            ],
            4,
            "与传统方案能力对比",
        )
        add_title(doc, "4.4 问题与改进", 2)
        add_body(
            doc,
            "外接存储卡在部分杜邦线条件下可能识别不稳，摄像头板载卡槽则可以正常识别，说明卡本身可用，后续改走线。"
            "酸碱度变送器要按实际地址配置，出厂地址可能与文档中的目标地址不一致，现场应先读通再接入自动控制。",
        )


def chapter5(doc, figs, detailed=True):
    FIG["n"] = 0
    TAB["n"] = 0
    add_title(doc, "5. 应用价值与市场前景", 1)
    add_title(doc, "5.1 应用价值", 2)
    add_body(
        doc,
        "对家庭用户，其价值在于降低水质失控造成的生物损失。加热、气阀与补水能够随测值动作，人员离场后仍可查看最近状态，换水与投喂不必再依赖记忆。损失往往不在于设备本身的费用，而在于鱼只与水草在无人值守时出现异常。",
    )
    add_body(
        doc,
        "对教学与竞赛，其价值在于过程可以核验。可以演示探头移除后气阀关闭，以及离开局域网后手机仍能查看最近照片，而不是仅展示一块处于运行状态的屏幕。开源的接线说明与结构文件，使其他人员能够按相同步骤完成装配。",
    )
    add_body(
        doc,
        "对相关装备，其价值在于提供可分解的参考结构：现场负责决策，手机负责记录，云端负责传递。后续的加热、照明或变送器只要符合这三个分区的边界，即可替换，而不必重做整套软件。",
    )
    add_title(doc, "5.2 目标用户与市场规模", 2)
    add_body(
        doc,
        "用户需求并不相同。草缸用户关注酸碱度与光照是否稳定，海水用户关注盐度是否被误读，实验室要求参数可改、过程可演示，造景队伍要求过程可以追溯。下表将诉求对应到产品中已经实现的部分，而不是分别为四类用户另行开发系统。",
    )
    add_table(
        doc,
        ["用户", "主要问题", "对应的产品部分"],
        [
            ["家庭草缸", "酸碱度、光照稳定，并减少值守", "现场联动与手机告警"],
            ["海水缸", "盐度不应按淡水指标解读", "水型切换与同一套测量"],
            ["教学实验", "能够演示失效时的系统行为", "开源说明与网页参数配置"],
            ["造景竞赛", "过程应当可以追溯", "日志、计划与摄像头"],
        ],
        5,
        "目标用户与已有功能的对应",
    )
    add_body(
        doc,
        "观赏水族及相关硬件的需求呈分层状态：一部分用户需要连续数据，另一部分用户需要降低事故概率。本作品以同一套现场设备覆盖测量与执行，以可选的云端和摄像头覆盖人员不在场的情形。现阶段首先服务具备自行接线条件的用户以及课程教学，随后再扩展渠道。",
    )
    add_title(doc, "5.3 推广与转化路径", 2)
    add_body(
        doc,
        "推广分为四个阶段。每一阶段均应能够独立演示。电气安全认证不置于第一阶段，功能数量亦不作为转化是否成立的标准。",
    )
    add_body(
        doc,
        "第一阶段为开放复现。仓库保持公开，并写明接线、烧录与默认参数。其他人员应能在自有鱼缸上完成测量、人工开关与手机查看。若该阶段不能完成，则后续套件缺少基础。",
    )
    add_body(
        doc,
        "第二阶段分为两档配置。基础配置包含主控、关键探头与缸沿结构件，用于解决指标集中与基本联动。进阶配置增加摄像头与云端查看，用于解决人员不在现场的问题。两档共用同一套手机软件，避免基础用户与进阶用户适应不同操作方式。",
    )
    add_body(
        doc,
        "第三阶段进入教学。实验不要求学生从零编写通信程序，而要求核验两项既定结果：探头失效后相关设备必须停止；离开局域网后仍能查看最近状态。结果可以核验，课程安排才具有可操作性。",
    )
    add_body(
        doc,
        "第四阶段再考虑小批量提供套件。涉及市电加热的部分必须写明仅切换相线，并由具备电工常识的人员安装。在该边界写明之前，不进入普通零售。当前阶段以开源复现与教学验证为主。",
    )
    add_table(
        doc,
        ["阶段", "对象", "交付内容", "完成标准"],
        [
            ["开放复现", "爱好者与学生", "文档、固件与结构文件", "能够测量、人工开关，手机能够查看"],
            ["基础套件", "家庭鱼缸", "主控、探头与缸沿结构件", "水质变化能够驱动相应设备"],
            ["离场查看", "需要离场的用户", "摄像头与云端", "离场后能够查看状态与最近照片"],
            ["教学案例", "课程", "可以核验的演示步骤", "失效即停止，断网后现场仍运行"],
            ["小批量", "具备安装条件的用户", "套件与安全说明", "市电接线边界已经写明"],
        ],
        5,
        "推广阶段与完成标准",
    )
    if detailed:
        add_body(
            doc,
            "转化时优先保证能够安装，并且失效后能够恢复，而不是继续增加传感器种类。配网页面、可修改的变送器地址以及上电默认断开，在后续提供套件时仍应保留。",
        )


def chapter6(doc, detailed=True):
    FIG["n"] = 0
    TAB["n"] = 0
    add_title(doc, "6. 其他补充说明", 1)
    add_title(doc, "6.1 开源与复现", 2)
    add_body(
        doc,
        f"本作品源代码与文档开源地址：{GITHUB} 。仓库在提交截止后至少 6 个月内保持公开可访问。"
        "克隆后可按 docs/wiring.md 与各子项目 README 完成编译烧录。摄像头 WiFi 等本地密钥请使用占位符配置，勿将真实口令提交到版本库。",
        first_line=True,
    )
    add_title(doc, "6.2 伦理与安全声明", 2)
    add_body(
        doc,
        "涉及 220 V 负载时须由具备电工常识人员接线，继电器与水族箱隔离；CO₂ 钢瓶与电磁阀需按规范固定。"
        "AI 输出仅供参考，不替代责任人巡检。",
    )
    add_title(doc, "6.3 致谢匿名说明", 2)
    add_body(
        doc,
        "本报告按赛道匿名要求撰写，凡需指代单位处统一写作“参赛队伍”。图表与截图已避免出现可识别身份信息。",
    )
    if detailed:
        add_title(doc, "6.4 术语表", 2)
        add_table(
            doc,
            ["术语", "含义"],
            [
                ["tel", "遥测帧"],
                ["evt", "事件帧"],
                ["测值有效性", "measurement validity；超时未更新则测值无效"],
                ["fresh", "固件字段，表示测值仍在有效期内"],
                ["stale", "测值超时无效，不得用于自动控制"],
                ["fail-safe", "失效后进入安全状态，如关阀、断热"],
                ["mDNS", "局域网主机名发现"],
                ["滞回", "开/关阈值分离防抖"],
                ["保留消息", "MQTT retained"],
            ],
            6,
            "常用术语",
        )
        add_title(doc, "6.5 参考文献（节选）", 2)
        refs = [
            "[1] Espressif Systems. ESP32 Technical Reference Manual.",
            "[2] Modbus Organization. Modbus Application Protocol Specification V1.1b3.",
            "[3] MQTT Version 3.1.1 / 5.0 OASIS Standard.",
            "[4] Flutter documentation; OpenHarmony Flutter SIG notes.",
            "[5] 水族养殖与水草缸维护相关公开资料与教材（综合整理）。",
        ]
        for r in refs:
            add_body(doc, r, first_line=False)
        add_title(doc, "6.6 详细模块说明附录", 2)
        topics = [
            ("配网与网络服务", "STA/AP 共存、NTP、mDNS、断线重连与门户配网流程。"),
            ("Web 前端资源嵌入", "构建前 gzip 压缩 index.html 并嵌入固件，降低文件系统依赖。"),
            ("历史存储格式", "定长记录追加、容量上限与折半压缩策略。"),
            ("云端证书校验", "CA 证书内置，避免 setInsecure 带来的中间人风险。"),
            ("App 告警引擎", "区间/百分比规则、连续触发去抖、冷却与跨天免打扰。"),
            ("喂食脉冲", "定时脉冲输出，避免继电器常吸。"),
            ("灯光跟随 CO₂", "可选策略，模拟白天光合与夜间停气。"),
            ("水位两点标定", "空/满毫米值映射百分比，适配不同缸高。"),
            ("主机名生成", "优先 cloud.dev_id，否则 MAC 后四位。"),
            ("CAM 服务端口", "80 控制与抓拍，81 MJPEG 流，降低单端口拥堵。"),
        ]
        for idx, (t, d) in enumerate(topics, 1):
            add_title(doc, f"6.6.{idx} {t}", 3)
            add_body(doc, d)
            add_body(
                doc,
                "实现上强调可观测：关键路径均有分级日志；配置变更提升 rev 以触发档案重载；"
                "命令路径提供 ack，便于人机界面确认。上述细节共同支撑方案从演示走向可维护系统。",
            )
            add_body(
                doc,
                "从工程管理角度，子目录分别对应主控、摄像头、上位机、Android 原型与 Flutter 双端 App，"
                "文档目录提供接线与结构件说明，方便不同角色并行协作而不互相阻塞。",
            )
        add_title(doc, "6.7 接口报文与配置示例附录", 2)
        add_body(
            doc,
            "为便于复现与评审理解，本节给出代表性报文与配置字段说明（字段名保持与实现一致）。"
            "实际部署时 Broker、密钥与主题前缀应按环境配置，禁止把密钥写入仓库。",
        )
        examples = [
            (
                "遥测 tel 示例",
                '{"ev":"tel","d":{"temp":26.4,"ph":6.92,"orp":280,"tds1":220,"tds2":180,'
                '"lux":4200,"lvl":86,"act":[0,0,1,0,0],"rssi":-48,"up":3600}}',
            ),
            (
                "控制命令示例",
                '{"cmd":"ctrl","ch":"co2","on":true} 或 {"cmd":"ctrl","ch":"light","mode":"auto"}',
            ),
            (
                "配置片段",
                "ctrl.co2.ph_on / ph_off / follow_light / max_on_min；regs.ph.addr / map.ph.reg / scale",
            ),
            (
                "CAM 抓拍",
                "HTTP GET http://<cam-ip>/capture → image/jpeg；流媒体 :81/stream",
            ),
        ]
        for title, body in examples:
            add_title(doc, "（1）" + title if title == examples[0][0] else title, 3)
            add_body(doc, body, first_line=False)

        add_title(doc, "6.8 物料清单（BOM）摘要", 2)
        add_table(
            doc,
            ["类别", "物料", "数量", "备注"],
            [
                ["主控", "ESP32 DevKitC", "1", "WROOM-32"],
                ["传感", "DS18B20", "1", "防水探头"],
                ["传感", "HC-SR04", "1", "水位"],
                ["传感", "BH1750/GY-30", "1", "光照"],
                ["传感", "TDS 变送器", "1", "RS485"],
                ["传感", "pH 变送器", "1", "RS485 隔离型"],
                ["执行", "4 路继电器", "1", "低电平触发"],
                ["执行", "MOS 模块", "1", "CO₂"],
                ["执行", "CO₂ 电磁阀", "1", "12 V"],
                ["视觉", "ESP32-CAM", "1", "OV2640/3660"],
                ["电源", "12V 适配器+DC-DC", "1", "≥2 A"],
                ["结构", "3D 打印支架套件", "1", "按缸定制"],
            ],
            6,
            "样机 BOM 摘要",
        )

        add_title(doc, "6.9 风险分析与对策", 2)
        add_table(
            doc,
            ["风险", "等级", "对策"],
            [
                ["探头失效误控", "高", "测值有效性门槛+强制关断"],
                ["GPIO 上电误动作", "中", "上拉/默认断开"],
                ["485 地址冲突", "中", "分步接入+可配地址"],
                ["云端密钥泄露", "高", "本地录入/禁止硬编码"],
                ["强电接线不当", "高", "隔离与专业施工"],
                ["多机 mDNS 冲突", "低", "MAC 后缀主机名"],
            ],
            6,
            "风险与对策",
        )

        add_title(doc, "6.10 扩展实验与数据记录模板", 2)
        for n in range(1, 29):
            if n > 1:
                page_break(doc)
            add_title(doc, f"6.10.{n} 实验记录页模板 {n}", 3)
            add_body(
                doc,
                "实验目的：验证某一传感/控制链路在设定工况下的稳定性与安全性。"
                "工况描述：温度设定区间、灯光时段、目标水位、是否启用 CO₂ 跟随等。"
                "采集方式：Web 实时观察 + 上位机 CSV 导出 + 串口关键事件日志。"
                "判定标准：无看门狗复位；无异常常开执行器；指标在合理物理范围；告警可复现。",
            )
            add_body(
                doc,
                "数据栏（填写）：日期____；设备ID____；固件版本____；起始/结束时间____；"
                "水温均值/极值____；pH 均值/极值____；TDS____；水位____；异常事件____；结论____。"
                "附加记录：执行器动作次数____；手动干预次数____；网络断线次数____；备注____________。",
                first_line=False,
            )
            add_body(
                doc,
                "分析要点：将执行器动作时间轴与水质曲线叠加，检查是否存在“传感延迟导致的过调”；"
                "评估滞回宽度是否合适；记录一次人工干预（手动模式）对系统恢复自动模式的影响。"
                "该模板用于教学实验与竞赛复盘，不替代正式计量校准证书。"
                "建议每次实验结束后立刻导出 CSV，并保存串口关键告警原文，形成可审计证据链。",
            )
            add_body(
                doc,
                "本页可复印使用。实验编号建议编码为：IAQ-YYYYMMDD-序号。指导教师或互评同学可在结论栏签字确认（正式提交匿名版请删除签字区）。",
            )

        add_title(doc, "6.11 部署检查清单", 2)
        checks = [
            "电源共地、12V/5V/3.3V 极性正确",
            "strapping 脚未误接负载；GPIO5 上拉已焊接",
            "485 A/B 与地址核对；先单设备后并联",
            "ECHO 分压电阻正确，防 5V 灌入",
            "配网后 mDNS/IP 可访问，Web 可开关执行器",
            "App MQTT 主题与 dev_id 一致",
            "CAM /capture 可用，镜头与防水安装可靠",
            "云端 TLS 证书校验开启，密钥不入库",
        ]
        for i, c in enumerate(checks, 1):
            add_body(doc, f"{i}. {c}", first_line=False)
            add_body(
                doc,
                "检查方法：按文档逐步通电；每一步仅增加一个变量；异常时回退到上一稳定状态。"
                "建议双人复核强电与钢瓶相关步骤。",
            )

        add_title(doc, "6.12 结语", 2)
        add_body(
            doc,
            "本作品从真实运维痛点出发，完成了边缘智能水族控制系统的软硬件一体设计，"
            "并在多端协同、安全优先与可配置接入方面形成可展示成果。后续将持续改进存储可靠性、"
            "标定流程与结构件标准化，推动开源社区与教学场景落地。",
        )
        add_body(
            doc,
            f"开源地址再次声明：{GITHUB}",
            first_line=False,
        )


def build(full: bool):
    figs = make_all_figs()
    doc = setup_doc()
    pages_hint = "见页脚" if full else "见页脚"
    write_cover(doc, pages_hint)
    # restart page numbering conceptually: Word field still continuous; cover counted in file but competition says cover not in total — we note in cover pages_hint as body estimate
    write_abstract(doc)
    chapter1(doc, figs, detailed=full)
    if full:
        page_break(doc)
    chapter2(doc, figs, detailed=full)
    if full:
        page_break(doc)
    chapter3(doc, figs, detailed=full)
    if full:
        page_break(doc)
    chapter4(doc, figs, detailed=full)
    if full:
        page_break(doc)
    chapter5(doc, figs, detailed=full)
    if full:
        page_break(doc)
    chapter6(doc, detailed=full)

    out = OUT_FULL if full else OUT_COMPACT
    try:
        doc.save(out)
    except OSError:
        out = out.with_name(out.stem + "-更新" + out.suffix)
        doc.save(out)
        print("原文件被占用，已另存为", out)
    return out


def estimate_pages_by_paragraphs(path: Path) -> int:
    """Rough estimate: not exact Word pagination."""
    from docx import Document as D
    d = D(str(path))
    chars = 0
    for p in d.paragraphs:
        chars += len(p.text)
    for t in d.tables:
        for row in t.rows:
            for cell in row.cells:
                chars += len(cell.text)
    # ~900-1100 Chinese chars/page at 小四 1.5 + figures consume pages
    text_pages = chars / 900.0
    fig_pages = 12 if "详版" in path.name else 6
    return int(math.ceil(text_pages + fig_pages))


if __name__ == "__main__":
    print("Generating figures and full report...")
    full = build(True)
    print("Saved", full)
    print("Generating compact report...")
    # reset counters by rebuilding figs already cached
    compact = build(False)
    print("Saved", compact)
    print("Rough page estimate full:", estimate_pages_by_paragraphs(full))
    print("Rough page estimate compact:", estimate_pages_by_paragraphs(compact))
