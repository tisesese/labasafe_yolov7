# -*- coding: utf-8 -*-
import shutil
import sys
import zipfile
from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET


SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("苏绍俊毕业论文_实验结果更新.docx")
OUT = SRC.with_name(SRC.stem + "_3.3.1参数完善.docx")

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


def make_label_paragraph(label, text):
    p = ET.Element(w("p"))
    p_pr = ET.SubElement(p, w("pPr"))
    ind = ET.SubElement(p_pr, w("ind"))
    set_w_attr(ind, "firstLine", "420")
    spacing = ET.SubElement(p_pr, w("spacing"))
    set_w_attr(spacing, "after", "120")
    set_w_attr(spacing, "line", "360")
    set_w_attr(spacing, "lineRule", "auto")
    p.append(make_run(label, bold=True))
    p.append(make_run(text))
    return p


def para_text(p):
    return "".join((t.text or "") for t in p.findall(".//" + w("t"))).strip()


NEW_BLOCKS = [
    make_paragraph(
        "为保证四组消融实验具有可比性，本文在模型训练阶段采用统一的训练环境、数据划分、输入尺寸和优化策略，仅改变注意力模块和损失函数类型。四组实验分别为原始 YOLOv7 基线模型、引入 SE 注意力机制的模型、采用 Focal Loss 的模型，以及同时引入 SE 注意力机制和 Focal Loss 的组合模型。通过这种控制变量方式，可以更清晰地分析 SE 模块和 Focal Loss 对检测性能的影响。"
    ),
    make_label_paragraph(
        "（1）训练环境与初始权重。 ",
        "模型训练基于 PyTorch 深度学习框架和 CUDA 加速环境完成，计算设备设置为 device=0，即使用单张 GPU 进行训练。初始权重采用 YOLOv7 官方预训练权重 yolov7.pt。预训练权重已经在大规模通用目标检测数据上学习到较稳定的边缘、纹理和形状特征，将其迁移到实验室安全检测任务中，可以降低从零训练带来的收敛难度，并提高小规模数据集上的训练稳定性。"
    ),
    make_label_paragraph(
        "（2）数据集与类别参数。 ",
        "实验使用清洗后的 mydata_YOLO_clean 数据集，训练集、验证集和测试集分别包含 1252、300 和 254 张图像。数据配置文件中 nc=3，表示模型需要识别 3 个类别，类别名称分别为 fire、person 和 board card。训练、验证和测试均使用相同的数据划分，避免因数据分布变化影响不同模型之间的横向比较。"
    ),
    make_label_paragraph(
        "（3）输入尺寸、训练轮数与批量大小。 ",
        "输入图像尺寸设置为 img_size=640×640。该尺寸是 YOLOv7 中较常用的训练尺度，能够在检测精度和显存占用之间取得平衡。训练轮数设置为 epochs=100，表示模型完整遍历训练集 100 次；batch size 设置为 6，表示每次参数更新时同时输入 6 张图像。batch size 的取值主要受 GPU 显存限制影响，设置为 6 可以保证训练过程稳定运行，同时尽量提高梯度估计的稳定性。"
    ),
    make_label_paragraph(
        "（4）优化器与学习率参数。 ",
        "优化器采用带动量的 SGD（Stochastic Gradient Descent）。初始学习率 lr0=0.01，用于控制训练初期参数更新步长；最终学习率比例 lrf=0.1，表示训练后期学习率衰减至初始学习率的一定比例；momentum=0.937，用于累积历史梯度方向，加快模型收敛并减小梯度震荡；weight_decay=0.0005，用于对权重参数进行正则化约束，降低过拟合风险。训练过程中配合余弦退火策略动态调整学习率，使模型前期快速学习、后期稳定收敛。"
    ),
    make_label_paragraph(
        "（5）预热训练参数。 ",
        "训练初期设置 warmup_epochs=3.0，即前 3 个 epoch 作为预热阶段。warmup_momentum=0.8 表示预热阶段动量的起始值，warmup_bias_lr=0.1 表示偏置参数在预热阶段使用的学习率。Warmup 的作用是在训练刚开始时逐步调整学习率和动量，避免模型从预训练权重迁移到新数据集时出现过大的梯度波动。"
    ),
    make_label_paragraph(
        "（6）损失权重参数。 ",
        "YOLOv7 的训练损失主要由边界框回归损失、目标置信度损失和类别分类损失组成。本文设置 box=0.05、obj=0.7、cls=0.3，分别表示边界框损失、目标置信度损失和分类损失在总损失中的权重。box 权重用于约束预测框与真实框的位置和尺度偏差；obj 权重用于强化前景与背景的区分能力；cls 权重用于提高 fire、person 和 board card 三类目标的分类判别能力。"
    ),
    make_label_paragraph(
        "（7）锚框与样本匹配参数。 ",
        "训练中保持 YOLOv7 默认锚框设置，并启用自动锚框检查。anchor_t=4.0 用于控制锚框与目标框尺寸匹配的阈值，iou_t=0.2 用于正负样本匹配过程中的 IoU 约束。合理的锚框和样本匹配策略能够提高小目标和不同尺度目标的正样本分配质量，减少因目标尺寸差异过大造成的漏检。"
    ),
    make_label_paragraph(
        "（8）数据增强参数。 ",
        "训练阶段启用 Mosaic、MixUp、Copy-Paste、HSV 色彩扰动和几何变换等增强策略。具体参数包括 hsv_h=0.05、hsv_s=0.7、hsv_v=0.5，用于改变图像色调、饱和度和亮度；degrees=10、translate=0.2、scale=1.2、shear=2.0、perspective=0.001，用于模拟旋转、平移、缩放、剪切和透视变化；flipud=0.5、fliplr=0.5，表示垂直翻转和水平翻转概率；mosaic=1.0、mixup=0.3、copy_paste=0.3、paste_in=0.3，用于增加目标组合方式和背景复杂度。这些增强方式有助于提高模型对光照变化、拍摄角度变化、小目标和遮挡目标的适应能力。"
    ),
    make_label_paragraph(
        "（9）注意力机制与损失函数参数。 ",
        "消融实验中，attention 参数用于控制是否引入注意力机制，当 attention=none 时表示使用原始 YOLOv7 结构，当 attention=se 时表示在主干网络中引入 SE 通道注意力模块。loss 参数用于控制训练损失类型，当 loss=bce 时使用默认 BCE 损失；当 loss=focal 时启用 Focal Loss。Focal Loss 实验中设置 fl_alpha=0.25、fl_gamma=1.5，其中 fl_alpha 用于平衡正负样本权重，fl_gamma 用于降低易分类样本的损失贡献，使模型更加关注困难样本。对于 BCE 对照组，训练程序将 fl_gamma 置为 0，以确保其不受 Focal Loss 调制因子的影响。"
    ),
    make_label_paragraph(
        "（10）评价指标参数。 ",
        "模型训练完成后，本文主要采用 Precision、Recall、mAP@0.5 和 mAP@0.5:0.95 评价检测性能。Precision 表示模型预测为目标的结果中真实目标所占比例，反映误检情况；Recall 表示真实目标中被模型成功检测出的比例，反映漏检情况；mAP@0.5 表示 IoU 阈值为 0.5 时各类别 AP 的平均值，更关注目标是否被正确检出；mAP@0.5:0.95 表示 IoU 阈值从 0.5 到 0.95 变化时的平均 mAP，对定位精度要求更严格，因此更能反映预测框质量。"
    ),
    make_paragraph("Precision = TP / (TP + FP)", align="center", first_line=False),
    make_paragraph("Recall = TP / (TP + FN)", align="center", first_line=False),
    make_paragraph("mAP = (1/N) Σ AP_i", align="center", first_line=False),
    make_paragraph(
        "其中，TP 表示正确检测出的目标数量，FP 表示误检数量，FN 表示漏检数量，N 表示类别数。通过上述训练参数和评价指标设置，本文能够在统一实验条件下比较不同模型的检测精度、召回能力、定位质量和模型稳定性，为后续训练结果分析提供依据。"
    ),
]


