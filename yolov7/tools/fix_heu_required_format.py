import copy
import os
import re
import shutil
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS = {"w": W_NS, "a": A_NS}

ET.register_namespace("w", W_NS)
ET.register_namespace("r", "http://schemas.openxmlformats.org/officeDocument/2006/relationships")
ET.register_namespace("wp", "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing")
ET.register_namespace("a", A_NS)
ET.register_namespace("pic", "http://schemas.openxmlformats.org/drawingml/2006/picture")
ET.register_namespace("w14", "http://schemas.microsoft.com/office/word/2010/wordml")
ET.register_namespace("w15", "http://schemas.microsoft.com/office/word/2012/wordml")
ET.register_namespace("mc", "http://schemas.openxmlformats.org/markup-compatibility/2006")


TITLE = "基于嵌入式的实验室视频监控系统的设计与实现"

SUMMARIES = {
    "第1章": (
        "1.4 本章小结",
        "本章首先阐述了实验室安全智能监控系统的研究背景与现实意义，指出传统人工巡检和普通视频监控在实时性、智能化和场景适应性方面存在不足。随后，从目标检测算法、嵌入式边缘计算平台和实验室智能监控系统三个方面梳理了国内外研究现状，明确了本文围绕 YOLOv7 算法改进、边缘端部署和多任务安全预警展开研究的总体思路，为后续系统需求分析和方案设计提供了依据。",
    ),
    "第2章": (
        "2.4 本章小结",
        "本章围绕实验室安全监控系统的需求与总体方案展开分析，明确了危险区域入侵检测、开发板资产清点和火灾火焰告警等核心功能需求，并结合边缘计算低延迟、低功耗的特点确定了以华为昇腾 Atlas 200I DK A2 为核心的硬件平台。同时，本章完成了摄像头采集、双端开发环境、边缘端运行环境和系统软件主流程的设计，为后续算法训练、模型转换和板端部署奠定了工程基础。",
    ),
    "第3章": (
        "3.4 本章小结",
        "本章完成了实验室安全检测算法的设计与实验分析。首先以 YOLOv7 作为基线模型，结合实验室场景构建了包含人员、开发板和火焰三类目标的数据集，并通过数据清洗、分组划分和数据增强提高数据质量。随后针对小目标、复杂背景和困难样本问题，引入 SE 通道注意力机制与 Focal Loss 损失函数，并设置四组消融实验进行验证。实验结果表明，改进方法能够在较小模型复杂度增量下提升严格 IoU 阈值下的定位质量和训练稳定性。",
    ),
    "第4章": (
        "4.5 本章小结",
        "本章围绕模型在嵌入式边缘平台上的工程化部署展开研究，完成了从 PyTorch 权重到 ONNX 中间格式，再到昇腾 OM 离线模型的转换流程。针对边缘端算力和存储资源受限的问题，采用 AMCT 完成模型量化压缩，并通过 ATC 编译、AIPP 硬件预处理和 AscendCL 推理接口实现软硬件协同优化。上述工作降低了模型体积和运行开销，为系统在 Atlas 200I DK A2 上稳定实时运行提供了支撑。",
    ),
    "第5章": (
        "5.4 本章小结",
        "本章对系统的实验环境、评价指标、检测效果和硬件性能进行了测试与分析。通过危险区域入侵、开发板缺失和火灾火焰告警三类实机场景验证，系统能够完成空间越界判断、微小资产清点和初起火情识别等任务，并在复杂背景和短时遮挡情况下保持较好的稳定性。硬件性能测试表明，系统经量化和硬件预处理优化后能够在边缘端保持实时推理能力，满足实验室安全监控的实际应用需求。",
    ),
}


def wtag(name: str) -> str:
    return f"{{{W_NS}}}{name}"


def text_of(el: ET.Element) -> str:
    return "".join(t.text or "" for t in el.findall(".//w:t", NS))


