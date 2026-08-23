import copy
import os
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

NS = {"w": W_NS, "r": R_NS, "pr": PKG_REL_NS}

ET.register_namespace("w", W_NS)
ET.register_namespace("r", R_NS)
ET.register_namespace("wp", "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing")
ET.register_namespace("a", "http://schemas.openxmlformats.org/drawingml/2006/main")
ET.register_namespace("pic", "http://schemas.openxmlformats.org/drawingml/2006/picture")
ET.register_namespace("w14", "http://schemas.microsoft.com/office/word/2010/wordml")
ET.register_namespace("w15", "http://schemas.microsoft.com/office/word/2012/wordml")
ET.register_namespace("mc", "http://schemas.openxmlformats.org/markup-compatibility/2006")


def wtag(name: str) -> str:
    return f"{{{W_NS}}}{name}"


def rtag(name: str) -> str:
    return f"{{{R_NS}}}{name}"


def text_of(el: ET.Element) -> str:
    return "".join(t.text or "" for t in el.findall(".//w:t", NS)).strip()


def ensure_page_num(sect: ET.Element, fmt: str | None = None, start: str | None = None) -> None:
    for old in sect.findall("w:pgNumType", NS):
        sect.remove(old)
    pg = ET.SubElement(sect, wtag("pgNumType"))
    if fmt:
        pg.set(wtag("fmt"), fmt)
    if start:
        pg.set(wtag("start"), start)


def ensure_type(sect: ET.Element, value: str) -> None:
    typ = sect.find("w:type", NS)
    if typ is None:
        typ = ET.Element(wtag("type"))
        sect.insert(0, typ)
    typ.set(wtag("val"), value)


def ensure_footer_refs(sect: ET.Element, rid: str) -> None:
    for old in list(sect.findall("w:footerReference", NS)):
        sect.remove(old)
    first_non_header_footer = 0
    for i, child in enumerate(list(sect)):
        if child.tag not in (wtag("headerReference"), wtag("footerReference")):
            first_non_header_footer = i
            break
    else:
        first_non_header_footer = len(list(sect))

    for typ in ("default", "even"):
        ref = ET.Element(wtag("footerReference"))
        ref.set(rtag("id"), rid)
        ref.set(wtag("type"), typ)
        sect.insert(first_non_header_footer, ref)
        first_non_header_footer += 1


def sect_pr_of(child: ET.Element) -> ET.Element | None:
    if child.tag == wtag("p"):
        return child.find("w:pPr/w:sectPr", NS)
    if child.tag == wtag("sectPr"):
        return child
    return None


def find_page_field_footer_rid(zf: zipfile.ZipFile) -> str:
    rels = ET.fromstring(zf.read("word/_rels/document.xml.rels"))
    for rel in rels:
        rid = rel.attrib.get("Id")
        target = rel.attrib.get("Target", "")
        if not rid or not re.fullmatch(r"footer\d+\.xml", target):
            continue
        footer = ET.fromstring(zf.read("word/" + target))
        instr = " ".join(i.text or "" for i in footer.findall(".//w:instrText", NS))
        if "PAGE" in instr:
            return rid
    raise RuntimeError("No footer with PAGE field found.")


def footer_target_for_rid(zf: zipfile.ZipFile, rid: str) -> str | None:
    rels = ET.fromstring(zf.read("word/_rels/document.xml.rels"))
    for rel in rels:
        if rel.attrib.get("Id") == rid:
            return rel.attrib.get("Target")
    return None


def make_roman_page_footer(footer_xml: bytes, fallback: str = "III") -> bytes:
    root = ET.fromstring(footer_xml)
    p = root.find(".//w:p", NS)
    if p is None:
        p = ET.SubElement(root, wtag("p"))
    ppr = p.find("w:pPr", NS)
    ppr_copy = copy.deepcopy(ppr) if ppr is not None else None
    for child in list(p):
        p.remove(child)
    if ppr_copy is not None:
        p.append(ppr_copy)
    begin = ET.SubElement(ET.SubElement(p, wtag("r")), wtag("fldChar"))
    begin.set(wtag("fldCharType"), "begin")
    instr_r = ET.SubElement(p, wtag("r"))
    instr = ET.SubElement(instr_r, wtag("instrText"))
    instr.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    instr.text = r"PAGE \* ROMAN"
    sep = ET.SubElement(ET.SubElement(p, wtag("r")), wtag("fldChar"))
    sep.set(wtag("fldCharType"), "separate")
    text_r = ET.SubElement(p, wtag("r"))
    text = ET.SubElement(text_r, wtag("t"))
    text.text = fallback
    end = ET.SubElement(ET.SubElement(p, wtag("r")), wtag("fldChar"))
    end.set(wtag("fldCharType"), "end")
    return ET.tostring(root, encoding="UTF-8", xml_declaration=True)


