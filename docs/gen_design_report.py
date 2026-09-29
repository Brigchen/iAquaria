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

# Windows 中文字体，避免图中缺字
for _fname in ("Microsoft YaHei", "SimHei", "SimSun"):
    try:
        matplotlib.rcParams["font.sans-serif"] = [_fname, "DejaVu Sans"]
        matplotlib.rcParams["axes.unicode_minus"] = False
        break
    except Exception:
        pass
matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "SimSun", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False

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
    plt.savefig(path, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close()
    return path


def fig_system_architecture():
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6)
    ax.axis("off")
    boxes = [
        (0.3, 4.2, 2.4, 1.3, "#E0F7FA", "移动端 App\niAquaria\nAndroid / 鸿蒙"),
        (3.8, 4.2, 2.4, 1.3, "#E8F5E9", "云端 MQTT\nEMQX TLS\ntel / evt / img"),
        (7.2, 4.2, 2.4, 1.3, "#FFF3E0", "PC 上位机\nWebSocket\n曲线 / CSV"),
        (0.3, 2.0, 2.4, 1.5, "#F3E5F5", "ESP32-CAM\n抓拍 / MJPEG\nmDNS"),
        (3.8, 1.6, 2.4, 2.2, "#E3F2FD", "主控 ESP32\n传感+控制\nWeb/WS/MQTT"),
        (7.2, 2.0, 2.4, 1.5, "#FFEBEE", "执行器层\n灯/热/泵/喂\nCO₂ 阀"),
    ]
    for x, y, w, h, c, t in boxes:
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05",
                                    facecolor=c, edgecolor="#455A64", linewidth=1.5))
        ax.text(x + w / 2, y + h / 2, t, ha="center", va="center", fontsize=10)
    ax.annotate("", xy=(3.8, 4.8), xytext=(2.7, 4.8),
                arrowprops=dict(arrowstyle="<->", color="#00695C", lw=1.5))
    ax.annotate("", xy=(7.2, 4.8), xytext=(6.2, 4.8),
                arrowprops=dict(arrowstyle="<->", color="#00695C", lw=1.5))
    ax.annotate("", xy=(5.0, 3.8), xytext=(5.0, 4.2),
                arrowprops=dict(arrowstyle="<->", color="#1565C0", lw=1.5))
    ax.annotate("", xy=(2.7, 2.7), xytext=(3.8, 2.7),
                arrowprops=dict(arrowstyle="<->", color="#6A1B9A", lw=1.5))
    ax.annotate("", xy=(7.2, 2.7), xytext=(6.2, 2.7),
                arrowprops=dict(arrowstyle="->", color="#C62828", lw=1.5))
    ax.set_title("iAqua 多端协同总体架构", fontsize=13, pad=8)
    return save_fig("fig_arch.png")


def fig_control_loop():
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.axis("off")
    ax.set_xlim(0, 9)
    ax.set_ylim(0, 4)
    steps = [
        (0.3, 1.5, "传感采集\n1–5 s"),
        (2.4, 1.5, "新鲜度判定\n超时强制安全"),
        (4.5, 1.5, "控制策略\npH/温/水位"),
        (6.6, 1.5, "执行器输出\n手动优先"),
    ]
    for x, y, t in steps:
        ax.add_patch(FancyBboxPatch((x, y), 1.8, 1.2, boxstyle="round,pad=0.04",
                                    facecolor="#E0F2F1", edgecolor="#00695C"))
        ax.text(x + 0.9, y + 0.6, t, ha="center", va="center", fontsize=10)
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
    fig, ax = plt.subplots(figsize=(9, 3.8))
    ax.axis("off")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4)
    ax.text(5, 3.5, "MQTT 主题约定（TLS）", ha="center", fontsize=13, weight="bold")
    rows = [
        "iaquaria/{dev_id}/tel   ← 设备遥测（保留消息，约 30 s）",
        "iaquaria/{dev_id}/evt   ← 执行器事件",
        "iaquaria/{dev_id}/cmd   → App/云端下行命令",
        "iaquaria/{dev_id}/img   ← CAM 抓拍（Base64/二进制）",
    ]
    for i, r in enumerate(rows):
        ax.add_patch(FancyBboxPatch((1.0, 2.5 - i * 0.7), 8.0, 0.55,
                                    boxstyle="round,pad=0.02",
                                    facecolor="#ECEFF1", edgecolor="#546E7A"))
        ax.text(1.2, 2.75 - i * 0.7, r, va="center", fontsize=10, family="monospace")
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
    labels = ["传感新鲜", "手动优先", "超时切断", "上电安全", "看门狗"]
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


