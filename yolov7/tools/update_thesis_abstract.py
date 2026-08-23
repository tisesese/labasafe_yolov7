import copy
import os
import shutil
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}

ET.register_namespace("w", W_NS)
ET.register_namespace("r", "http://schemas.openxmlformats.org/officeDocument/2006/relationships")
ET.register_namespace("wp", "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing")
ET.register_namespace("a", "http://schemas.openxmlformats.org/drawingml/2006/main")
ET.register_namespace("pic", "http://schemas.openxmlformats.org/drawingml/2006/picture")
ET.register_namespace("w14", "http://schemas.microsoft.com/office/word/2010/wordml")
ET.register_namespace("w15", "http://schemas.microsoft.com/office/word/2012/wordml")
ET.register_namespace("mc", "http://schemas.openxmlformats.org/markup-compatibility/2006")


def wtag(name: str) -> str:
    return f"{{{W_NS}}}{name}"


def paragraph_text(p: ET.Element) -> str:
    return "".join(t.text or "" for t in p.findall(".//w:t", NS))


def set_plain_paragraph(p: ET.Element, text: str) -> None:
    ppr = p.find("w:pPr", NS)
    preserved_ppr = copy.deepcopy(ppr) if ppr is not None else None
    for child in list(p):
        p.remove(child)
    if preserved_ppr is not None:
        p.append(preserved_ppr)
    run = ET.SubElement(p, wtag("r"))
    t = ET.SubElement(run, wtag("t"))
    t.text = text


def find_source() -> Path:
    preferred = Path("苏绍俊毕业论文最新.docx")
    if preferred.exists():
        return preferred
    candidates = [p for p in Path(".").glob("*.docx") if not p.name.startswith("~$")]
    if not candidates:
        raise FileNotFoundError("No DOCX file found.")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def paragraph_children(body: ET.Element) -> list[ET.Element]:
    return [child for child in list(body) if child.tag == wtag("p")]


def find_para(paras: list[ET.Element], predicate) -> ET.Element:
    for p in paras:
        if predicate(paragraph_text(p).strip()):
            return p
    raise RuntimeError("Target paragraph not found.")


def remove_between(body: ET.Element, first_keep: ET.Element, last_keep: ET.Element) -> None:
    children = list(body)
    start = children.index(first_keep)
    end = children.index(last_keep)
    for child in children[start + 1 : end]:
        body.remove(child)


CHINESE_ABSTRACT = (
    "实验室是高校教学和科研的重要场所，人员流动、设备密集和火灾隐患使其对实时安全监控提出较高要求。"
    "针对传统监控依赖人工巡视、预警滞后和边缘侧智能分析不足的问题，本文设计并实现了一套基于嵌入式平台的实验室视频监控系统。"
    "系统以 YOLOv7 为视觉检测基线，构建人员、开发板和火焰三类目标数据集，通过数据清洗、分组划分和增强策略提升样本质量与泛化能力；"
    "在算法层面引入 SE 通道注意力机制增强关键特征表达，并在置信度与分类分支加入 Focal Loss 以改善小目标和困难样本学习。"
    "实验结果表明，改进模型在验证集上的 mAP@0.5:0.95 达到 0.6614，较基线模型 0.5377 明显提升，且 SE 模块仅增加约 0.87% 参数量。"
    "工程部署方面，本文完成 PyTorch 模型到 ONNX、OM 的转换，结合 AMCT 量化、ATC 编译和 AIPP 硬件预处理，将模型体积由 140 MB 压缩至 35.2 MB，并部署于华为昇腾 Atlas 200I DK A2。"
    "实机测试表明，系统在危险区域入侵、开发板清点和火灾告警三类任务并发运行时保持 11.78 至 13.91 FPS，能够满足实验室场景低功耗、低延迟的实时监控需求。"
)

CHINESE_KEYWORDS = "关键词：实验室安全，目标检测，YOLOv7，边缘计算，昇腾 Atlas 200I DK A2"

ENGLISH_ABSTRACT = (
    "Laboratories are important places for teaching and scientific research in universities. "
    "Due to frequent personnel movement, dense equipment placement and potential fire hazards, they require real-time and intelligent safety monitoring. "
    "To address the dependence on manual inspection, delayed warning and insufficient edge-side analysis in traditional monitoring systems, this thesis designs and implements an embedded laboratory video monitoring system. "
    "YOLOv7 is adopted as the baseline visual detection network, and a dataset containing persons, development boards and flames is constructed. "
    "Data cleaning, grouped dataset splitting and augmentation strategies are used to improve sample quality and generalization. "
    "At the algorithm level, the SE channel attention mechanism is introduced to enhance key feature representation, and Focal Loss is applied to the objectness and classification branches to improve the learning of small targets and hard samples. "
    "Experimental results show that the improved model achieves an mAP@0.5:0.95 of 0.6614 on the validation set, which is significantly higher than the baseline value of 0.5377, while the SE module increases the number of parameters by only about 0.87%. "
    "For engineering deployment, the trained PyTorch model is converted to ONNX and OM formats, compressed from 140 MB to 35.2 MB through AMCT quantization, ATC compilation and AIPP hardware preprocessing, and deployed on the Huawei Ascend Atlas 200I DK A2. "
    "On-device tests show that the system maintains 11.78-13.91 FPS when intrusion detection, board counting and fire warning run concurrently, meeting the low-power and low-latency requirements of real-time laboratory monitoring."
)

ENGLISH_KEYWORDS = "Keywords: laboratory safety, object detection, YOLOv7, edge computing, Ascend Atlas 200I DK A2"


def main() -> None:
    source = find_source()
    output = source.with_name(source.stem + "_摘要完善.docx")
    tmp = Path("_tmp_thesis_abstract_edit")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()

    with zipfile.ZipFile(source, "r") as zin:
        zin.extractall(tmp)

    doc_xml = tmp / "word" / "document.xml"
    tree = ET.parse(doc_xml)
    root = tree.getroot()
    body = root.find(".//w:body", NS)
    if body is None:
        raise RuntimeError("Cannot find document body.")

    paras = paragraph_children(body)
    chinese_heading = find_para(paras, lambda t: t.replace(" ", "") == "摘要")
    chinese_keywords = find_para(paras, lambda t: t.startswith("关键词"))
    english_heading = find_para(paras, lambda t: t == "ABSTRACT")
    english_keywords = find_para(paras, lambda t: t.startswith("Keywords:"))

    # Keep the first body paragraph after each heading and delete template-only explanation paragraphs.
    children = list(body)
    ch_start = children[children.index(chinese_heading) + 1]
    remove_between(body, ch_start, chinese_keywords)
    set_plain_paragraph(ch_start, CHINESE_ABSTRACT)
    set_plain_paragraph(chinese_keywords, CHINESE_KEYWORDS)
    remove_between(body, chinese_keywords, english_heading)

    children = list(body)
    en_start = children[children.index(english_heading) + 1]
    remove_between(body, en_start, english_keywords)
    set_plain_paragraph(en_start, ENGLISH_ABSTRACT)
    set_plain_paragraph(english_keywords, ENGLISH_KEYWORDS)

    tree.write(doc_xml, encoding="UTF-8", xml_declaration=True)

    if output.exists():
        output.unlink()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zout:
        for root_dir, _, files in os.walk(tmp):
            for file in files:
                path = Path(root_dir) / file
                zout.write(path, path.relative_to(tmp).as_posix())

    shutil.rmtree(tmp)
    print(f"source={source}")
    print(f"output={output}")


if __name__ == "__main__":
    main()
