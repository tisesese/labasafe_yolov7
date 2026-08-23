# -*- coding: utf-8 -*-
import zipfile
from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET


DOCS = [p for p in Path(".").glob("*.docx") if not p.name.startswith("~$")]
SRC_CANDIDATES = [p for p in DOCS if "3.2算法改进更新" in p.name]
SRC = sorted(SRC_CANDIDATES or DOCS, key=lambda p: p.stat().st_mtime)[-1]
OUT = Path("苏绍俊毕业论文_3.1.1改进更新.docx")

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
    set_w_attr(fonts, "hAnsi", "Times New Roman")
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


def make_paragraph(text="", align=None, first_line=True):
    p = ET.Element(w("p"))
    p_pr = ET.SubElement(p, w("pPr"))
    if align:
        jc = ET.SubElement(p_pr, w("jc"))
        set_w_attr(jc, "val", align)
    if first_line and not align:
        ind = ET.SubElement(p_pr, w("ind"))
        set_w_attr(ind, "firstLine", "420")
    spacing = ET.SubElement(p_pr, w("spacing"))
    set_w_attr(spacing, "after", "120")
    set_w_attr(spacing, "line", "360")
    set_w_attr(spacing, "lineRule", "auto")
    if text:
        p.append(make_run(text))
    return p


def para_text(p):
    return "".join((t.text or "") for t in p.findall(".//" + w("t"))).strip()


NEW_BLOCKS = [
    make_paragraph(
        "YOLOv7 是一种典型的单阶段目标检测算法，其整体流程可以概括为“输入预处理—主干特征提取—多尺度特征融合—检测头预测—后处理筛选”。与两阶段检测算法相比，YOLO 系列不需要先生成候选区域，而是直接在不同尺度的特征图上进行边界框回归、目标置信度预测和类别预测，因此具有较高的推理速度，适合实验室安全监控这类对实时性有一定要求的应用场景。本文以 YOLOv7 为基线网络，并根据实验室场景中火焰、人员和开发板三类目标的检测需求进行后续改进。"
    ),
    make_paragraph(
        "在输入端，采集到的图像首先被缩放并填充到统一尺寸，随后进行归一化处理，以保证不同分辨率图像能够以一致的形式输入网络。YOLOv7 在检测阶段采用多尺度预测思想，网络最终输出步长分别为 8、16 和 32 的三组特征图。其中，步长较小的特征图保留了更多空间细节，适合检测开发板等小目标；步长较大的特征图具有更强的语义表达能力，适合检测人员等尺度较大的目标。"
    ),
    make_paragraph(
        "在主干网络（Backbone）部分，YOLOv7 采用扩展高效层聚合网络 E-ELAN（Extended Efficient Layer Aggregation Network）进行特征提取。E-ELAN 通过多分支卷积、特征拼接和通道聚合的方式扩展网络宽度，使不同层级的特征能够在较短的梯度路径中充分交互。该结构既能够提升深层语义特征的表达能力，又能避免单纯加深网络带来的梯度传播困难和计算量过大问题。对于实验室场景而言，E-ELAN 有助于同时提取火焰的颜色边缘信息、人员的轮廓信息以及开发板的局部纹理信息。"
    ),
    make_paragraph(
        "在下采样过程中，YOLOv7 使用卷积和最大池化等模块逐步扩大感受野，使网络能够从局部纹理特征过渡到高层语义特征。主干末端还引入 SPPCSPC 结构，通过不同尺度的池化操作进一步聚合上下文信息，增强网络对复杂背景的建模能力。实验室画面中常出现桌面、线缆、仪器外壳和反光区域等干扰因素，较大的感受野有助于模型结合上下文判断目标是否真实存在，从而减少局部纹理相似造成的误检。"
    ),
    make_paragraph(
        "在特征融合阶段（Neck），YOLOv7 采用类似 PAFPN 的路径聚合结构，将高层语义信息与低层定位信息进行双向融合。自顶向下路径能够把深层语义信息传递到高分辨率特征图中，提高小目标类别判别能力；自底向上路径则进一步将低层边缘和位置信息传递到深层特征图中，增强大目标定位能力。由于本文数据集中同时存在人员这类大尺度目标和开发板这类小尺度目标，多尺度特征融合对于提高整体检测稳定性具有重要作用。"
    ),
    make_paragraph(
        "在检测头（Head）部分，YOLOv7 通过 RepConv 模块对融合后的三组特征图进行进一步处理，并由 IDetect 检测层完成最终预测。对于每一个候选框，网络输出边界框位置、目标置信度以及类别概率。其中边界框位置用于描述目标中心点坐标和宽高信息，目标置信度表示该候选框中存在目标的概率，类别概率表示目标分别属于 fire、person 和 board card 三类的条件概率。对于第 k 个类别，其最终检测置信度可表示为："
    ),
    make_paragraph("Score_k = P(object) × P(class_k | object)", align="center", first_line=False),
    make_paragraph(
        "网络得到候选框预测后，还需要通过置信度阈值过滤和非极大值抑制（Non-Maximum Suppression, NMS）去除重复框。NMS 根据候选框置信度和交并比关系保留最能代表目标位置的检测框，从而得到最终检测结果。对于实验室安全检测任务而言，合理的后处理能够减少同一火焰或同一开发板被多次检测的问题，使输出结果更清晰、稳定。"
    ),
    make_paragraph(
        "综上，YOLOv7 通过 E-ELAN 主干网络、多尺度特征融合结构和解耦式多尺度检测头，在检测精度与推理速度之间取得了较好的平衡。但在实验室实际场景中，仍然存在小目标细节弱、背景干扰多、困难样本比例较高等问题。因此，本文在保留 YOLOv7 基线结构优势的基础上，进一步从特征增强和损失函数优化两个方面进行改进，为后续引入 SE 注意力机制和 Focal Loss 奠定基础。"
    ),
]


with zipfile.ZipFile(SRC, "r") as zin:
    document_xml = zin.read("word/document.xml")

root = ET.fromstring(document_xml)
body = root.find(w("body"))
children = list(body)


def find_body_heading(prefix):
    for idx, child in enumerate(children):
        if child.tag == w("p") and para_text(child).startswith(prefix):
            # Skip table-of-contents entries near the beginning of the document.
            if idx > 150:
                return idx
    raise RuntimeError(f"Heading not found: {prefix}")


h311 = find_body_heading("3.1.1 ")
h312 = find_body_heading("3.1.2 ")

for idx in range(h312 - 1, h311, -1):
    body.remove(children[idx])
for offset, block in enumerate(deepcopy(NEW_BLOCKS)):
    body.insert(h311 + 1 + offset, block)

if OUT.exists():
    OUT.unlink()

with zipfile.ZipFile(SRC, "r") as zin, zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        if item.filename == "word/document.xml":
            zout.writestr(item, ET.tostring(root, encoding="utf-8", xml_declaration=True))
        else:
            zout.writestr(item, zin.read(item.filename))

print(f"source={SRC.resolve()}")
print(f"output={OUT.resolve()}")
