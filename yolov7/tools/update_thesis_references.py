import copy
import os
import re
import shutil
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML_NS = "http://www.w3.org/XML/1998/namespace"
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


def add_text_run(p: ET.Element, text: str) -> None:
    r = ET.SubElement(p, wtag("r"))
    t = ET.SubElement(r, wtag("t"))
    if text.startswith(" ") or text.endswith(" "):
        t.set(f"{{{XML_NS}}}space", "preserve")
    t.text = text


def remove_trailing_spaces_before_citation(p: ET.Element) -> None:
    text_nodes = p.findall(".//w:t", NS)
    for t in reversed(text_nodes):
        if t.text:
            t.text = re.sub(r"\s+$", "", t.text)
            return


def add_citation_if_needed(p: ET.Element, citation: str) -> bool:
    text = paragraph_text(p).strip()
    if not text or citation in text:
        return False
    if re.search(r"\[[0-9,\-\s]+\]$", text):
        return False
    remove_trailing_spaces_before_citation(p)
    add_text_run(p, citation)
    return True


def make_ref_paragraph(text: str, ppr_template: ET.Element | None) -> ET.Element:
    p = ET.Element(wtag("p"))
    if ppr_template is not None:
        p.append(copy.deepcopy(ppr_template))
    r = ET.SubElement(p, wtag("r"))
    t = ET.SubElement(r, wtag("t"))
    t.text = text
    return p


def find_source() -> Path:
    exact = Path("苏绍俊毕业论文_最新.docx")
    if exact.exists():
        return exact
    no_underscore = Path("苏绍俊毕业论文最新.docx")
    if no_underscore.exists():
        return no_underscore
    candidates = sorted(Path(".").glob("*.docx"), key=lambda p: p.stat().st_mtime, reverse=True)
    for p in candidates:
        if "毕业论文最新" in p.name and "参考文献标注完善" not in p.name:
            return p
    if not candidates:
        raise FileNotFoundError("No .docx file found in current directory.")
    return candidates[0]


REFERENCES = [
    "[1] 陈磊静. 面向化工实验室的开放式智能监控系统设计[D]. 2024.",
    "[2] Shi W, Cao J, Zhang Q, et al. Edge computing: Vision and challenges[J]. IEEE Internet of Things Journal, 2016, 3(5): 637-646.",
    "[3] Satyanarayanan M. The emergence of edge computing[J]. Computer, 2017, 50(1): 30-39.",
    "[4] Girshick R. Fast R-CNN[C]//2015 IEEE International Conference on Computer Vision. Santiago: IEEE, 2015: 1440-1448.",
    "[5] Ren S, He K, Girshick R, et al. Faster R-CNN: Towards real-time object detection with region proposal networks[J]. IEEE Transactions on Pattern Analysis and Machine Intelligence, 2017, 39(6): 1137-1149.",
    "[6] Redmon J, Divvala S, Girshick R, et al. You Only Look Once: Unified, real-time object detection[C]//2016 IEEE Conference on Computer Vision and Pattern Recognition. Las Vegas: IEEE, 2016: 779-788.",
    "[7] Bochkovskiy A, Wang C Y, Liao H Y M. YOLOv4: Optimal speed and accuracy of object detection[EB/OL]. arXiv:2004.10934, 2020.",
    "[8] Wang C Y, Bochkovskiy A, Liao H Y M. YOLOv7: Trainable bag-of-freebies sets new state-of-the-art for real-time object detectors[C]//2023 IEEE/CVF Conference on Computer Vision and Pattern Recognition. Vancouver: IEEE, 2023: 7464-7475.",
    "[9] Jocher G, Chaurasia A, Qiu J. Ultralytics YOLOv8[EB/OL]. 2023.",
    "[10] Wang A, Chen H, Liu L, et al. YOLOv10: Real-time end-to-end object detection[EB/OL]. arXiv:2405.14458, 2024.",
    "[11] Tian Y, Ye Q, Doermann D. YOLOv12: Attention-centric real-time object detectors[EB/OL]. arXiv:2502.12524, 2025.",
    "[12] Lei M, Li S, Wu Y, et al. YOLOv13: Real-time object detection with hypergraph-enhanced adaptive visual perception[EB/OL]. arXiv:2506.17733, 2025.",
    "[13] Hu J, Shen L, Sun G. Squeeze-and-Excitation Networks[C]//2018 IEEE/CVF Conference on Computer Vision and Pattern Recognition. Salt Lake City: IEEE, 2018: 7132-7141.",
    "[14] Lin T Y, Goyal P, Girshick R, et al. Focal Loss for Dense Object Detection[C]//2017 IEEE International Conference on Computer Vision. Venice: IEEE, 2017: 2980-2988.",
    "[15] Paszke A, Gross S, Massa F, et al. PyTorch: An imperative style, high-performance deep learning library[C]//Advances in Neural Information Processing Systems. 2019, 32: 8024-8035.",
    "[16] Bradski G. The OpenCV Library[J]. Dr. Dobb's Journal of Software Tools, 2000, 25(11): 120-126.",
    "[17] 华为技术有限公司. Atlas 200I DK A2 开发者套件产品文档[EB/OL]. 2024.",
    "[18] 华为技术有限公司. CANN 开发工具链用户指南[EB/OL]. 2024.",
    "[19] 华为技术有限公司. AscendCL 应用开发指南[EB/OL]. 2024.",
    "[20] 武畅, 夏玉林, 杨小漫, 等. 基于华为昇腾Atlas 200DK的黑白图片上色实验[J]. 实验科学与技术, 2025, 23(2): 14-22.",
    "[21] 段品凡. 基于边缘计算的工业目标检测算法研究[D]. 大连: 大连交通大学, 2022.",
    "[22] 高维露. 基于昇腾310处理器的电力视觉巡检系统设计与实现[D]. 2023.",
    "[23] 姜庭豪. 基于昇腾AI处理器的YOLOx-F火灾检测算法与系统实现[D]. 2024.",
    "[24] 赵月爱, 沈帅杰, 王智瑜, 等. 基于昇腾AI处理器的轻量化MNG-YOLO模型研究[J]. 电子器件, 2024, 47(5): 1193-1200.",
    "[25] 王浩宇. 基于NPU的SAR目标检测方法研究与实现[D]. 2024.",
]


