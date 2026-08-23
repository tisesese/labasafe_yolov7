# -*- coding: utf-8 -*-
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


SRC = Path(sys.argv[1])
OUT = SRC.with_name(SRC.stem + "_检查修正.docx")

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
ET.register_namespace("w", W_NS)


def w(tag):
    return f"{{{W_NS}}}{tag}"


def para_text(p):
    return "".join((t.text or "") for t in p.findall(".//" + w("t"))).strip()


def set_para_text(p, text):
    p_pr = p.find(w("pPr"))
    for child in list(p):
        if child is not p_pr:
            p.remove(child)
    r = ET.SubElement(p, w("r"))
    r_pr = ET.SubElement(r, w("rPr"))
    fonts = ET.SubElement(r_pr, w("rFonts"))
    fonts.set(w("ascii"), "Times New Roman")
    fonts.set(w("hAnsi"), "Times New Roman")
    fonts.set(w("eastAsia"), "宋体")
    sz = ET.SubElement(r_pr, w("sz"))
    sz.set(w("val"), "21")
    t = ET.SubElement(r, w("t"))
    t.text = text


def replace_text(p, old, new):
    texts = p.findall(".//" + w("t"))
    for t in texts:
        if t.text and old in t.text:
            t.text = t.text.replace(old, new)


def has_drawing(p):
    return bool(p.findall(".//" + w("drawing")) or p.findall(".//" + w("pict")))


def remove_drawings_keep_text(p):
    for r in list(p.findall(w("r"))):
        if r.findall(".//" + w("drawing")) or r.findall(".//" + w("pict")):
            p.remove(r)


with zipfile.ZipFile(SRC, "r") as zin:
    root = ET.fromstring(zin.read("word/document.xml"))

body = root.find(w("body"))
children = list(body)

body_h31 = None
body_h32 = None
body_h332 = None
body_h34 = None
result_intro = None

for idx, child in enumerate(children):
    if child.tag != w("p"):
        continue
    text = para_text(child)
    if idx > 150 and text.startswith("3.1 "):
        body_h31 = idx
    if idx > 150 and text.startswith("3.2 "):
        body_h32 = idx
    if idx > 150 and text.startswith("3.3.2 "):
        body_h332 = idx
    if idx > 150 and text.startswith("3.4 "):
        body_h34 = idx
    if idx > 150 and text.startswith("为验证注意力机制与损失函数改进"):
        result_intro = idx

if None in (body_h31, body_h32, body_h332, body_h34, result_intro):
    raise RuntimeError("Could not locate expected body ranges")

to_remove = []

for idx, child in enumerate(children):
    if child.tag != w("p"):
        continue
    text = para_text(child)

    # Fix section heading and static TOC text.
    if text.startswith("3.3.1 数据集构建与分析"):
        set_para_text(child, "3.1.2 数据集构建与分析")
    if text.startswith("3.2.2 损失函数改进"):
        replace_text(child, "损失函数改进", "面向小目标的损失函数改进")

    # Remove irrelevant Type-c screenshots/captions that leaked into Chapter 3.
    if body_h31 < idx < body_h34 and "Type-c接口登录" in text:
        to_remove.append(child)
        continue

    # Remove blank image paragraphs in the same leaked-image regions.
    if has_drawing(child) and not text:
        if (body_h31 < idx < body_h32) or (body_h332 < idx < result_intro):
            to_remove.append(child)
            continue

    # One leaked image is anchored inside the NMS paragraph; keep the paragraph text.
    if body_h31 < idx < body_h32 and text.startswith("网络得到候选框预测后"):
        remove_drawings_keep_text(child)

    # Fill missing Focal Loss parameter value.
    if text.startswith("结合本文数据集特点，训练中设置 该参数组合"):
        set_para_text(
            child,
            "结合本文数据集特点，训练中设置 α=0.25、γ=1.5。该参数组合在保持训练稳定性的同时，能够适度提高困难样本在损失函数中的贡献。与直接增大类别权重相比，Focal Loss 的优势在于其权重调节随预测难度动态变化，不会简单地固定放大某一类样本，而是更关注当前模型尚未学习充分的样本。"
        )

    # Improve one awkward sentence in 3.3.1.
    if text.startswith("（2）数据集与类别参数。 实验使用数据集有训练集"):
        set_para_text(
            child,
            "（2）数据集与类别参数。 实验使用清洗后的实验室安全检测数据集，训练集、验证集和测试集分别包含 1252、300 和 254 张图像。数据配置文件中 nc=3，表示模型需要识别 3 个类别，类别名称分别为 fire、person 和 board card。训练、验证和测试均使用相同的数据划分，避免因数据分布变化影响不同模型之间的横向比较。"
        )

    # Fix table numbering after the dataset table.
    if idx > body_h332:
        if text.startswith("表3-1  消融实验验证集结果对比"):
            set_para_text(child, "表3-2  消融实验验证集结果对比")
        elif text.startswith("由表3-1可知"):
            replace_text(child, "由表3-1可知", "由表3-2可知")
        elif text.startswith("表3-2  独立测试集检测结果对比"):
            set_para_text(child, "表3-3  独立测试集检测结果对比")
        elif "结果如表3-2所示" in text:
            replace_text(child, "结果如表3-2所示", "结果如表3-3所示")
        elif text.startswith("表3-3  模型大小与参数量对比"):
            set_para_text(child, "表3-4  模型大小与参数量对比")
        elif text.startswith("由表3-3可知"):
            replace_text(child, "由表3-3可知", "由表3-4可知")

    # Fix duplicated word in later heading.
    if text.startswith("4.1.3 离线模型编译与与预处理"):
        set_para_text(child, "4.1.3 离线模型编译与预处理")

for child in to_remove:
    if child in list(body):
        body.remove(child)

if OUT.exists():
    OUT.unlink()

with zipfile.ZipFile(SRC, "r") as zin, zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        if item.filename == "word/document.xml":
            zout.writestr(item, ET.tostring(root, encoding="utf-8", xml_declaration=True))
        else:
            zout.writestr(item, zin.read(item.filename))

print(f"output={OUT.resolve()}")
