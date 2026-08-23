# -*- coding: utf-8 -*-
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


DOCX = Path(sys.argv[1])
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
ET.register_namespace("w", W_NS)


def w(tag):
    return f"{{{W_NS}}}{tag}"


def para_text(p):
    return "".join((t.text or "") for t in p.findall(".//" + w("t"))).strip()


def set_para_text(p, value):
    p_pr = p.find(w("pPr"))
    for child in list(p):
        if child is not p_pr:
            p.remove(child)
    r = ET.SubElement(p, w("r"))
    r_pr = ET.SubElement(r, w("rPr"))
    fonts = ET.SubElement(r_pr, w("rFonts"))
    fonts.set(w("ascii"), "Times New Roman")
    fonts.set(w("hAnsi"), "Times New Roman")
    fonts.set(w("eastAsia"), "宋体")
    sz = ET.SubElement(r_pr, w("sz"))
    sz.set(w("val"), "21")
    t = ET.SubElement(r, w("t"))
    t.text = value


with zipfile.ZipFile(DOCX, "r") as zin:
    root = ET.fromstring(zin.read("word/document.xml"))

for idx, p in enumerate(root.findall(".//" + w("p"))):
    text = para_text(p)
    if idx < 150 and text.startswith("3.2.2 "):
        set_para_text(p, "3.2.2 面向小目标的损失函数改进3")

tmp = DOCX.with_suffix(".tmp.docx")
with zipfile.ZipFile(DOCX, "r") as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        if item.filename == "word/document.xml":
            zout.writestr(item, ET.tostring(root, encoding="utf-8", xml_declaration=True))
        else:
            zout.writestr(item, zin.read(item.filename))
tmp.replace(DOCX)
print(DOCX.resolve())
