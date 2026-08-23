# -*- coding: utf-8 -*-
import zipfile
from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET


DOCS = [p for p in Path(".").glob("*.docx") if not p.name.startswith("~$")]
SRC_CANDIDATES = [p for p in DOCS if "3.1.1改进更新" in p.name]
SRC = sorted(SRC_CANDIDATES or DOCS, key=lambda p: p.stat().st_mtime)[-1]
OUT = Path("苏绍俊毕业论文_3.3训练参数更新.docx")

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
ET.register_namespace("w", W_NS)


def w(tag):
    return f"{{{W_NS}}}{tag}"


def set_w_attr(el, key, val):
    el.set(w(key), str(val))


def make_run(text, size=21):
    r = ET.Element(w("r"))
    r_pr = ET.SubElement(r, w("rPr"))
    fonts = ET.SubElement(r_pr, w("rFonts"))
    set_w_attr(fonts, "ascii", "Times New Roman")
    set_w_attr(fonts, "hAnsi", "Times New Roman")
    set_w_attr(fonts, "eastAsia", "宋体")
    sz = ET.SubElement(r_pr, w("sz"))
    set_w_attr(sz, "val", size)
    t = ET.SubElement(r, w("t"))
    if text.startswith(" ") or text.endswith(" "):
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t.text = text
    return r


def make_paragraph(text, first_line=True):
    p = ET.Element(w("p"))
    p_pr = ET.SubElement(p, w("pPr"))
    if first_line:
        ind = ET.SubElement(p_pr, w("ind"))
        set_w_attr(ind, "firstLine", "420")
    spacing = ET.SubElement(p_pr, w("spacing"))
    set_w_attr(spacing, "after", "120")
    set_w_attr(spacing, "line", "360")
    set_w_attr(spacing, "lineRule", "auto")
    p.append(make_run(text))
    return p


def para_text(p):
    return "".join((t.text or "") for t in p.findall(".//" + w("t"))).strip()


SECTION_INTRO = make_paragraph(
    "在完成基线网络结构设计、数据集构建与改进模块实现后，需要采用统一的训练策略对各组模型进行权重迭代。为保证消融实验具有可比性，本文在四组实验中保持数据集划分、输入尺寸、训练轮数、优化器、学习率策略和主要损失权重一致，仅改变注意力模块和损失函数类型。本节首先说明数据集构建与增强方式，随后介绍训练参数、评价指标以及不同模型的实验结果。"
)

PARAM_BLOCKS = [
    make_paragraph(
        "模型训练在 Windows 环境下基于 PyTorch 和 CUDA 加速完成，初始权重采用 YOLOv7 在通用数据集上预训练得到的 yolov7.pt。使用预训练权重能够为模型提供较稳定的底层边缘、纹理和形状特征，减少小规模实验室数据集从零训练时可能出现的收敛不稳定问题。训练时将类别数设置为 3，分别对应 fire、person 和 board card 三类目标，并将输入图像统一缩放为 640×640。"
    ),
    make_paragraph(
        "为保证四组消融实验的公平性，Baseline、SE、Focal 和 SE+Focal 均采用相同的数据划分和训练参数。训练集、验证集和测试集分别包含 1252、300 和 254 张图像；训练轮数设置为 100 epoch，batch size 设置为 6。选择 batch size=6 主要是考虑到显卡显存限制，在保证训练能够稳定运行的同时尽量提高单次迭代的样本数量。所有实验均使用相同随机划分后的 clean 数据集，以避免数据分布差异对模型性能比较造成干扰。"
    ),
    make_paragraph(
        "优化器采用带动量的 SGD（Stochastic Gradient Descent）。初始学习率 lr0 设置为 0.01，最终学习率比例 lrf 设置为 0.1，并采用余弦退火策略对学习率进行动态衰减，使训练前期具有较大的参数更新幅度，后期逐渐减小学习率以获得更稳定的收敛结果。动量 momentum 设置为 0.937，用于累积历史梯度方向并加快收敛；权重衰减 weight_decay 设置为 0.0005，用于抑制模型参数过大，降低过拟合风险。"
    ),
    make_paragraph(
        "在训练初期设置 3 个 epoch 的 warmup 阶段，其中 warmup_momentum 设置为 0.8，warmup_bias_lr 设置为 0.1。Warmup 的作用是在训练初期逐步调整学习率和动量，避免预训练权重在刚开始迁移到实验室数据集时出现梯度震荡。对于目标检测损失权重，边界框回归损失权重 box 设置为 0.05，分类损失权重 cls 设置为 0.3，目标置信度损失权重 obj 设置为 0.7。该设置能够在保持定位精度的同时，使模型充分学习前景背景区分能力和三类目标的分类能力。"
    ),
    make_paragraph(
        "数据增强参数方面，训练阶段启用 Mosaic、MixUp、Copy-Paste、HSV 色彩扰动、随机旋转、平移、缩放、剪切、透视变换以及水平和垂直翻转等策略。其中 Mosaic 用于提升模型对多目标组合和小目标的学习频率，HSV 扰动用于增强模型对光照变化的鲁棒性，几何变换用于模拟摄像头角度和目标位置变化。需要说明的是，上述数据增强仅作用于训练集，验证集和测试集不进行随机增强，以保证评估结果能够反映模型在真实未增强图像上的检测能力。"
    ),
    make_paragraph(
        "在损失函数设置上，基线模型和 SE 模型使用 YOLOv7 默认的 BCE 损失；Focal 和 SE+Focal 模型在目标置信度分支和类别分支中引入 Focal Loss，并设置 α=0.25、γ=1.5。当使用 BCE 损失时，训练程序将 fl_gamma 强制置为 0，确保该组实验未引入 Focal Loss 的调制作用；当使用 Focal Loss 时，则启用上述 α 和 γ 参数。通过这种设置，可以保证四组实验之间的差异仅来自“是否引入 SE 注意力机制”和“是否使用 Focal Loss”，从而满足消融实验的控制变量要求。"
    ),
]


with zipfile.ZipFile(SRC, "r") as zin:
    document_xml = zin.read("word/document.xml")

root = ET.fromstring(document_xml)
body = root.find(w("body"))
children = list(body)


def find_body_heading(prefix):
    for idx, child in enumerate(children):
        if child.tag == w("p") and para_text(child).startswith(prefix) and idx > 150:
            return idx
    raise RuntimeError(f"Heading not found: {prefix}")


h33 = find_body_heading("3.3 ")
h331 = find_body_heading("3.3.1 ")
h332 = find_body_heading("3.3.2 ")

# Replace the 3.3 section lead paragraph only.
for idx in range(h331 - 1, h33, -1):
    body.remove(children[idx])
body.insert(h33 + 1, deepcopy(SECTION_INTRO))

children = list(body)
h332 = find_body_heading("3.3.2 ")

target_idx = None
for idx in range(h332 + 1, len(children)):
    text = para_text(children[idx])
    if text.startswith("为科学量化模型在测试集上的表现"):
        target_idx = idx
        break

if target_idx is None:
    raise RuntimeError("Metric paragraph not found after 3.3.2")

for idx in range(target_idx - 1, h332, -1):
    body.remove(children[idx])
for offset, block in enumerate(deepcopy(PARAM_BLOCKS)):
    body.insert(h332 + 1 + offset, block)

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
