from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
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


def ensure_ppr(p: ET.Element) -> ET.Element:
    ppr = p.find("w:pPr", NS)
    if ppr is None:
        ppr = ET.Element(qn("pPr"))
        p.insert(0, ppr)
    return ppr


def set_spacing_before(p: ET.Element, before_twips: str) -> None:
    ppr = ensure_ppr(p)
    spacing = ppr.find("w:spacing", NS)
    if spacing is None:
        spacing = ET.SubElement(ppr, qn("spacing"))
    spacing.set(qn("before"), before_twips)


def set_page_break_before(p: ET.Element) -> None:
    ppr = ensure_ppr(p)
    if ppr.find("w:pageBreakBefore", NS) is None:
        ET.SubElement(ppr, qn("pageBreakBefore"))


def prepend_break(p: ET.Element, break_type: str | None = None) -> None:
    first_non_ppr = None
    for child in list(p):
        if child.tag != qn("pPr"):
            first_non_ppr = child
            break
    if first_non_ppr is not None:
        br = first_non_ppr.find("w:br", NS)
        if br is not None and (break_type is None or br.get(qn("type")) == break_type):
            return
    run = ET.Element(qn("r"))
    br = ET.SubElement(run, qn("br"))
    if break_type is not None:
        br.set(qn("type"), break_type)
    insert_at = 1 if p.find("w:pPr", NS) is not None else 0
    p.insert(insert_at, run)


def main() -> None:
    src = Path("thesis_full_polished.docx")
    out = Path("thesis_full_polished.docx")
    tmp = Path("~layout_fix.tmp.docx")
    shutil.copyfile(src, tmp)

    with ZipFile(tmp, "r") as zin:
        root = ET.fromstring(zin.read("word/document.xml"))
    paras = root.findall(".//w:body/w:p", NS)

    abstract_idx = next(i for i, p in enumerate(paras) if para_text(p) == "摘    要")
    conclusion_idx = next(i for i, p in enumerate(paras) if para_text(p) == "结    论")

    set_spacing_before(paras[abstract_idx], "720")
    spacing = ensure_ppr(paras[abstract_idx]).find("w:spacing", NS)
    if spacing is not None:
        spacing.attrib.pop(qn("beforeLines"), None)
    prepend_break(paras[abstract_idx])
    set_page_break_before(paras[conclusion_idx])
    prepend_break(paras[conclusion_idx], "page")

    new_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    with ZipFile(tmp, "r") as zin, ZipFile(out, "w", ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = new_xml if item.filename == "word/document.xml" else zin.read(item.filename)
            zout.writestr(item, data)

    tmp.unlink(missing_ok=True)
    print(out.resolve())


if __name__ == "__main__":
    main()
