from __future__ import annotations

import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML_NS = "http://www.w3.org/XML/1998/namespace"
NS = {"w": W_NS}

ET.register_namespace("w", W_NS)
ET.register_namespace("r", "http://schemas.openxmlformats.org/officeDocument/2006/relationships")
ET.register_namespace("wp", "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing")
ET.register_namespace("a", "http://schemas.openxmlformats.org/drawingml/2006/main")
ET.register_namespace("pic", "http://schemas.openxmlformats.org/drawingml/2006/picture")
ET.register_namespace("mc", "http://schemas.openxmlformats.org/markup-compatibility/2006")
ET.register_namespace("w14", "http://schemas.microsoft.com/office/word/2010/wordml")
ET.register_namespace("w15", "http://schemas.microsoft.com/office/word/2012/wordml")
ET.register_namespace("w16", "http://schemas.microsoft.com/office/word/2018/wordml")


def qn(tag: str) -> str:
    return f"{{{W_NS}}}{tag}"


def para_text(p: ET.Element) -> str:
    return "".join(t.text or "" for t in p.findall(".//w:t", NS)).strip()


def make_run(text: str, superscript: bool = False) -> ET.Element:
    run = ET.Element(qn("r"))
    if superscript:
        rpr = ET.SubElement(run, qn("rPr"))
        vert = ET.SubElement(rpr, qn("vertAlign"))
        vert.set(qn("val"), "superscript")
    t = ET.SubElement(run, qn("t"))
    if text.startswith(" ") or text.endswith(" ") or "  " in text:
        t.set(f"{{{XML_NS}}}space", "preserve")
    t.text = text
    return run


def replace_paragraph_text(p: ET.Element, text: str) -> None:
    keep = []
    for child in list(p):
        if child.tag == qn("pPr"):
            keep.append(child)
    for child in list(p):
        p.remove(child)
    for child in keep:
        p.append(child)

    parts = re.split(r"(\[[0-9,\-\s]+\])", text)
    for part in parts:
        if not part:
            continue
        p.append(make_run(part, bool(re.fullmatch(r"\[[0-9,\-\s]+\]", part))))


