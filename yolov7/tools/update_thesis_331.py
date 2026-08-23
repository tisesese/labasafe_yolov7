# -*- coding: utf-8 -*-
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


SRC = Path("苏绍俊毕业论文_实验结果更新.docx")
if not SRC.exists():
    SRC = Path("thesis_experiment_update.docx")
OUT = Path("苏绍俊毕业论文_3.3.1数据集更新.docx")

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
ET.register_namespace("w", W_NS)


def w(tag):
    return f"{{{W_NS}}}{tag}"


def set_w_attr(el, key, val):
    el.set(w(key), str(val))


def make_run(text, bold=False, size=21):
    r = ET.Element(w("r"))
    r_pr = ET.SubElement(r, w("rPr"))
    fonts = ET.SubElement(r_pr, w("rFonts"))
    set_w_attr(fonts, "ascii", "Times New Roman")
    set_w_attr(fonts, "eastAsia", "宋体")
    if bold:
        ET.SubElement(r_pr, w("b"))
    sz = ET.SubElement(r_pr, w("sz"))
    set_w_attr(sz, "val", size)
    t = ET.SubElement(r, w("t"))
    if text.startswith(" ") or text.endswith(" "):
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t.text = text
    return r


def make_paragraph(text="", align=None, bold=False, size=21):
    p = ET.Element(w("p"))
    p_pr = ET.SubElement(p, w("pPr"))
    if align:
        jc = ET.SubElement(p_pr, w("jc"))
        set_w_attr(jc, "val", align)
    spacing = ET.SubElement(p_pr, w("spacing"))
    set_w_attr(spacing, "after", "120")
    set_w_attr(spacing, "line", "360")
    set_w_attr(spacing, "lineRule", "auto")
    if text:
        p.append(make_run(text, bold=bold, size=size))
    return p


def make_cell(text, width, bold=False):
    tc = ET.Element(w("tc"))
    tc_pr = ET.SubElement(tc, w("tcPr"))
    tc_w = ET.SubElement(tc_pr, w("tcW"))
    set_w_attr(tc_w, "w", width)
    set_w_attr(tc_w, "type", "dxa")
    v_align = ET.SubElement(tc_pr, w("vAlign"))
    set_w_attr(v_align, "val", "center")
    mar = ET.SubElement(tc_pr, w("tcMar"))
    for side in ["top", "left", "bottom", "right"]:
        m = ET.SubElement(mar, w(side))
        set_w_attr(m, "w", "80")
        set_w_attr(m, "type", "dxa")
    tc.append(make_paragraph(str(text), align="center", bold=bold, size=18))
    return tc


def make_table(rows, widths):
    tbl = ET.Element(w("tbl"))
    tbl_pr = ET.SubElement(tbl, w("tblPr"))
    tbl_w = ET.SubElement(tbl_pr, w("tblW"))
    set_w_attr(tbl_w, "w", "0")
    set_w_attr(tbl_w, "type", "auto")
    borders = ET.SubElement(tbl_pr, w("tblBorders"))
    for side in ["top", "left", "bottom", "right", "insideH", "insideV"]:
        border = ET.SubElement(borders, w(side))
        set_w_attr(border, "val", "single")
        set_w_attr(border, "sz", "4")
        set_w_attr(border, "space", "0")
        set_w_attr(border, "color", "808080")
    tbl_grid = ET.SubElement(tbl, w("tblGrid"))
    for width in widths:
        col = ET.SubElement(tbl_grid, w("gridCol"))
        set_w_attr(col, "w", width)
    for row_i, row in enumerate(rows):
        tr = ET.SubElement(tbl, w("tr"))
        if row_i == 0:
            tr_pr = ET.SubElement(tr, w("trPr"))
            ET.SubElement(tr_pr, w("tblHeader"))
        for cell, width in zip(row, widths):
            tr.append(make_cell(cell, width, bold=(row_i == 0)))
    return tbl


def para_text(p):
    return "".join((t.text or "") for t in p.findall(".//" + w("t"))).strip()


