# -*- coding: utf-8 -*-
import sys
import zipfile
from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET


SRC = Path(sys.argv[1])
OUT = SRC.with_name(SRC.stem + "_3.3优化版.docx")

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
ET.register_namespace("w", W_NS)


def w(tag):
    return f"{{{W_NS}}}{tag}"


def set_w_attr(el, key, val):
    el.set(w(key), str(val))


def para_text(p):
    return "".join((t.text or "") for t in p.findall(".//" + w("t"))).strip()


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


def set_para_text(p, text):
    p_pr = p.find(w("pPr"))
    for child in list(p):
        if child is not p_pr:
            p.remove(child)
    p.append(make_run(text))


def replace_text(p, old, new):
    for t in p.findall(".//" + w("t")):
        if t.text and old in t.text:
            t.text = t.text.replace(old, new)


def has_drawing(p):
    return bool(p.findall(".//" + w("drawing")) or p.findall(".//" + w("pict")))


def remove_drawings_keep_text(p):
    for r in list(p.findall(w("r"))):
        if r.findall(".//" + w("drawing")) or r.findall(".//" + w("pict")):
            p.remove(r)


PARAM_BLOCKS = [
    make_paragraph(
        "为验证 SE 注意力机制与 Focal Loss 对实验室安全检测任务的影响，本文设置四组实验进行对比，分别为原始 YOLOv7 基线模型、引入 SE 注意力机制的模型、采用 Focal Loss 的模型，以及同时引入 SE 与 Focal Loss 的组合模型。四组实验使用相同的数据划分、输入尺寸和训练轮数，仅改变注意力模块和损失函数设置，以保证实验结论具有可比性。"
    ),
    make_paragraph(
        "训练过程基于 PyTorch 与 CUDA 环境完成，使用单张 GPU 进行计算，初始权重采用 YOLOv7 官方预训练权重 yolov7.pt。由于本文数据集规模相对有限，使用预训练权重可以利用通用目标检测任务中已经学习到的边缘、纹理和形状特征，使模型在较短训练轮数内稳定收敛。数据配置中类别数设置为 nc=3，对应 fire、person 和 board card 三类目标；训练集、验证集和测试集分别包含 1252、300 和 254 张图像。"
    ),
    make_paragraph(
        "输入图像统一缩放为 640×640，训练轮数设置为 100 epoch，batch size 设置为 6。该输入尺寸能够兼顾小目标检测效果和显存占用，batch size 的取值则主要受单卡显存限制影响。优化器采用带动量的 SGD，初始学习率 lr0=0.01，动量 momentum=0.937，权重衰减 weight_decay=0.0005，并配合余弦退火策略调整学习率。训练前 3 个 epoch 设置为 warmup 阶段，用于降低训练初期梯度波动，使模型由预训练权重平滑迁移到本文数据集。"
    ),
    make_paragraph(
        "损失函数权重保持 YOLOv7 训练配置中的主要设置，其中边界框损失权重 box=0.05，目标置信度损失权重 obj=0.7，分类损失权重 cls=0.3。对于采用 Focal Loss 的实验，设置 fl_alpha=0.25、fl_gamma=1.5，用于降低易分类样本对总损失的主导作用，使模型更加关注小目标和困难样本；对于 BCE 对照组，则不启用 Focal Loss 的调制项。训练阶段同时使用 Mosaic、MixUp、Copy-Paste、HSV 色彩扰动和随机几何变换等数据增强方式，以提高模型对光照变化、目标尺度变化和背景干扰的适应能力。"
    ),
    make_paragraph(
        "模型性能主要通过 Precision、Recall、mAP@0.5 和 mAP@0.5:0.95 进行评价。其中 Precision 反映预测结果中的误检情况，Recall 反映真实目标中的漏检情况；mAP@0.5 表示在 IoU 阈值为 0.5 时的平均检测精度，主要衡量目标是否能够被正确检出；mAP@0.5:0.95 则在更严格的 IoU 条件下综合评价定位质量，因此更适合分析模型边界框回归能力的差异。"
    ),
]