CITATION_RULES = [
    (lambda t: "实验室是高校和科研机构中重要的功能区域" in t, "[1-3]"),
    (lambda t: "传统实验室监控系统依赖人工" in t, "[1]"),
    (lambda t: "边缘计算的核心" in t, "[2-3]"),
    (lambda t: "算法的演进在近年来持续加速" in t, "[4-12]"),
    (lambda t: "华为昇腾系列凭借" in t, "[17-20,24]"),
    (lambda t: "华为 Atlas 200I DK A2 开发者套件" in t and "代表性产品" in t, "[17,20-25]"),
    (lambda t: t.startswith("YOLOv7 凭借其出色的架构设计"), "[8]"),
    (lambda t: t.startswith("SE 模块的核心思想"), "[13]"),
    (lambda t: "Focal Loss 主要作用于目标置信度损失" in t, "[14]"),
    (lambda t: "训练过程基于 PyTorch" in t, "[8,15]"),
    (lambda t: "底层 OpenCV 可通过非阻塞模式" in t, "[16]"),
    (lambda t: "宿主机必须安装华为官方提供的 CANN" in t, "[18]"),
    (lambda t: "提供 AscendCL" in t, "[19]"),
    (lambda t: "ATC昇腾张量编译器" in t, "[18]"),
    (lambda t: "AIPP 允许在模型推理前" in t, "[17-19]"),
    (lambda t: "相关指标测试" in t and "Atlas 200DK" in t, "[20]"),
    (lambda t: "工业目标检测" in t, "[21]"),
    (lambda t: "电力视觉巡检" in t, "[22]"),
    (lambda t: "火灾" in t and "YOLOx-F" in t, "[23]"),
    (lambda t: "轻量化目标检测模型MNG-YOLO" in t, "[24]"),
    (lambda t: "NPU" in t and "SAR" in t, "[25]"),
]


def main() -> None:
    source = find_source()
    out = source.with_name(source.stem + "_参考文献标注完善.docx")

    tmp = Path("_tmp_thesis_reference_edit")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()

    with zipfile.ZipFile(source, "r") as zin:
        zin.extractall(tmp)

    doc_xml = tmp / "word" / "document.xml"
    tree = ET.parse(doc_xml)
    root = tree.getroot()
    body = root.find("w:body", NS)
    if body is None:
        raise RuntimeError("Cannot find document body.")

    body_children = list(body)
    paragraphs = [child for child in body_children if child.tag == wtag("p")]
    ref_p = None
    next_p = None
    for p in paragraphs:
        text = paragraph_text(p).strip()
        if ref_p is None and text == "参考文献":
            ref_p = p
        elif ref_p is not None and (text.startswith("攻读学士") or text.startswith("致") and "谢" in text):
            next_p = p
            break
    if ref_p is None:
        raise RuntimeError("Cannot find reference heading.")

    changed_citations = 0
    for p in paragraphs:
        if p is ref_p:
            break
        text = paragraph_text(p).strip()
        if not text:
            continue
        for predicate, citation in CITATION_RULES:
            if predicate(text):
                changed_citations += int(add_citation_if_needed(p, citation))
                break

    # Reference paragraph style: reuse the first old reference paragraph if available.
    ref_heading_idx = body_children.index(ref_p)
    ref_end_idx = body_children.index(next_p) if next_p is not None else len(body_children) - 1
    ppr_template = None
    for child in body_children[ref_heading_idx + 1 : ref_end_idx]:
        if child.tag == wtag("p"):
            ppr = child.find("w:pPr", NS)
            if ppr is not None:
                ppr_template = copy.deepcopy(ppr)
                break

    for child in body_children[ref_heading_idx + 1 : ref_end_idx]:
        body.remove(child)

    insert_at = list(body).index(ref_p) + 1
    for ref in REFERENCES:
        body.insert(insert_at, make_ref_paragraph(ref, ppr_template))
        insert_at += 1

    tree.write(doc_xml, encoding="UTF-8", xml_declaration=True)

    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for root_dir, _, files in os.walk(tmp):
            for file in files:
                path = Path(root_dir) / file
                arcname = path.relative_to(tmp).as_posix()
                zout.write(path, arcname)

    shutil.rmtree(tmp)
    print(f"source={source}")
    print(f"output={out}")
    print(f"citations_added={changed_citations}")
    print(f"references={len(REFERENCES)}")


if __name__ == "__main__":
    main()
