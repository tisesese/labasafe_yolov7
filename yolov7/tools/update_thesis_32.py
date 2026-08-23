# -*- coding: utf-8 -*-
import zipfile
from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET


DOCS = [p for p in Path(".").glob("*.docx") if not p.name.startswith("~$")]
SRC_CANDIDATES = [p for p in DOCS if "3.3.1" in p.name]
SRC = sorted(SRC_CANDIDATES or DOCS, key=lambda p: p.stat().st_mtime)[-1]
OUT = Path("苏绍俊毕业论文_3.2算法改进更新.docx")

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


def make_paragraph(text="", align=None, bold=False, size=21, first_line=True):
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
        p.append(make_run(text, bold=bold, size=size))
    return p


def para_text(p):
    return "".join((t.text or "") for t in p.findall(".//" + w("t"))).strip()


SE_BLOCKS = [
    make_paragraph(
        "实验室安全检测场景中，不同检测目标的尺度、形态和纹理差异较为明显。人员目标通常具有较完整的轮廓和较大的空间尺度；开发板目标尺寸较小，表面纹理和边缘细节密集；火焰目标虽然颜色特征较突出，但形态变化大、边界不稳定，且容易受到灯光反射和背景颜色的影响。若仅依赖 YOLOv7 原始卷积特征进行检测，网络在复杂背景下容易将桌面纹理、线缆、反光区域等干扰信息与真实目标混淆，尤其会影响开发板等小目标的识别稳定性。为增强模型对关键通道特征的选择能力，本文在 YOLOv7 主干特征提取阶段引入 SE（Squeeze-and-Excitation）通道注意力机制。"
    ),
    make_paragraph(
        "SE 模块的核心思想是通过全局信息建模得到各通道的重要性权重，再利用该权重对原始特征图进行重标定。设输入特征图为 X∈R^{C×H×W}，其中 C、H、W 分别表示通道数、高度和宽度。首先通过全局平均池化对每一个通道进行压缩，得到通道描述向量 z，其第 c 个通道可表示为："
    ),
    make_paragraph("z_c = 1/(H×W) Σ_i Σ_j X_c(i,j)", align="center", first_line=False),
    make_paragraph(
        "随后，通道描述向量经过两层全连接映射和非线性激活，得到各通道的注意力权重 s："
    ),
    make_paragraph("s = sigmoid(W_2·ReLU(W_1·z))", align="center", first_line=False),
    make_paragraph(
        "其中，W_1 和 W_2 分别表示降维和升维映射参数，sigmoid 函数用于将通道权重限制在 0 到 1 之间。最后，SE 模块将权重 s 与原始特征图逐通道相乘，得到重标定后的输出特征："
    ),
    make_paragraph("X'_c = s_c · X_c", align="center", first_line=False),
    make_paragraph(
        "在具体实现中，本文没有改变 YOLOv7 的检测头结构和多尺度输出方式，而是在主干网络若干 ELAN 特征聚合阶段之后插入轻量级 SEBlock。该设计能够在不破坏原有特征传递路径和检测头索引关系的前提下，对不同语义层级的通道响应进行自适应增强。对于开发板等小目标，SE 模块有助于提升细粒度纹理通道的响应；对于火焰目标，则能够强化颜色、边缘和局部形态相关通道，从而提高复杂背景下的特征辨识能力。"
    ),
    make_paragraph(
        "需要注意的是，SE 模块只在网络结构中增加少量参数。本文实现中采用 reduction=16 的压缩比例，改进后的 SE 模型相较基线模型仅增加约 0.33M 参数，模型文件大小增加约 0.67 MB，属于轻量级结构增强。因此，该改进适合实验室边缘部署场景中对模型复杂度较敏感的应用需求。"
    ),
]