with zipfile.ZipFile(SRC, "r") as zin:
    document_xml = zin.read("word/document.xml")

root = ET.fromstring(document_xml)
body = root.find(w("body"))
children = list(body)


def find_after(start_idx, prefix):
    for idx in range(start_idx + 1, len(children)):
        if children[idx].tag == w("p") and para_text(children[idx]).startswith(prefix):
            return idx
    raise RuntimeError(f"Heading not found after {start_idx}: {prefix}")


body_h33 = None
for idx, child in enumerate(children):
    if idx > 150 and child.tag == w("p") and para_text(child).startswith("3.3 "):
        text = para_text(child)
        if "训练参数" in text or "结果分析" in text:
            body_h33 = idx
if body_h33 is None:
    raise RuntimeError("Body 3.3 heading not found")

h331 = find_after(body_h33, "3.3.1 ")
h332 = find_after(h331, "3.3.2 ")

for idx in range(h332 - 1, h331, -1):
    body.remove(children[idx])
for offset, block in enumerate(deepcopy(NEW_BLOCKS)):
    body.insert(h331 + 1 + offset, block)

if OUT.exists():
    OUT.unlink()

shutil.copy2(SRC, OUT)
with zipfile.ZipFile(SRC, "r") as zin, zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        if item.filename == "word/document.xml":
            zout.writestr(item, ET.tostring(root, encoding="utf-8", xml_declaration=True))
        else:
            zout.writestr(item, zin.read(item.filename))

print(f"source={SRC.resolve()}")
print(f"output={OUT.resolve()}")