NEW_BLOCKS = [
    make_paragraph(
        "深度学习目标检测模型的性能高度依赖数据集质量。针对实验室安全监控场景中“火焰、人员、开发板”三类目标，本文采用实地采集与公开数据筛选相结合的方式构建训练数据。其中，人员和开发板样本主要来自实验室摄像头在不同拍摄角度、距离和光照条件下采集的视频帧；火焰样本则在公开火灾图像数据的基础上进行筛选，优先保留室内场景、光照复杂场景和形态变化较明显的火焰图像。所有图像均使用 LabelImg 工具进行人工标注，并统一转换为 YOLO 格式，即每个目标以“类别编号、中心点横坐标、中心点纵坐标、宽度、高度”的归一化形式保存。"
    ),
    make_paragraph(
        "在初始数据整理过程中发现，直接对视频抽帧图像进行随机划分会使相邻帧同时出现在训练集和验证集或测试集中，导致评估结果偏高，难以真实反映模型的泛化能力。为避免这种数据泄漏问题，本文首先对原始图像与标签进行一致性检查，仅保留图像和同名标注文件同时存在的有效样本；随后基于图像哈希值去除重复图像，并舍弃无对应图像的冗余标签文件。清洗后共保留 1806 张有效图像，包含 3927 个目标实例。"
    ),
    make_paragraph(
        "在数据集划分阶段，本文未采用简单随机划分，而是根据文件名前缀与帧编号将连续图像划分为若干时间片段，再以片段为单位分配到训练集、验证集和测试集。该方法能够降低相邻帧跨集合出现的概率，使验证集和测试集更接近真实未知场景。最终得到的数据集分布如表3-1所示。"
    ),
    make_paragraph("表3-1  数据集划分与类别分布", align="center", bold=True),
    make_table(
        [
            ["数据集", "图像数", "目标框总数", "火焰", "人员", "开发板"],
            ["训练集", "1252", "2304", "665", "891", "748"],
            ["验证集", "300", "951", "180", "241", "530"],
            ["测试集", "254", "672", "134", "185", "353"],
            ["合计", "1806", "3927", "979", "1317", "1631"],
        ],
        [1200, 1000, 1300, 1000, 1000, 1100],
    ),
    make_paragraph(
        "从表3-1可以看出，三个数据子集均覆盖了本文关注的三类目标，其中开发板目标数量相对较多，但其在图像中的尺度通常较小，且容易与桌面电子元器件、线缆和背景纹理混淆；火焰目标形态变化较大，颜色和边缘特征受光照影响明显；人员目标尺度跨度较大，既包括近距离完整人体，也包括远距离或局部遮挡人体。因此，该数据集能够覆盖实验室安全监控系统中较常见的检测难点。"
    ),
    make_paragraph(
        "为进一步提升模型对小目标、遮挡目标和复杂背景的适应能力，训练阶段引入了多种数据增强策略。首先使用 Mosaic 增强将多张图像随机缩放、裁剪并拼接为一张训练图像，从而增加背景组合方式并提高模型对小目标的学习频率；其次使用 HSV 色彩扰动、随机旋转、平移、缩放、剪切和轻微透视变换，增强模型对光照变化和摄像头视角变化的鲁棒性；同时配合水平翻转、垂直翻转、MixUp 和 Copy-Paste 等增强方式，扩展目标出现位置和上下文组合。通过上述处理，模型在训练过程中能够接触到更加丰富的目标尺度、空间布局和背景变化，从而提高其在实际实验室场景中的泛化能力。"
    ),
]

CAPTION_REPLACEMENTS = {
    "表3-1  消融实验验证集结果对比": "表3-2  消融实验验证集结果对比",
    "由表3-1可知": "由表3-2可知",
    "表3-2  独立测试集检测结果对比": "表3-3  独立测试集检测结果对比",
    "结果如表3-2所示": "结果如表3-3所示",
    "表3-3  模型大小与参数量对比": "表3-4  模型大小与参数量对比",
    "由表3-3可知": "由表3-4可知",
}


with zipfile.ZipFile(SRC, "r") as zin:
    document_xml = zin.read("word/document.xml")

root = ET.fromstring(document_xml)
body = root.find(w("body"))
children = list(body)

start = end = None
for idx, child in enumerate(children):
    if child.tag != w("p"):
        continue
    text = para_text(child)
    if text.startswith("3.3.1 "):
        start = idx + 1
    elif start is not None and text.startswith("3.3.2 "):
        end = idx
        break

if start is None or end is None or end <= start:
    raise RuntimeError("Could not locate 3.3.1 body range")

for idx in range(end - 1, start - 1, -1):
    body.remove(children[idx])

for offset, block in enumerate(NEW_BLOCKS):
    body.insert(start + offset, block)

for text_node in root.findall(".//" + w("t")):
    if text_node.text:
        for old, new in CAPTION_REPLACEMENTS.items():
            text_node.text = text_node.text.replace(old, new)

if OUT.exists():
    OUT.unlink()

with zipfile.ZipFile(SRC, "r") as zin, zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        if item.filename == "word/document.xml":
            zout.writestr(item, ET.tostring(root, encoding="utf-8", xml_declaration=True))
        else:
            zout.writestr(item, zin.read(item.filename))

print(OUT.resolve())