def update_fields_setting(settings_xml: bytes | None) -> bytes | None:
    if settings_xml is None:
        return None
    root = ET.fromstring(settings_xml)
    update = root.find("w:updateFields", NS)
    if update is None:
        update = ET.Element(wtag("updateFields"))
        root.insert(0, update)
    update.set(wtag("val"), "true")
    return ET.tostring(root, encoding="UTF-8", xml_declaration=True)


def patch_docx(source: Path, output: Path) -> None:
    with zipfile.ZipFile(source, "r") as zin:
        page_footer_rid = find_page_field_footer_rid(zin)
        doc_root = ET.fromstring(zin.read("word/document.xml"))
        body = doc_root.find(".//w:body", NS)
        if body is None:
            raise RuntimeError("Cannot find document body.")

        children = list(body)
        chapter1_idx = None
        for i, child in enumerate(children):
            if child.tag == wtag("p") and text_of(child).startswith("\u7b2c1\u7ae0"):
                chapter1_idx = i
                break
        if chapter1_idx is None:
            raise RuntimeError("Cannot find Chapter 1 heading.")

        previous_sect = None
        for child in children[:chapter1_idx]:
            sect = sect_pr_of(child)
            if sect is not None:
                previous_sect = sect
        if previous_sect is None:
            raise RuntimeError("Cannot find preceding front-matter section.")
        roman_footer_target = None
        for footer_ref in previous_sect.findall("w:footerReference", NS):
            rid = footer_ref.get(rtag("id"))
            roman_footer_target = footer_target_for_rid(zin, rid) if rid else None
            if roman_footer_target:
                break

        has_break_before_chapter = False
        if chapter1_idx > 0:
            prev_child = children[chapter1_idx - 1]
            has_break_before_chapter = prev_child.tag == wtag("p") and sect_pr_of(prev_child) is not None and not text_of(prev_child)

        if not has_break_before_chapter:
            break_p = ET.Element(wtag("p"))
            ppr = ET.SubElement(break_p, wtag("pPr"))
            toc_sect = copy.deepcopy(previous_sect)
            ensure_type(toc_sect, "continuous")
            ensure_page_num(toc_sect, fmt="upperRoman")
            ensure_footer_refs(toc_sect, page_footer_rid)
            ppr.append(toc_sect)
            body.insert(chapter1_idx, break_p)
            chapter1_idx += 1
            children = list(body)

        body_sect = None
        for child in children[chapter1_idx + 1 :]:
            sect = sect_pr_of(child)
            if sect is not None:
                body_sect = sect
                break
        if body_sect is None:
            body_sect = body.find("w:sectPr", NS)
        if body_sect is None:
            raise RuntimeError("Cannot find body section.")
        ensure_page_num(body_sect, fmt="decimal", start="1")
        ensure_footer_refs(body_sect, page_footer_rid)

        passed_body = False
        for child in children:
            sect = sect_pr_of(child)
            if sect is None:
                continue
            if sect is body_sect:
                passed_body = True
                continue
            if passed_body:
                for old in sect.findall("w:pgNumType", NS):
                    sect.remove(old)

        patched_document = ET.tostring(doc_root, encoding="UTF-8", xml_declaration=True)
        settings_xml = zin.read("word/settings.xml") if "word/settings.xml" in zin.namelist() else None
        patched_settings = update_fields_setting(settings_xml)
        patched_roman_footer = None
        roman_footer_name = "word/" + roman_footer_target if roman_footer_target else None
        if roman_footer_name and roman_footer_name in zin.namelist():
            patched_roman_footer = make_roman_page_footer(zin.read(roman_footer_name))

        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == "word/document.xml":
                    data = patched_document
                elif item.filename == "word/settings.xml" and patched_settings is not None:
                    data = patched_settings
                elif item.filename == roman_footer_name and patched_roman_footer is not None:
                    data = patched_roman_footer
                zout.writestr(item, data)


def main() -> None:
    candidates = [
        p
        for p in Path(".").glob("*.docx")
        if not p.name.startswith("~$")
        and p.name.endswith("_\u683c\u5f0f\u4fee\u6b63.docx")
    ]
    if not candidates:
        candidates = [p for p in Path(".").glob("*.docx") if not p.name.startswith("~$")]
    source = max(candidates, key=lambda p: p.stat().st_mtime)
    output = source.with_name(source.stem + "_\u9875\u7801\u4fee\u6b63.docx")
    patch_docx(source, output)
    print(f"source={source}")
    print(f"output={output}")


if __name__ == "__main__":
    main()
