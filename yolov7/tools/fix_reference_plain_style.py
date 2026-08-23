import os
import re
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


def text_of(el: ET.Element) -> str:
    return "".join(t.text or "" for t in el.findall(".//w:t", NS)).strip()


def child(parent: ET.Element, name: str) -> ET.Element:
    node = parent.find(f"w:{name}", NS)
    if node is None:
        node = ET.SubElement(parent, wtag(name))
    return node


def remove_all(parent: ET.Element, names: tuple[str, ...]) -> None:
    for name in names:
        for item in list(parent.findall(f"w:{name}", NS)):
            parent.remove(item)


def normalize_reference_paragraph(p: ET.Element) -> None:
    ppr = p.find("w:pPr", NS)
    if ppr is None:
        ppr = ET.Element(wtag("pPr"))
        p.insert(0, ppr)
    remove_all(ppr, ("pBdr", "shd", "rPr", "ind", "jc", "spacing"))

    spacing = ET.SubElement(ppr, wtag("spacing"))
    spacing.set(wtag("line"), "360")
    spacing.set(wtag("lineRule"), "auto")
    ind = ET.SubElement(ppr, wtag("ind"))
    ind.set(wtag("firstLine"), "0")
    ind.set(wtag("firstLineChars"), "0")
    jc = ET.SubElement(ppr, wtag("jc"))
    jc.set(wtag("val"), "left")

    for r in p.findall("w:r", NS):
        rpr = r.find("w:rPr", NS)
        if rpr is None:
            rpr = ET.Element(wtag("rPr"))
            r.insert(0, rpr)
        remove_all(rpr, ("b", "i", "color", "highlight", "shd", "vertAlign", "sz", "szCs", "rFonts"))
        fonts = ET.SubElement(rpr, wtag("rFonts"))
        fonts.set(wtag("eastAsia"), "\u5b8b\u4f53")
        fonts.set(wtag("ascii"), "Times New Roman")
        fonts.set(wtag("hAnsi"), "Times New Roman")
        size = ET.SubElement(rpr, wtag("sz"))
        size.set(wtag("val"), "21")
        size_cs = ET.SubElement(rpr, wtag("szCs"))
        size_cs.set(wtag("val"), "21")


def patch_docx(source: Path, output: Path) -> None:
    with zipfile.ZipFile(source, "r") as zin:
        root = ET.fromstring(zin.read("word/document.xml"))
        body = root.find(".//w:body", NS)
        if body is None:
            raise RuntimeError("Cannot find document body.")
        changed = 0
        for p in body.findall("w:p", NS):
            if re.match(r"^\[\d+\]", text_of(p)):
                normalize_reference_paragraph(p)
                changed += 1
        patched_document = ET.tostring(root, encoding="UTF-8", xml_declaration=True)

        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == "word/document.xml":
                    data = patched_document
                zout.writestr(item, data)
    print(f"source={source}")
    print(f"output={output}")
    print(f"references_normalized={changed}")


def main() -> None:
    candidates = [
        p
        for p in Path(".").glob("*.docx")
        if not p.name.startswith("~$") and "\u9875\u7801\u4fee\u6b63" in p.name
    ]
    if not candidates:
        candidates = [p for p in Path(".").glob("*.docx") if not p.name.startswith("~$")]
    source = max(candidates, key=lambda p: p.stat().st_mtime)
    output = source.with_name("\u82cf\u7ecd\u4fca\u6bd5\u4e1a\u8bba\u6587\u6700\u65b0_\u6700\u7ec8\u683c\u5f0f\u4fee\u6b63.docx")
    patch_docx(source, output)


if __name__ == "__main__":
    main()