INTRO_332 = (
    "在上述统一训练设置下，本文对四组模型进行训练与评估。消融实验的目的并不是单纯追求某一项指标的最高值，而是观察 SE 注意力机制和 Focal Loss 分别对特征表达、困难样本学习以及定位质量的影响。四组模型均在相同训练集上训练，并分别在验证集和独立测试集上进行评价，以减少偶然数据划分对结论的影响。"
)

ANALYSIS_VAL = (
    "由表3-2可知，四组模型在 mAP@0.5 上均保持较高水平，说明基线 YOLOv7 已经能够较稳定地完成实验室场景中的三类目标检测。相比 mAP@0.5，mAP@0.5:0.95 对预测框位置更加敏感，因此更能反映模型定位质量。基线模型的 mAP@0.5:0.95 为 0.5377，引入 SE 后提升至 0.6195，采用 Focal Loss 后提升至 0.6147，二者结合后达到 0.6614。该结果说明，SE 模块能够增强关键通道特征表达，Focal Loss 能够缓解困难样本学习不足的问题，两者在严格 IoU 条件下对定位性能具有一定促进作用。"
)

ANALYSIS_TEST = (
    "为进一步检验模型泛化能力，本文使用独立测试集对各模型的 best.pt 权重进行评估，结果如表3-3所示。可以看出，四组模型在测试集上均保持了较高检测性能，说明模型对实验室场景具有较好的适应能力。与验证集相比，测试集上各改进模型与基线模型之间的差距较小，说明当前测试集规模下改进方法并未形成绝对优势。因此，本文将实验结论表述为：SE 注意力机制和 Focal Loss 对模型定位质量和训练稳定性具有一定改善作用，但提升幅度受数据规模和测试集分布影响。"
)

ANALYSIS_SIZE = (
    "由表3-4可知，Focal Loss 只作用于训练阶段，不改变模型网络结构，因此模型大小和参数量均与基线模型保持一致。引入 SE 注意力机制后，模型参数量由 37,207,344 增加至 37,532,552，增加 325,208 个参数，增幅约为 0.87%；模型大小由 74.82 MB 增加至 75.49 MB，仅增加约 0.67 MB。由此可见，SE 模块属于轻量级结构改进，在增加较少模型复杂度的前提下，能够带来一定的验证集定位性能提升。"
)

ANALYSIS_FIG = (
    "图3-1展示了四组模型在 Precision、Recall、mAP@0.5 和 mAP@0.5:0.95 上的对比情况。可以看出，各模型在 mAP@0.5 上差异较小，而在 mAP@0.5:0.95 上差异更为明显，说明改进方法主要影响预测框的精细定位能力。图3-2展示了验证阶段损失对比，采用 Focal Loss 的模型在目标置信度损失和分类损失上更低，这与其降低易分类样本权重、强调困难样本学习的机制一致。图3-3进一步表明，四组模型在宽松 IoU 阈值下均具有较好的检出能力，因此后续分析更应关注严格 IoU 指标、召回率和模型复杂度之间的综合平衡。"
)


with zipfile.ZipFile(SRC, "r") as zin:
    root = ET.fromstring(zin.read("word/document.xml"))

body = root.find(w("body"))
children = list(body)

body_h31 = body_h32 = body_h33 = h331 = h332 = body_h34 = None
result_intro = None
for idx, child in enumerate(children):
    if child.tag != w("p"):
        continue
    text = para_text(child)
    if idx > 150 and text.startswith("3.1 "):
        body_h31 = idx
    elif idx > 150 and text.startswith("3.2 "):
        body_h32 = idx
    elif idx > 150 and text.startswith("3.3 "):
        body_h33 = idx
    elif idx > 150 and text.startswith("3.3.1 "):
        h331 = idx
    elif idx > 150 and text.startswith("3.3.2 训练结果"):
        h332 = idx
    elif idx > 150 and text.startswith("3.4 "):
        body_h34 = idx
    if idx > 150 and text.startswith("为验证注意力机制与损失函数改进"):
        result_intro = idx