def set_text_preserve_ppr(p: ET.Element, text: str) -> None:
    ppr = p.find("w:pPr", NS)
    ppr_copy = copy.deepcopy(ppr) if ppr is not None else None
    for child in list(p):
        p.remove(child)
    if ppr_copy is not None:
        p.append(ppr_copy)
    r = ET.SubElement(p, wtag("r"))
    t = ET.SubElement(r, wtag("t"))
    t.text = text


def make_paragraph(text: str, template: ET.Element | None) -> ET.Element:
    p = ET.Element(wtag("p"))
    if template is not None:
        ppr = template.find("w:pPr", NS)
        if ppr is not None:
            p.append(copy.deepcopy(ppr))
    r = ET.SubElement(p, wtag("r"))
    t = ET.SubElement(r, wtag("t"))
    t.text = text
    return p


def replace_text_nodes(root: ET.Element) -> None:
    fig_table_pattern = re.compile(r"([图表])(\d+)-(\d+)")
    for node in root.findall(".//w:t", NS):
        if not node.text:
            continue
        node.text = fig_table_pattern.sub(r"\1\2.\3", node.text)
        if node.text.startswith("关键词："):
            body = node.text.split("：", 1)[1].strip()
            parts = [p.strip() for p in re.split(r"[，,；;]", body) if p.strip()]
            node.text = "关键词：" + "；".join(parts)


def fix_headers(tmp: Path) -> None:
    for header in (tmp / "word").glob("header*.xml"):
        tree = ET.parse(header)
        root = tree.getroot()
        changed = False
        for node in root.findall(".//w:t", NS):
            if node.text and ("论文题目" in node.text and "×" in node.text):
                node.text = TITLE
                changed = True
        if changed:
            tree.write(header, encoding="UTF-8", xml_declaration=True)


def move_table_captions_above(body: ET.Element) -> None:
    for p in list(body):
        if p.tag != wtag("p"):
            continue
        text = text_of(p).strip()
        if not re.match(r"^表\d+\.\d+\s+", text):
            continue
        children = list(body)
        idx = children.index(p)
        prev_idx = idx - 1
        while prev_idx >= 0 and children[prev_idx].tag == wtag("p") and not text_of(children[prev_idx]).strip():
            prev_idx -= 1
        if prev_idx >= 0 and children[prev_idx].tag == wtag("tbl"):
            table = children[prev_idx]
            body.remove(p)
            body.insert(list(body).index(table), p)


def add_superscript_to_citations(body: ET.Element) -> None:
    citation_re = re.compile(r"(\[[0-9][0-9,\-\s，]*\])")
    paragraphs = [c for c in list(body) if c.tag == wtag("p")]
    ref_heading = next((p for p in paragraphs if text_of(p).strip() == "参考文献"), None)
    ref_body_index = list(body).index(ref_heading) if ref_heading is not None else len(list(body))
    for p in list(body)[:ref_body_index]:
        if p.tag != wtag("p"):
            continue
        # Do not superscript references that appear inside figure/table captions.
        if re.match(r"^[图表]\d+\.\d+", text_of(p).strip()):
            continue
        new_children = []
        changed = False
        for child in list(p):
            if child.tag != wtag("r"):
                new_children.append(child)
                continue
            texts = child.findall("w:t", NS)
            if len(texts) != 1 or not texts[0].text or not citation_re.search(texts[0].text):
                new_children.append(child)
                continue
            original_text = texts[0].text
            base_rpr = child.find("w:rPr", NS)
            parts = citation_re.split(original_text)
            for part in parts:
                if not part:
                    continue
                r = ET.Element(wtag("r"))
                if base_rpr is not None:
                    r.append(copy.deepcopy(base_rpr))
                if citation_re.fullmatch(part):
                    rpr = r.find("w:rPr", NS)
                    if rpr is None:
                        rpr = ET.Element(wtag("rPr"))
                        r.insert(0, rpr)
                    for old in rpr.findall("w:vertAlign", NS):
                        rpr.remove(old)
                    va = ET.SubElement(rpr, wtag("vertAlign"))
                    va.set(wtag("val"), "superscript")
                t = ET.SubElement(r, wtag("t"))
                if part.startswith(" ") or part.endswith(" "):
                    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
                t.text = part
                new_children.append(r)
            changed = True
        if changed:
            for child in list(p):
                p.remove(child)
            for child in new_children:
                p.append(child)