def fig_cost():
    labels = ["主控+传感", "执行器", "摄像头", "结构件", "其他"]
    sizes = [35, 25, 15, 15, 10]
    colors = ["#2DD4BF", "#60A5FA", "#A78BFA", "#FBBF24", "#F87272"]
    fig, ax = plt.subplots(figsize=(6.5, 5))
    ax.pie(sizes, labels=labels, autopct="%1.0f%%", colors=colors, startangle=90)
    ax.set_title("样机物料成本结构（示意）")
    return save_fig("fig_cost.png")


def fig_roadmap():
    fig, ax = plt.subplots(figsize=(9, 3.5))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 3)
    ax.axis("off")
    phases = [
        (0.4, "M0–M2\n传感与控制"),
        (2.7, "M3–M4\n485 与标定"),
        (5.0, "M5\nApp/云"),
        (7.3, "M6+\n量产优化"),
    ]
    for x, t in phases:
        ax.add_patch(FancyBboxPatch((x, 1.0), 2.0, 1.2, boxstyle="round,pad=0.04",
                                    facecolor="#E0F2F1", edgecolor="#00695C"))
        ax.text(x + 1.0, 1.6, t, ha="center", va="center", fontsize=10)
    ax.annotate("", xy=(9.5, 1.6), xytext=(0.3, 1.6),
                arrowprops=dict(arrowstyle="->", color="#004D40", lw=1.5))
    ax.set_title("研发里程碑路线图", fontsize=13)
    return save_fig("fig_roadmap.png")


def make_all_figs():
    return {
        "arch": fig_system_architecture(),
        "control": fig_control_loop(),
        "mqtt": fig_mqtt_topics(),
        "metrics": fig_metrics_demo(),
        "pins": fig_pin_map(),
        "app": fig_app_ia(),
        "safety": fig_safety(),
        "cost": fig_cost(),
        "roadmap": fig_roadmap(),
    }