FOCAL_BLOCKS = [
    make_paragraph(
        "在实验室安全检测任务中，小目标和困难样本占有一定比例。例如，开发板在远距离画面中只占据较少像素，火焰目标又容易受到红色物体、灯光反射和曝光变化的干扰。传统 BCE 损失在训练过程中会同时计算大量易分类背景样本和少量困难前景样本的损失。当简单负样本数量远大于有效正样本时，模型参数更新容易被大量低价值样本主导，导致网络对小目标、遮挡目标以及边界模糊目标的学习不充分。"
    ),
    make_paragraph(
        "为缓解这一问题，本文在目标置信度分支和类别分类分支中引入 Focal Loss。Focal Loss 在 BCE 损失的基础上增加调制因子，使模型在训练时降低易分类样本的权重，并更加关注难分类样本。对二分类形式的预测，其基本表达式为："
    ),
    make_paragraph("FL(p_t) = -α_t(1-p_t)^γ log(p_t)", align="center", first_line=False),
    make_paragraph(
        "式中，p_t 表示模型对真实类别的预测概率，α_t 为类别平衡因子，用于调节正负样本之间的权重；γ 为聚焦参数，用于控制对易分类样本的抑制强度。当样本较容易被正确分类时，p_t 接近 1，调制因子 (1-p_t)^γ 接近 0，对应损失被明显削弱；当样本难以分类时，p_t 较小，调制因子保持较大，模型会在该样本上获得更强的梯度反馈。"
    ),
    make_paragraph(
        "结合本文数据集特点，训练中设置 α=0.25、γ=1.5。该参数组合在保持训练稳定性的同时，能够适度提高困难样本在损失函数中的贡献。与直接增大类别权重相比，Focal Loss 的优势在于其权重调节随预测难度动态变化，不会简单地固定放大某一类样本，而是更关注当前模型尚未学习充分的样本。"
    ),
    make_paragraph(
        "在 YOLOv7 原始损失结构中，边界框回归损失仍采用 CIoU Loss，用于优化预测框与真实框之间的位置、尺寸和长宽比关系；Focal Loss 主要作用于目标置信度损失和类别分类损失，用于改善前景背景区分和类别判别能力。因此，本文的损失函数改进并不是完全替换 YOLOv7 的联合损失，而是在保持原有定位损失机制不变的基础上，对分类与置信度分支进行困难样本重加权。改进后的联合损失可概括为："
    ),
    make_paragraph("L = L_CIoU + L_obj^Focal + L_cls^Focal", align="center", first_line=False),
    make_paragraph(
        "其中，L_CIoU 表示边界框回归损失，L_obj^Focal 表示经过 Focal Loss 调制后的目标置信度损失，L_cls^Focal 表示经过 Focal Loss 调制后的类别分类损失。通过该设计，模型能够在保持 YOLOv7 原有定位优势的同时，提高对开发板、火焰等困难目标的学习强度，为后续消融实验中验证损失函数改进的有效性提供基础。"
    ),
]


with zipfile.ZipFile(SRC, "r") as zin:
    document_xml = zin.read("word/document.xml")

root = ET.fromstring(document_xml)
body = root.find(w("body"))
children = list(body)


def find_heading(prefix):
    for idx, child in enumerate(children):
        if child.tag == w("p") and para_text(child).startswith(prefix):
            return idx
    raise RuntimeError(f"Heading not found: {prefix}")


h321 = find_heading("3.2.1 ")
h322 = find_heading("3.2.2 ")

for idx in range(h322 - 1, h321, -1):
    body.remove(children[idx])
for offset, block in enumerate(deepcopy(SE_BLOCKS)):
    body.insert(h321 + 1 + offset, block)

children = list(body)
h322 = find_heading("3.2.2 ")
h33 = find_heading("3.3 ")
for idx in range(h33 - 1, h322, -1):
    body.remove(children[idx])
for offset, block in enumerate(deepcopy(FOCAL_BLOCKS)):
    body.insert(h322 + 1 + offset, block)

for p in root.findall(".//" + w("p")):
    text = para_text(p)
    if text.startswith("3.2.2 损失函数改进"):
        runs = p.findall(".//" + w("t"))
        for t in runs:
            if t.text == "损失函数改进":
                t.text = "面向小目标的损失函数改进"

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