def paragraph_starts(body: ET.Element, prefix: str) -> ET.Element | None:
    for p in body.findall("w:p", NS):
        if text_of(p).strip().startswith(prefix):
            return p
    return None


def add_chapter_summaries(body: ET.Element) -> None:
    children = list(body)
    heading_template = paragraph_starts(body, "2.3.2") or paragraph_starts(body, "3.3.2")
    body_template = paragraph_starts(body, "本系统") or paragraph_starts(body, "实验室")

    for next_chapter, (summary_heading, summary_text) in reversed(
        [
            ("第6章", SUMMARIES["第5章"]),
            ("第5章", SUMMARIES["第4章"]),
            ("第4章", SUMMARIES["第3章"]),
            ("第3章", SUMMARIES["第2章"]),
            ("第2章", SUMMARIES["第1章"]),
        ]
    ):
        # Avoid inserting twice.
        if paragraph_starts(body, summary_heading):
            continue
        current_children = list(body)
        target = next((c for c in current_children if c.tag == wtag("p") and text_of(c).strip().startswith(next_chapter)), None)
        if target is None:
            continue
        insert_at = current_children.index(target)
        body.insert(insert_at, make_paragraph(summary_text, body_template))
        body.insert(insert_at, make_paragraph(summary_heading, heading_template))


def fix_page_numbering_and_duplicate_keywords(body: ET.Element) -> None:
    keyword_seen = 0
    for p in body.findall("w:p", NS):
        text = text_of(p).strip()
        if text.startswith("Keywords:"):
            keyword_seen += 1
            if keyword_seen > 1:
                # Keep paragraph properties and section break, but remove the duplicated visible text.
                set_text_preserve_ppr(p, "")

    # Body section should restart Arabic page numbering from Chapter 1 / Introduction.
    children = list(body)
    chapter1_seen = False
    body_sect = None
    for child in children:
        if child.tag == wtag("p") and text_of(child).strip().startswith("第1章"):
            chapter1_seen = True
        if not chapter1_seen:
            continue
        sect = None
        if child.tag == wtag("p"):
            sect = child.find("w:pPr/w:sectPr", NS)
        elif child.tag == wtag("sectPr"):
            sect = child
        if sect is not None:
            body_sect = sect
            break
    if body_sect is not None:
        for old in body_sect.findall("w:pgNumType", NS):
            body_sect.remove(old)
        pg = ET.SubElement(body_sect, wtag("pgNumType"))
        pg.set(wtag("fmt"), "decimal")
        pg.set(wtag("start"), "1")

    # Later postscript sections should continue Arabic numbering instead of restarting.
    if body_sect is not None:
        passed = False
        for child in children:
            sect = None
            if child.tag == wtag("p"):
                sect = child.find("w:pPr/w:sectPr", NS)
            elif child.tag == wtag("sectPr"):
                sect = child
            if sect is None:
                continue
            if sect is body_sect:
                passed = True
                continue
            if not passed:
                continue
            for old in sect.findall("w:pgNumType", NS):
                sect.remove(old)


def main() -> None:
    source = Path("苏绍俊毕业论文最新.docx")
    if not source.exists():
        candidates = [p for p in Path(".").glob("*.docx") if not p.name.startswith("~$")]
        source = max(candidates, key=lambda p: p.stat().st_mtime)
    output = source.with_name(source.stem + "_格式修正.docx")

    tmp = Path("_tmp_heu_format_fix")
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

    replace_text_nodes(root)
    move_table_captions_above(body)
    add_superscript_to_citations(body)
    add_chapter_summaries(body)
    fix_page_numbering_and_duplicate_keywords(body)
    fix_headers(tmp)

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
