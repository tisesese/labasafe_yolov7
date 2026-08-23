import os
import shutil
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageDraw


NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def main() -> None:
    files = [f for f in os.listdir(".") if f.lower().endswith(".docx")]
    source = max(files, key=lambda f: os.path.getmtime(f))
    out = Path("figure_extract_check")
    if out.exists():
        shutil.rmtree(out)
    out.mkdir()

    with zipfile.ZipFile(source) as z:
        document = ET.fromstring(z.read("word/document.xml"))
        rels = ET.fromstring(z.read("word/_rels/document.xml.rels"))
        relmap = {r.attrib["Id"]: r.attrib["Target"] for r in rels.findall("rel:Relationship", NS)}
        body = document.find(".//w:body", NS)
        images = []
        for idx, child in enumerate(list(body)):
            if not child.tag.endswith("}p"):
                continue
            text = "".join(t.text or "" for t in child.findall(".//w:t", NS)).strip()
            for blip in child.findall(".//a:blip", NS):
                rid = blip.attrib.get(f"{{{NS['r']}}}embed")
                if not rid or rid not in relmap:
                    continue
                target = relmap[rid]
                media_path = "word/" + target.lstrip("/") if not target.startswith("word/") else target
                ext = Path(media_path).suffix or ".png"
                number = len(images) + 1
                images.append((number, idx, media_path, text))
                (out / f"{number:02d}_body{idx}{ext}").write_bytes(z.read(media_path))

    print(f"doc={source}")
    print(f"images={len(images)}")
    for image in images:
        print(image)

    thumbs = []
    for file in sorted(out.glob("*")):
        if file.suffix.lower() not in [".png", ".jpg", ".jpeg", ".bmp"]:
            continue
        try:
            image = Image.open(file).convert("RGB")
        except Exception as exc:
            print(f"skip {file.name}: {exc}")
            continue
        image.thumbnail((260, 180))
        canvas = Image.new("RGB", (280, 220), "white")
        canvas.paste(image, ((280 - image.width) // 2, 10))
        draw = ImageDraw.Draw(canvas)
        draw.text((8, 190), file.name[:34], fill="black")
        thumbs.append(canvas)

    if thumbs:
        cols = 3
        rows = (len(thumbs) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * 280, rows * 220), "white")
        for i, image in enumerate(thumbs):
            sheet.paste(image, ((i % cols) * 280, (i // cols) * 220))
        sheet.save(out / "contact_sheet.jpg", quality=90)
        print(f"contact={out / 'contact_sheet.jpg'}")


if __name__ == "__main__":
    main()