if None in (body_h31, body_h32, body_h33, h331, h332, body_h34):
    raise RuntimeError("Could not locate expected Chapter 3 headings")

# Keep static TOC in sync with body headings.
for child in children:
    if child.tag != w("p"):
        continue
    text = para_text(child)
    if text.startswith("3.3.2 数据集构建与分析"):
        set_para_text(child, "3.1.2 数据集构建与分析")
    if text.startswith("3.2.2 损失函数改进"):
        replace_text(child, "损失函数改进", "面向小目标的损失函数改进")

# Fix misplaced body heading if present.
for child in children:
    if child.tag == w("p") and para_text(child).startswith("3.3.2 数据集构建与分析"):
        set_para_text(child, "3.1.2 数据集构建与分析")

# Replace 3.3.1 content.
for idx in range(h332 - 1, h331, -1):
    body.remove(children[idx])
for offset, block in enumerate(deepcopy(PARAM_BLOCKS)):
    body.insert(h331 + 1 + offset, block)

children = list(body)
body_h31 = body_h32 = h332 = body_h34 = result_intro = None
for idx, child in enumerate(children):
    if child.tag != w("p"):
        continue
    text = para_text(child)
    if idx > 150 and text.startswith("3.1 "):
        body_h31 = idx
    elif idx > 150 and text.startswith("3.2 "):
        body_h32 = idx
    elif idx > 150 and text.startswith("3.3.2 训练结果"):
        h332 = idx
    elif idx > 150 and text.startswith("3.4 "):
        body_h34 = idx
    if idx > 150 and text.startswith("为验证注意力机制与损失函数改进"):
        result_intro = idx

# Remove leaked Type-c images/captions in Chapter 3, and keep text where an image is anchored in a paragraph.
to_remove = []
for idx, child in enumerate(children):
    if child.tag != w("p"):
        continue
    text = para_text(child)
    if body_h31 < idx < body_h34 and "Type-c接口登录" in text:
        to_remove.append(child)
    elif body_h31 < idx < body_h32 and text.startswith("网络得到候选框预测后"):
        remove_drawings_keep_text(child)
    elif has_drawing(child) and not text and ((body_h31 < idx < body_h32) or (h332 < idx < (result_intro or h332 + 10))):
        to_remove.append(child)

for child in to_remove:
    if child in list(body):
        body.remove(child)

children = list(body)

# Rewrite 3.3.2 analysis text and fix table numbers/references.
for idx, child in enumerate(children):
    if child.tag != w("p"):
        continue
    text = para_text(child)
    if text.startswith("为验证注意力机制与损失函数改进"):
        set_para_text(child, INTRO_332)
    elif text.startswith("表3-1  消融实验验证集结果对比"):
        set_para_text(child, "表3-2  消融实验验证集结果对比")
    elif text.startswith("由表3-1可知") or text.startswith("由表3-2可知，四组模型在 mAP@0.5"):
        set_para_text(child, ANALYSIS_VAL)
    elif text.startswith("表3-2  独立测试集检测结果对比"):
        set_para_text(child, "表3-3  独立测试集检测结果对比")
    elif text.startswith("为进一步检验模型泛化能力"):
        set_para_text(child, ANALYSIS_TEST)
    elif text.startswith("表3-3  模型大小与参数量对比"):
        set_para_text(child, "表3-4  模型大小与参数量对比")
    elif text.startswith("由表3-3可知") or text.startswith("由表3-4可知"):
        set_para_text(child, ANALYSIS_SIZE)
    elif text.startswith("图3-1展示"):
        set_para_text(child, ANALYSIS_FIG)
    elif text.startswith("4.1.3 离线模型编译与与预处理"):
        set_para_text(child, "4.1.3 离线模型编译与预处理")

if OUT.exists():
    OUT.unlink()

with zipfile.ZipFile(SRC, "r") as zin, zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        if item.filename == "word/document.xml":
            zout.writestr(item, ET.tostring(root, encoding="utf-8", xml_declaration=True))
        else:
            zout.writestr(item, zin.read(item.filename))

print(f"output={OUT.resolve()}")
