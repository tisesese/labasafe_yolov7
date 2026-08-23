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


def replace_text(p, old, new):
    for t in p.findall(".//" + w("t")):
        if t.text and old in t.text:
            t.text = t.text.replace(old, new)


with zipfile.ZipFile(DOCX, "r") as zin:
    root = ET.fromstring(zin.read("word/document.xml"))

for p in root.findall(".//" + w("p")):
    text = para_text(p)
    if text.startswith("3.2.2 损失函数改进"):
        replace_text(p, "损失函数改进", "面向小目标的损失函数改进")

tmp = DOCX.with_suffix(".tmp.docx")
if tmp.exists():
    tmp.unlink()
with zipfile.ZipFile(DOCX, "r") as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        if item.filename == "word/document.xml":
            zout.writestr(item, ET.tostring(root, encoding="utf-8", xml_declaration=True))
        else:
            zout.writestr(item, zin.read(item.filename))
tmp.replace(DOCX)
print(DOCX.resolve())