def main() -> None:
    src = Path("\u82cf\u7ecd\u4fca\u6bd5\u4e1a\u8bba\u6587\u6700\u65b0_\u6700\u7ec8\u683c\u5f0f\u4fee\u6b63.docx")
    out = Path("thesis_chapter1_polished.docx")
    tmp = Path("~chapter1_polished.tmp.docx")
    if not src.exists():
        raise FileNotFoundError(src)

    shutil.copyfile(src, tmp)

    replacements = {
        2: "实验室承担着高校教学、科研和实践训练等多重任务，内部设备类型复杂，人员进出频繁，危险区域误入、初起火情以及小型资产管理不到位等问题都可能带来安全隐患。现有实验室安防仍较多依靠人工巡查和普通报警设备，这类方式虽然实现简单，但在连续监看、主动识别和细分场景判断方面存在不足。例如，人员是否进入危险区域、画面中是否出现火焰、开发板等实验资产数量是否异常，仅依赖传统视频监控并不容易及时发现。随着深度学习目标检测方法逐渐成熟，将视觉算法引入监控画面实时分析，已成为实验室安全管理升级的一条可行路径；与此同时，华为昇腾等国产边缘 AI 平台的应用，也为嵌入式场景下的本地化推理提供了硬件支撑。[1-3]",
        3: "从实际应用角度看，本文研究有助于提升实验室安全管理的主动性。系统通过危险区域入侵告警、火焰视觉告警和板卡缺失告警，对常见风险进行较早发现和提示，可在一定程度上减少人工巡检带来的时间成本以及误判、漏判问题。系统运行过程中能够持续接入视频流，自动触发报警并保存相关日志，从而为后续追溯和现场管理提供依据。对于高校实验室智能化改造而言，该方案不只停留在算法验证层面，还兼顾了嵌入式部署和实时应用需求，因此具有一定的工程推广价值。",
        4: "因此，面向实验室场景构建一个可视化智能检测平台，可以弥补传统监控“只显示画面、缺少智能分析”的不足。在高校实验室安全管理要求不断提高的背景下，开展该课题研究既具有现实意义，也具备较明确的应用前景。",
        7: "目标检测是计算机视觉中的基础任务之一，其目标是在图像或视频流中确定感兴趣目标的位置，并给出相应类别。随着深度学习的发展，目标检测算法逐渐形成了两条主要技术路线：一类是基于候选区域的两阶段检测方法，另一类是直接回归目标位置和类别的单阶段检测方法。",
        8: "两阶段算法以 R-CNN 系列为代表，如 Faster R-CNN、Mask R-CNN 等。该类方法通常先生成候选区域，再对候选区域进行特征提取、分类和边界框回归，因此在检测精度方面具有较强优势。需要注意的是，两阶段结构往往计算流程较长，网络复杂度和推理开销也更高，在 COCO 等标准数据集上可以取得较好的 AP 指标，但放到工业安防或实验室实时监控场景中，推理延迟和硬件资源占用会成为较明显的限制。",
        9: "为提高检测速度，SSD 和 YOLO（You Only Look Once）等单阶段检测器逐渐得到广泛应用。这类方法将目标检测视为端到端回归问题，通过一次前向传播直接输出目标边界框和类别概率，因而更适合实时应用。自 YOLOv1 提出以来，YOLO 系列不断围绕特征表达、训练策略和网络结构进行改进：YOLOv3 引入多尺度预测，增强了小目标检测能力；YOLOv4、YOLOv5 进一步结合 Mosaic 数据增强、CSP 结构等工程化技巧，使训练效率、检测速度和部署便利性都有了明显提升。",
        10: "近年来，YOLO 系列仍在持续演进，并逐步向更高精度、更低延迟和更易部署的方向发展。YOLOv7 通过扩展的高效层聚合网络（E-ELAN）改善特征学习能力，在精度与速度之间取得了较好的平衡；后续版本则继续探索无锚框检测、端到端检测、注意力机制以及更轻量的网络结构，以适配不同计算平台和应用场景。对本文而言，YOLOv7 的结构相对成熟，训练与部署流程也较稳定，因此更适合作为实验室边缘检测系统的基础模型。[4-12]",
        11: "不过，算法指标的提升并不等同于工程场景中的可用性。对于实验室监控这类边缘端应用，模型需要在算力和内存受限的设备上长时间稳定运行。如果网络结构过于复杂，即使离线测试精度较高，也可能在实际部署时出现帧率不足、延迟偏大或资源占用过高等问题。因此，选择成熟、稳定且便于硬件加速的检测网络，并围绕具体场景进行适当优化，是实验室可视化监控系统落地时更需要关注的研究重点。",
        13: "随着人工智能计算从云端向端侧延伸，面向视觉推理任务的嵌入式 AI 平台逐渐成为边缘智能的重要载体。当前常见硬件路线大致包括三类：以 NVIDIA Jetson 系列为代表的移动端 GPU 平台，依托 CUDA 生态提供较强的浮点计算能力；以华为昇腾和 Google Edge TPU 为代表的 ASIC 平台，通过专用神经网络处理单元在定点推理中获得较高能效；以及以 Xilinx 为代表的 FPGA 异构平台，侧重底层逻辑的可定制化。不同平台在性能、功耗、开发生态和成本方面各有侧重，具体选择需要结合应用场景综合考虑。",
        14: "在上述平台中，华为昇腾系列凭借较完整的软硬件生态，在国产化边缘计算场景中具有较强代表性。其硬件底层采用面向深度学习计算设计的达芬奇架构（DaVinci Architecture），内部矩阵计算单元能够对卷积和张量乘加运算进行加速。软件层面，CANN（Compute Architecture for Neural Networks）作为异构计算基础架构，负责衔接上层训练框架与底层硬件；通过 ATC 编译器，可将 PyTorch 等框架训练得到的模型转换为昇腾平台可直接运行的离线模型（OM 格式）。这一流程为目标检测模型从训练环境迁移到边缘端部署提供了较完整的工程路径。[17-20,24]",
        16: "高校实验室设备类型多、空间布局复杂，人员进出也较为频繁，因此一直是安全管理中的重点区域。近几年，实验室监控系统逐步从传统的被动记录向智能分析转变，但在实际落地过程中，仍然存在实时性不足、场景适应性不强和部署成本偏高等问题。",
        17: "传统实验室安防通常依靠烟感报警器等物理传感器，以及事后录像回看。物理传感器需要在烟雾、温度或其他危险因素积累到一定程度后才会触发，预警时间相对滞后；普通网络摄像头虽然能够记录现场画面，却缺少对画面内容的实时理解能力。因此，这类系统更多承担事后取证作用，难以在风险刚出现时及时提醒管理人员。",
        18: "为改善被动监控的不足，部分实验室开始采用集中式视觉分析方案，将多路视频统一传输到后台服务器进行推理。这种方式在算法管理上较为集中，但工程代价并不低。一方面，连续视频流对局域网带宽和传输稳定性要求较高，一旦发生拥塞或丢包，预警延迟会明显增加；另一方面，高性能 GPU 服务器采购和维护成本较高，普通高校实验室如果按房间大规模铺开，整体投入压力较大。",
        19: "在算力逐步下沉的背景下，边缘计算为实验室智能安防提供了新的思路。边缘设备可以在摄像头附近完成视频解析和模型推理，减少对中心服务器和网络带宽的依赖。不过，现有商用边缘分析盒在实验室细分场景中仍有局限：通用算法对开发板、仪器附件等小目标和遮挡目标的适应能力有限，多任务处理能力也不够灵活；同时，如果缺少针对 NPU 架构的编译优化和多线程调度设计，系统在长时间处理高频视频流时容易出现掉帧、延迟升高甚至资源泄漏等问题，难以满足 7×24 小时稳定运行的要求。",
        21: "本文围绕基于 YOLOv7 的实验室安全实时检测系统展开研究，主要针对传统实验室监控依赖人工判断、预警不够及时的问题，设计并实现一套能够自动识别实验室安全风险的智能检测系统。系统面向人员靠近危险区域、实验室资产异常以及火焰火情等典型场景，完成视频流检测、实时告警和日志记录等功能。研究重点包括 YOLOv7 模型在实验室数据集上的训练与改进，以及模型在华为昇腾 Atlas 200I DK A2 开发者套件上的部署实现，最终形成集算法、软件和硬件于一体的边缘智能应用方案。[1]",
        23: "第一章说明实验室安全智能监控的研究背景和意义，并从目标检测算法、嵌入式 AI 设备以及实验室监控系统三个方面梳理相关研究现状，在此基础上给出本文的研究内容和章节安排。",
        24: "第二章围绕系统需求与总体方案展开，分析实验室安全实时检测系统的功能需求，介绍硬件平台和视觉传感器的选型依据，并说明软件系统架构、开发环境和整体工作流程。",
        25: "第三章介绍 YOLOv7 算法的网络结构和基本原理，随后说明实验室场景数据集的构建、数据增强和模型训练方法；在此基础上，进一步讨论注意力机制引入、损失函数调整等模型优化工作，并通过消融实验与对比实验验证改进效果。",
        26: "第四章面向边缘部署需求，介绍模型轻量化与转换流程，包括利用 AMCT 和 ATC 工具完成 PyTorch、ONNX 到昇腾 OM 模型的转换，并说明模型推理过程以及人机交互界面的设计与实现。",
        27: "第五章给出系统实验环境和评价指标，重点展示危险区域入侵告警、板卡缺失告警和火灾火焰告警三个功能模块的检测结果，并对系统运行性能进行分析。",
        28: "第六章总结本文在算法研究、系统设计和工程实现方面完成的主要工作，分析当前系统仍存在的不足，并对后续可继续改进的方向进行展望。",
        30: "本章围绕论文研究对象展开了整体说明。首先介绍实验室安全智能监控系统的研究背景和应用意义，指出人工巡检和普通视频监控在实时性、智能化程度以及场景适应性方面仍有不足；随后从目标检测算法、嵌入式边缘计算平台和实验室智能监控系统三个角度梳理国内外研究现状，进一步明确本文以 YOLOv7 算法改进、边缘端部署和多任务安全预警为核心的研究思路。上述内容为后续系统需求分析、方案设计和实验验证奠定了基础。",
    }

    with ZipFile(tmp, "r") as zin:
        xml_bytes = zin.read("word/document.xml")

    root = ET.fromstring(xml_bytes)
    paras = root.findall(".//w:body/w:p", NS)
    texts = [para_text(p) for p in paras]
    start = next(i for i, t in enumerate(texts) if t.startswith("第1章"))
    end = next(i for i, t in enumerate(texts[start + 1 :], start + 1) if t.startswith("第2章"))
    if end - start < 25:
        raise RuntimeError("Chapter 1 range looks too short; aborting.")

    for rel_index, new_text in replacements.items():
        replace_paragraph_text(paras[start + rel_index], new_text)

    new_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)

    with ZipFile(tmp, "r") as zin, ZipFile(out, "w", ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = new_xml if item.filename == "word/document.xml" else zin.read(item.filename)
            zout.writestr(item, data)

    tmp.unlink(missing_ok=True)
    print(out.resolve())


if __name__ == "__main__":
    main()