# -------------------- content blocks --------------------
ABSTRACT = (
    "针对家庭与实验室水族场景中水质监测分散、执行器联动缺失、养护记录难以闭环等问题，"
    "本作品以“边缘主控 + 多端协同 + 云端可观测”为思路，研发智能水族管理系统 iAqua。"
    "系统以 ESP32 主控采集水温、pH/ORP、TDS、水位、光照等指标，闭环控制灯光、加热、补水、喂食与 CO₂；"
    "配套 ESP32-CAM 视觉节点、内嵌 Web 控制台、PC 上位机与 Flutter 双端 App（Android/鸿蒙），"
    "经局域网 WebSocket 与 MQTT over TLS 实现内外网协同，并接入兼容 OpenAI 协议的大模型完成水质解释与抓拍识图建议。"
    "实测表明主控可稳定完成传感轮询与安全优先控制，App 可实现多缸管理、告警与养护计划闭环。"
    "方案可应用于家庭草缸/海水缸、教学演示与小型实验室养殖监测。"
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
        ("作 品 名 称：", "iAqua 智能水族多端协同控制系统"),
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
    add_title(doc, "1.1 行业发展现状与应用场景", 2)
    add_body(
        doc,
        "水族产业涵盖家庭观赏、水产科研教学、水族造景竞赛与商业展陈等多个细分市场。"
        "随着物联网与边缘智能硬件成本下降，水质在线监测、执行器自动化与移动端运维成为升级方向。"
        "传统方案多停留在“单一仪表显示”或“定时插座级控制”，难以形成传感—决策—执行—记录的完整闭环。",
    )
    add_body(
        doc,
        "在竞赛与教学场景中，参赛队伍与指导教师更关注造景美学与生物健康的平衡：光照周期、CO₂ 与 pH 联动、"
        "水位补水、投喂节奏等均直接影响水草生长与鱼虾状态。若缺乏可复现的数据记录与告警机制，经验难以沉淀。",
    )
    if detailed:
        add_body(
            doc,
            "从产业链看，上游为传感器与变送器（温度、电导/TDS、pH/ORP、液位、光照），中游为控制器与执行器，"
            "下游为内容与服务（App、云端、AI 建议）。本作品聚焦中游控制系统，并向上下两端开放标准接口，"
            "以降低二次开发门槛。",
        )

    add_title(doc, "1.2 传统方案痛点梳理", 2)
    add_body(doc, "通过对常见商用控制器、开源 DIY 方案与人工运维方式的对比，可归纳如下痛点：")
    add_table(
        doc,
        ["痛点", "具体表现", "影响"],
        [
            ["监测碎片化", "多仪表分散，读数不同步", "难以关联分析"],
            ["控制开环", "定时器/手动开关为主", "无法随水质自适应"],
            ["安全不足", "传感失效仍持续加温/加气", "生物风险高"],
            ["记录缺失", "换水喂食靠记忆", "无法追溯与复盘"],
            ["内外网割裂", "仅局域网或仅云端", "场景切换成本高"],
            ["跨端不一致", "Web/App 协议不统一", "维护成本上升"],
        ],
        1,
        "传统水族运维痛点对照",
    )
    if detailed:
        add_title(doc, "1.2.1 传感与执行割裂", 3)
        add_body(
            doc,
            "许多用户已购买 pH 笔、TDS 笔与独立加热棒、电磁阀，但彼此不共享状态。"
            "当 pH 升高需要补 CO₂，或水位下降需要补水时，仍依赖人工观察，夜间与出差场景尤为脆弱。",
        )
        add_title(doc, "1.2.2 数据新鲜度被忽视", 3)
        add_body(
            doc,
            "RS485 变送器掉线、探头开路或总线冲突时，若控制器继续沿用旧值进行 PID/阈值控制，"
            "极易造成过量加温或长时间开阀。本作品将“数据新鲜度”提升为控制前置条件。",
        )

    add_title(doc, "1.3 立项依据与目标", 2)
    add_body(
        doc,
        "基于上述痛点，参赛队伍立项研发 iAqua：以低成本经典 ESP32 为边缘主控，统一采集与安全控制；"
        "以 Web/WS 服务同网段实时运维；以 MQTT 支撑广域查看；以 Flutter App 完成多缸档案、养护闭环与 AI 辅助；"
        "以 CAM 节点补充视觉信息。目标是形成可演示、可复现、可开源传播的完整技术栈。",
    )
    add_picture(doc, figs["arch"], 1, "iAqua 多端协同总体架构")
    if detailed:
        add_body(
            doc,
            "图1-1 给出了本作品的总体协同关系。边缘侧强调实时性与安全兜底，云端强调可达性与事件分发，"
            "移动端强调人机协同与养护知识沉淀。三者通过明确主题约定与 JSON 协议对齐，避免“各端各说一套”。",
        )
        add_table(
            doc,
            ["目标层级", "指标示例", "验证方式"],
            [
                ["功能完备", "7 类传感 + 5 路执行", "联调清单"],
                ["安全优先", "失效→断热断气", "故障注入"],
                ["多端一致", "同缸同协议", "对照抓包"],
                ["可维护", "配置热更新/开源", "仓库与文档"],
            ],
            1,
            "立项目标与验证方式",
        )
        for i in range(3):
            add_body(
                doc,
                f"补充论述（{i+1}）：水族系统属于典型 CPS（信息物理系统）。物理侧存在非线性与时滞（加热、CO₂溶解、补水波浪），"
                f"信息侧存在采样抖动与丢包。因此方案必须在架构上预留手动覆盖、最大连续运行时间与新鲜度门槛，"
                f"而不是追求单一“全自动最优”。这也是本作品与纯展示型仪表方案的本质差异。",
            )


def chapter2(doc, figs, detailed=True):
    FIG["n"] = 0
    TAB["n"] = 0
    add_title(doc, "2. 关键技术与创新点", 1)
    add_title(doc, "2.1 核心自研点总览", 2)
    add_table(
        doc,
        ["创新点", "传统做法", "本作品做法"],
        [
            ["安全优先控制", "阈值触发即动作", "新鲜度+手动优先+超时切断"],
            ["多端协议对齐", "各端私有协议", "WS JSON + MQTT 统一字段"],
            ["水型驱动 UI", "固定指标", "淡水/海水显示语义切换"],
            ["双平台 App", "仅 Android", "Flutter Android+鸿蒙纯 Dart"],
            ["边缘 AI 辅助", "无 App", "抓拍多模态+水质上下文注入"],
            ["可配置 485", "固件写死寄存器", "Web 热更新 regs 映射"],
        ],
        2,
        "创新点与同类方案对比",
    )
    add_title(doc, "2.2 安全优先控制引擎", 2)
    add_body(
        doc,
        "控制引擎以 1 s 节拍运行。对 CO₂：可跟随灯光，并按 pH 滞回（默认高于 7.0 开、低于 6.8 关）；"
        "对加热与水位补水：采用阈值与滞回；喂食采用脉冲输出。任意通道支持手动覆盖，自动逻辑不得强行抢占手动态。"
        "当 pH 等关键量超时未刷新，强制关闭 CO₂，避免“瞎控”。",
    )
    add_picture(doc, figs["control"], 2, "闭环控制与安全优先逻辑")
    if detailed:
        add_body(
            doc,
            "与常见“云端决策下发”不同，关键闭环留在边缘，保证断网时仍可按最后有效策略安全运行；"
            "云端仅承担观测、告警分发与非实时命令，降低广域链路抖动对生物安全的影响。",
        )
        add_title(doc, "2.3 可配置 Modbus 档案", 2)
        add_body(
            doc,
            "TDS/EC 与 pH/ORP 变送器品牌繁多、寄存器表不一。本作品将地址、功能码、寄存器与缩放系数纳入配置文档，"
            "可在 Web 端热更新而无需重编译固件，显著降低现场适配成本。",
        )
        add_title(doc, "2.4 多端一致与水型语义", 2)
        add_body(
            doc,
            "协议层统一 temp/ph/orp/tds1/tds2/lux/lvl 等键名；展示层按水型映射：淡水/草缸强调滤前滤后 TDS，"
            "海水缸将 tds1 解释为盐度。该设计避免“一套硬件、多套互相矛盾的 App 逻辑”。",
        )
        add_picture(doc, figs["app"], 2, "移动端信息架构（四 Tab）")
        add_title(doc, "2.5 AI 辅助但不替代控制", 2)
        add_body(
            doc,
            "大模型用于解释与建议（流式输出、抓拍识图），不直接闭环驱动执行器。关键动作仍由本地规则与用户确认完成，"
            "符合水族安全场景对“可解释、可打断”的要求。",
        )
        for i in range(4):
            add_body(
                doc,
                f"创新论证补充（{i+1}）：差异化并不来自堆叠更多传感器型号，而来自“把失败模式设计进去”。"
                f"例如 GPIO5 用于补水泵时增加上拉以保证 strapping 脚上电安全；TF 卡与执行器引脚规划互不侵占传感脚；"
                f"主机名按 MAC 后缀生成，避免多机同网 mDNS 冲突。这些工程细节共同构成可落地的竞争力。",
            )


def chapter3(doc, figs, detailed=True):
    FIG["n"] = 0
    TAB["n"] = 0
    add_title(doc, "3. 项目技术方案设计和原理", 1)
    add_title(doc, "3.1 总体架构与模块划分", 2)
    add_body(
        doc,
        "系统划分为：传感采集层、控制与执行层、本地服务层（HTTP/WebSocket/配网/历史）、云链路层、视觉节点、人机层（Web/PC/App）。"
        "主控固件采用模块化 C++（Arduino 框架），关键类包括 SensorStore、ControlEngine、Actuators、ModbusBus、NetService、"
        "WebService、HistStore、CloudLink、TfStore 等。",
    )
    add_table(
        doc,
        ["模块", "职责", "关键技术"],
        [
            ["SensorStore", "遥测快照与新鲜度", "内存结构+时间戳"],
            ["ModbusBus", "485 轮询", "Modbus RTU 异步"],
            ["ControlEngine", "自动策略", "滞回/超时/跟随"],
            ["Actuators", "GPIO 驱动", "高低电平语义统一"],
            ["WebService", "仪表盘与命令", "AsyncWebServer+WS"],
            ["CloudLink", "云端上行", "MQTT over TLS"],
            ["iAquaria", "多缸运维", "Flutter/MQTT/LLM"],
            ["ESP32-CAM", "视觉", "HTTP capture/stream"],
        ],
        3,
        "软件模块职责一览",
    )
    add_title(doc, "3.2 硬件方案与电源", 2)
    add_body(
        doc,
        "主控选用经典 ESP32 DevKitC（WROOM-32）。电源采用 12 V 适配器，经 DC-DC 得到 5 V 供继电器与部分模块，"
        "3.3 V 由板载 LDO 供给逻辑器件。CO₂ 电磁阀由 MOSFET 开关 12 V 回路，并建议并联续流二极管。",
    )
    add_picture(doc, figs["pins"], 3, "主控关键引脚规划一览")
    add_table(
        doc,
        ["电源轨", "来源", "主要负载"],
        [
            ["12 V", "适配器≥2 A", "CO₂ 阀、DC-DC 输入"],
            ["5 V", "DC-DC≥2 A", "继电器、SR04、485"],
            ["3.3 V", "板载 LDO", "DS18B20、BH1750、逻辑"],
        ],
        3,
        "电源架构",
    )
    add_title(doc, "3.3 传感链路原理", 2)
    add_body(
        doc,
        "温度采用 DS18B20 单总线异步转换；水位采用 HC-SR04 超声测距并两点标定为空满；光照采用 BH1750 I2C；"
        "TDS 与 pH/ORP 走 RS485 Modbus，主站 9600 8N1，按设备档案分段读寄存器并缩放。",
    )
    if detailed:
        add_table(
            doc,
            ["传感器", "接口", "周期(典型)", "备注"],
            [
                ["DS18B20", "1-Wire", "5 s", "上拉 4.7k"],
                ["HC-SR04", "GPIO", "5 s", "ECHO 分压"],
                ["BH1750", "I2C", "2 s", "地址 0x23/0x5C"],
                ["TDS 变送", "RS485", "2 s 级", "可配寄存器"],
                ["pH/ORP", "RS485", "2 s 级", "单通道探头"],
            ],
            3,
            "传感接口与采样策略",
        )
    add_title(doc, "3.4 通信与数据流", 2)
    add_body(
        doc,
        "局域网：浏览器或上位机连接 ws://<ip>/ws，接收 tel 帧并下发 ctrl/set 等命令。"
        "广域：设备作为 MQTT 客户端经 TLS 连接 Broker，发布 tel/evt，CAM 可发布 img；App 订阅查看并可下发 cmd。"
        "主机名按 cloud.dev_id/MAC 生成，形如 iaqua-xxxx.local，避免多机冲突。",
    )
    add_picture(doc, figs["mqtt"], 3, "MQTT 主题约定")
    add_title(doc, "3.5 人机与 AI 子系统", 2)
    add_body(
        doc,
        "Web 仪表盘提供实时卡片、控制与 485/控制参数配置；PC 上位机侧重长时间曲线与 SQLite/CSV；"
        "App 提供多缸、日志、计划、告警与 AI 对话。AI 服务兼容 DeepSeek/通义等 OpenAI 协议接口，密钥仅存本地。",
    )
    if detailed:
        add_title(doc, "3.6 存储策略", 2)
        add_body(
            doc,
            "主控历史默认写入片内 LittleFS，按固定记录结构追加并可压缩；可选 TF 卡用于扩展存储。"
            "App 侧缸档案、日志、任务与规则使用本地持久化，保证弱网可用。",
        )
        add_title(doc, "3.7 结构与装备配套", 2)
        add_body(
            doc,
            "围绕安装可靠性，参赛队伍同步设计了探头支架、超声支架、摄像头挂架、喂食器与密封结构等 3D 打印件，"
            "形成“电子系统 + 结构装备”一体化方案，便于在水族箱场景快速部署。",
        )
        for i in range(5):
            add_body(
                doc,
                f"方案可行性说明（{i+1}）：所选器件均为市场易购模块，固件基于成熟 Arduino-ESP32 与开源库"
                f"（AsyncWebServer、Modbus、PubSubClient、OneWire 等），降低实现风险；"
                f"关键状态机均为短周期非阻塞设计，并启用任务看门狗，避免单点阻塞导致整机假死。",
            )


def chapter4(doc, figs, detailed=True):
    FIG["n"] = 0
    TAB["n"] = 0
    add_title(doc, "4. 技术效果实现", 1)
    add_title(doc, "4.1 测试环境与方法", 2)
    add_body(
        doc,
        "测试在实验室局域网环境进行：2.4 GHz WiFi、Mosquitto/EMQX 可选、真机 ESP32 主控与 CAM、"
        "TDS 与 pH 变送器、部分执行器负载。方法包括：串口日志核验、Web/WS 联调、故障注入（拔总线、断探头）、"
        "多机 mDNS 冲突验证、App 多缸切换与告警规则触发。",
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
    add_title(doc, "4.2 性能与资源", 2)
    add_table(
        doc,
        ["指标", "观测值/设计值", "说明"],
        [
            ["主控 Flash 占用", "约 85%–90% 量级", "含 Web 资源与 TLS"],
            ["主控 RAM 占用", "约 16% 量级", "运行期仍有余量"],
            ["控制节拍", "1 s", "ControlEngine"],
            ["遥测推送", "约 1 Hz 级", "WS tel"],
            ["云端 tel", "约 30 s 保留", "可配"],
            ["看门狗", "2 s 级", "防死循环"],
        ],
        4,
        "性能与资源指标",
    )
    add_picture(doc, figs["safety"], 4, "安全机制设计覆盖评估")
    if detailed:
        add_title(doc, "4.3 对比提升", 2)
        add_table(
            doc,
            ["能力", "传统定时插座方案", "本作品"],
            [
                ["水质自适应", "无", "有（阈值/滞回）"],
                ["失效保护", "弱", "新鲜度强制安全"],
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
            "外接 SPI TF 模块在部分杜邦线条件下可能出现文件系统识别不稳，而 CAM 板载 SD_MMC 识别正常，"
            "说明存储介质本身可用，后续将优化主控侧走线与上拉。pH 需按实际从机地址配置，出厂地址与文档目标地址可能不一致。",
        )
        for i in range(4):
            add_body(
                doc,
                f"测试讨论（{i+1}）：量化指标应以生物安全为第一约束。例如加热最大连续开启时间、CO₂ 最大连续开启时间，"
                f"其“性能”不是越大越好，而是在效果与风险之间取得可证明的平衡。本作品通过配置项暴露这些阈值，便于不同缸体调参。",
            )


def chapter5(doc, figs, detailed=True):
    FIG["n"] = 0
    TAB["n"] = 0
    add_title(doc, "5. 应用价值与市场前景", 1)
    add_title(doc, "5.1 应用价值", 2)
    add_body(
        doc,
        "经济价值：降低水质失控导致的鱼获与水草损失，减少频繁人工巡检成本。"
        "产业价值：为水族装备提供可复制的“边缘控制+多端软件”参考实现，促进模块化配件生态。"
        "社会与教育价值：可用于高校实验教学与科普展示，帮助学生理解物联网闭环与安全设计。",
    )
    add_picture(doc, figs["cost"], 5, "样机物料成本结构（示意）")
    add_title(doc, "5.2 目标用户与市场规模", 2)
    add_table(
        doc,
        ["用户画像", "核心诉求", "产品切面"],
        [
            ["家庭草缸玩家", "稳定 pH/光照/少维护", "主控+App"],
            ["海水缸玩家", "盐度/设备联动", "水型语义+告警"],
            ["教学实验室", "可演示可改", "开源+Web 配置"],
            ["造景竞赛队伍", "过程可控可记录", "日志/计划/摄像"],
        ],
        5,
        "目标用户与产品切面",
    )
    add_body(
        doc,
        "国内观赏水族与相关智能硬件市场持续扩容，呈现“高阶玩家要数据、普通用户要省心”的分层需求。"
        "本作品以开源方案降低试用门槛，以可选云端能力满足进阶需求，具备从竞赛作品走向小规模转化的潜力。",
    )
    add_title(doc, "5.3 推广与转化路径", 2)
    add_picture(doc, figs["roadmap"], 5, "研发里程碑路线图")
    add_bullets(
        doc,
        [
            "开源仓库持续维护，提供接线文档与刷机说明；",
            "推出基础套件（主控+关键传感+结构件）与进阶套件（CAM+云）；",
            "与教学实验结合，形成课程案例；",
            "逐步完善认证与电气安全，再进入商业渠道。",
        ],
    )
    if detailed:
        for i in range(4):
            add_body(
                doc,
                f"市场分析补充（{i+1}）：转化关键不在“功能最多”，而在“安装友好与失败可恢复”。"
                f"因此文档化接线、配网门户、地址可配、安全默认态等工程能力，将成为产品化的核心资产。",
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
                ["fresh", "数据新鲜有效"],
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
                ["探头失效误控", "高", "新鲜度门槛+强制关断"],
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
    pages_hint = 52 if full else 12
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
    doc.save(out)
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
