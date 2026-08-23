import sys
from pathlib import Path

from PIL import Image, ImageDraw


out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("render_format_current")
pages = [int(x) for x in sys.argv[2:]] if len(sys.argv) > 2 else [1, 2, 3, 4, 5, 6, 7, 8, 20, 30, 40, 55]
thumbs = []
for n in pages:
    p = out / f"page-{n:03d}.png"
    image = Image.open(p).convert("RGB")
    image.thumbnail((240, 340))
    canvas = Image.new("RGB", (260, 380), "white")
    canvas.paste(image, ((260 - image.width) // 2, 10))
    ImageDraw.Draw(canvas).text((10, 350), p.name, fill="black")
    thumbs.append(canvas)

cols = 3
rows = (len(thumbs) + cols - 1) // cols
sheet = Image.new("RGB", (cols * 260, rows * 380), "white")
for i, image in enumerate(thumbs):
    sheet.paste(image, ((i % cols) * 260, (i // cols) * 380))

target = out / "format_contact.jpg"
sheet.save(target, quality=90)
print(target)
