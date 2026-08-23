import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

try:
    from PIL import Image
except Exception:
    Image = None


SRC = next(p for p in Path(".").glob("*.docx") if p.name != "thesis_experiment_update.docx")
OUT = Path("thesis_experiment_update.docx")

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
PIC_NS = "http://schemas.openxmlformats.org/drawingml/2006/picture"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"

ET.register_namespace("w", W_NS)
ET.register_namespace("r", R_NS)
ET.register_namespace("wp", WP_NS)
ET.register_namespace("a", A_NS)
ET.register_namespace("pic", PIC_NS)
ET.register_namespace("", REL_NS)


def q(ns, tag):
    return f"{{{ns}}}{tag}"


def w(tag):
    return q(W_NS, tag)


def set_attr(el, ns, key, val):
    el.set(q(ns, key), str(val))


def make_run(text, bold=False, size=21):
    r = ET.Element(w("r"))
    r_pr = ET.SubElement(r, w("rPr"))
    fonts = ET.SubElement(r_pr, w("rFonts"))
    set_attr(fonts, W_NS, "ascii", "Times New Roman")
    set_attr(fonts, W_NS, "eastAsia", "宋体")
    if bold:
        ET.SubElement(r_pr, w("b"))
    sz = ET.SubElement(r_pr, w("sz"))
    set_attr(sz, W_NS, "val", size)
    t = ET.SubElement(r, w("t"))
    if text.startswith(" ") or text.endswith(" "):
        set_attr(t, "http://www.w3.org/XML/1998/namespace", "space", "preserve")
    t.text = text
    return r


def make_paragraph(text="", style=None, align=None, bold=False, size=21):
    p = ET.Element(w("p"))
    p_pr = ET.SubElement(p, w("pPr"))
    if style:
        ps = ET.SubElement(p_pr, w("pStyle"))
        set_attr(ps, W_NS, "val", style)
    if align:
        jc = ET.SubElement(p_pr, w("jc"))
        set_attr(jc, W_NS, "val", align)
    spacing = ET.SubElement(p_pr, w("spacing"))
    set_attr(spacing, W_NS, "after", "120")
    set_attr(spacing, W_NS, "line", "360")
    set_attr(spacing, W_NS, "lineRule", "auto")
    if text:
        p.append(make_run(text, bold=bold, size=size))
    return p


def make_cell(text, width, bold=False, align="center"):
    tc = ET.Element(w("tc"))
    tc_pr = ET.SubElement(tc, w("tcPr"))
    tc_w = ET.SubElement(tc_pr, w("tcW"))
    set_attr(tc_w, W_NS, "w", width)
    set_attr(tc_w, W_NS, "type", "dxa")
    v_align = ET.SubElement(tc_pr, w("vAlign"))
    set_attr(v_align, W_NS, "val", "center")
    mar = ET.SubElement(tc_pr, w("tcMar"))
    for side in ["top", "left", "bottom", "right"]:
        m = ET.SubElement(mar, w(side))
        set_attr(m, W_NS, "w", "80")
        set_attr(m, W_NS, "type", "dxa")
    tc.append(make_paragraph(text, align=align, bold=bold, size=18))
    return tc


def make_table(rows, widths):
    tbl = ET.Element(w("tbl"))
    tbl_pr = ET.SubElement(tbl, w("tblPr"))
    tbl_w = ET.SubElement(tbl_pr, w("tblW"))
    set_attr(tbl_w, W_NS, "w", "0")
    set_attr(tbl_w, W_NS, "type", "auto")
    borders = ET.SubElement(tbl_pr, w("tblBorders"))
    for side in ["top", "left", "bottom", "right", "insideH", "insideV"]:
        b = ET.SubElement(borders, w(side))
        set_attr(b, W_NS, "val", "single")
        set_attr(b, W_NS, "sz", "4")
        set_attr(b, W_NS, "space", "0")
        set_attr(b, W_NS, "color", "808080")
    tbl_grid = ET.SubElement(tbl, w("tblGrid"))
    for width in widths:
        grid = ET.SubElement(tbl_grid, w("gridCol"))
        set_attr(grid, W_NS, "w", width)
    for ri, row in enumerate(rows):
        tr = ET.SubElement(tbl, w("tr"))
        if ri == 0:
            tr_pr = ET.SubElement(tr, w("trPr"))
            ET.SubElement(tr_pr, w("tblHeader"))
        for cell, width in zip(row, widths):
            tr.append(make_cell(str(cell), width, bold=(ri == 0)))
    return tbl


def make_image_paragraph(rid, filename, width_inches=5.75):
    if Image:
        with Image.open(filename) as im:
            px_w, px_h = im.size
    else:
        px_w, px_h = (1500, 760)
    cx = int(width_inches * 914400)
    cy = int(cx * px_h / px_w)

    p = ET.Element(w("p"))
    p_pr = ET.SubElement(p, w("pPr"))
    jc = ET.SubElement(p_pr, w("jc"))
    set_attr(jc, W_NS, "val", "center")
    r = ET.SubElement(p, w("r"))
    drawing = ET.SubElement(r, w("drawing"))
    inline = ET.SubElement(drawing, q(WP_NS, "inline"))
    extent = ET.SubElement(inline, q(WP_NS, "extent"))
    extent.set("cx", str(cx))
    extent.set("cy", str(cy))
    effect = ET.SubElement(inline, q(WP_NS, "effectExtent"))
    effect.set("l", "0")
    effect.set("t", "0")
    effect.set("r", "0")
    effect.set("b", "0")
    doc_pr = ET.SubElement(inline, q(WP_NS, "docPr"))
    doc_pr.set("id", rid.replace("rId", ""))
    doc_pr.set("name", Path(filename).stem)
    c_nv = ET.SubElement(inline, q(WP_NS, "cNvGraphicFramePr"))
    locks = ET.SubElement(c_nv, q(A_NS, "graphicFrameLocks"))
    locks.set("noChangeAspect", "1")
    graphic = ET.SubElement(inline, q(A_NS, "graphic"))
    graphic_data = ET.SubElement(graphic, q(A_NS, "graphicData"))
    graphic_data.set("uri", PIC_NS)
    pic = ET.SubElement(graphic_data, q(PIC_NS, "pic"))
    nv_pic_pr = ET.SubElement(pic, q(PIC_NS, "nvPicPr"))
    c_nv_pr = ET.SubElement(nv_pic_pr, q(PIC_NS, "cNvPr"))
    c_nv_pr.set("id", "0")
    c_nv_pr.set("name", Path(filename).name)
    ET.SubElement(nv_pic_pr, q(PIC_NS, "cNvPicPr"))
    blip_fill = ET.SubElement(pic, q(PIC_NS, "blipFill"))
    blip = ET.SubElement(blip_fill, q(A_NS, "blip"))
    blip.set(q(R_NS, "embed"), rid)
    stretch = ET.SubElement(blip_fill, q(A_NS, "stretch"))
    ET.SubElement(stretch, q(A_NS, "fillRect"))
    sp_pr = ET.SubElement(pic, q(PIC_NS, "spPr"))
    xfrm = ET.SubElement(sp_pr, q(A_NS, "xfrm"))
    off = ET.SubElement(xfrm, q(A_NS, "off"))
    off.set("x", "0")
    off.set("y", "0")
    ext = ET.SubElement(xfrm, q(A_NS, "ext"))
    ext.set("cx", str(cx))
    ext.set("cy", str(cy))
    geom = ET.SubElement(sp_pr, q(A_NS, "prstGeom"))
    geom.set("prst", "rect")
    ET.SubElement(geom, q(A_NS, "avLst"))
    return p


VAL_TABLE = [
    ["模型", "注意力", "损失函数", "P", "R", "mAP@0.5", "mAP@0.5:0.95"],
    ["Baseline", "无", "BCE", "0.9760", "0.9547", "0.9762", "0.5377"],
    ["SE", "SE", "BCE", "0.9870", "0.9636", "0.9809", "0.6195"],
    ["Focal", "无", "Focal", "0.9873", "0.9489", "0.9678", "0.6147"],
    ["SE+Focal", "SE", "Focal", "0.9912", "0.9428", "0.9716", "0.6614"],
]
TEST_TABLE = [
    ["模型", "P", "R", "mAP@0.5", "mAP@0.5:0.95", "主要说明"],
    ["Baseline", "0.995", "0.958", "0.975", "0.664", "基线模型已具备较高检测性能"],
    ["SE", "0.992", "0.966", "0.984", "0.663", "召回率和 mAP@0.5 略有提升"],
    ["Focal", "0.996", "0.947", "0.975", "0.666", "严格 IoU 下略高，但召回率下降"],
    ["SE+Focal", "0.988", "0.955", "0.981", "0.661", "整体稳定，但测试集提升幅度有限"],
]
COMPLEXITY_TABLE = [
    ["模型", "模型大小/MB", "参数量", "相对基线增加", "说明"],
    ["Baseline", "74.82", "37,207,344", "0", "原始 YOLOv7 基线"],
    ["SE", "75.49", "37,532,552", "+325,208", "增加约 0.87% 参数"],
    ["Focal", "74.82", "37,207,344", "0", "仅改变训练损失，不增加推理参数"],
    ["SE+Focal", "75.49", "37,532,552", "+325,208", "兼具注意力增强与损失重加权"],
]


def build_insert_blocks(add_image_rel):
    blocks = [
        make_paragraph(
            "为验证注意力机制与损失函数改进对模型性能的影响，本文在重新划分后的实验室安全检测数据集上设计了四组消融实验：原始 YOLOv7 基线模型、引入 SE 注意力机制的模型、采用 Focal Loss 的模型，以及同时引入 SE 注意力机制和 Focal Loss 的组合模型。四组实验均采用相同的数据集划分、输入尺寸和训练轮数，训练集、验证集和测试集分别包含 1252、300 和 254 张图像，类别包括火焰、人员和开发板。训练过程中输入图像尺寸设为 640×640，训练轮数为 100，batch size 设为 6。"
        ),
        make_paragraph("表3-1  消融实验验证集结果对比", align="center", bold=True),
        make_table(VAL_TABLE, [1300, 1050, 1200, 900, 900, 1200, 1500]),
        make_paragraph(
            "由表3-1可知，四组模型在 mAP@0.5 上均取得较高结果，说明各模型均能够较稳定地检测出实验室场景中的目标。相比之下，mAP@0.5:0.95 对预测框定位质量提出了更严格要求，因此更能反映模型边界框回归能力。基线模型的 mAP@0.5:0.95 为 0.5377，引入 SE 注意力机制后提升至 0.6195，采用 Focal Loss 后提升至 0.6147，二者结合后达到 0.6614，较基线模型提升 0.1237。该结果表明，SE 注意力机制能够增强关键通道特征表达，Focal Loss 能够缓解简单样本占主导导致的训练偏置，二者结合后对严格 IoU 条件下的定位性能改善最明显。"
        ),
        make_paragraph("表3-2  独立测试集检测结果对比", align="center", bold=True),
        make_table(TEST_TABLE, [1100, 800, 800, 1100, 1400, 2600]),
        make_paragraph(
            "为进一步检验模型泛化能力，本文使用独立测试集对各模型的 best.pt 权重进行评估，结果如表3-2所示。可以看出，各模型在测试集上均保持了较高的检测性能，说明模型对实验室场景具有较好的泛化能力。与验证集相比，测试集上各改进模型与基线模型之间的差距较小，说明改进方法在当前测试集规模下并未带来压倒性提升。因此，本文在结论中不将其表述为“显著全面优于基线模型”，而是认为 SE 注意力机制与 Focal Loss 对模型定位质量和整体稳定性具有一定促进作用。"
        ),
        make_paragraph("表3-3  模型大小与参数量对比", align="center", bold=True),
        make_table(COMPLEXITY_TABLE, [1100, 1300, 1500, 1400, 2600]),
        make_paragraph(
            "由表3-3可知，Focal Loss 仅作用于训练阶段，不改变网络结构，因此模型大小与参数量均与基线模型保持一致。引入 SE 注意力机制后，模型参数量由 37,207,344 增加至 37,532,552，增加 325,208 个参数，增幅约为 0.87%；模型大小由 74.82 MB 增加至 75.49 MB，仅增加约 0.67 MB。该结果说明 SE 模块属于轻量级结构改进，在带来验证集定位性能提升的同时，并未显著增加模型复杂度。"
        ),
    ]
    image_infos = [
        ("figures_clean/ablation_accuracy.png", "图3-1  消融实验检测精度对比"),
        ("figures_clean/ablation_loss.png", "图3-2  消融实验验证损失对比"),
        ("figures_clean/ablation_map50_summary.png", "图3-3  mAP@0.5 指标汇总对比"),
    ]
    for img, caption in image_infos:
        rid = add_image_rel(img)
        blocks.append(make_image_paragraph(rid, img))
        blocks.append(make_paragraph(caption, align="center", bold=True, size=19))
    blocks.append(
        make_paragraph(
            "图3-1展示了四组模型的综合检测精度对比。虽然各模型在 mAP@0.5 上差异较小，但在更严格的 mAP@0.5:0.95 指标上差距更为明显，说明改进方法主要提升了预测框的定位质量。图3-2展示了验证阶段的损失变化，其中采用 Focal Loss 的模型在目标置信度损失和分类损失上明显更低，这与 Focal Loss 降低易分类样本权重、强调困难样本学习的机制一致。需要注意的是，由于 BCE 与 Focal Loss 的函数形式和数值尺度不同，损失值不能单独作为模型优劣判断依据，应结合 mAP、Precision 和 Recall 等指标综合分析。图3-3进一步说明，各模型在宽松 IoU 阈值下均已具备较好的目标检出能力，而严格 IoU 指标更能体现改进方法的有效性。"
        )
    )
    return blocks, image_infos


with zipfile.ZipFile(SRC, "r") as zin:
    doc_xml = zin.read("word/document.xml")
    rels_xml = zin.read("word/_rels/document.xml.rels")
    ct_xml = zin.read("[Content_Types].xml")

doc_root = ET.fromstring(doc_xml)
body = doc_root.find(w("body"))
rels_root = ET.fromstring(rels_xml)
ct_root = ET.fromstring(ct_xml)
max_id = 0
for rel in rels_root.findall(q(REL_NS, "Relationship")):
    m = re.match(r"rId(\d+)$", rel.get("Id") or "")
    if m:
        max_id = max(max_id, int(m.group(1)))


def add_image_rel(image_path):
    global max_id
    max_id += 1
    rid = f"rId{max_id}"
    rel = ET.SubElement(rels_root, q(REL_NS, "Relationship"))
    rel.set("Id", rid)
    rel.set("Type", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image")
    rel.set("Target", f"media/{Path(image_path).name}")
    return rid


has_png = any(el.tag == q(CT_NS, "Default") and el.get("Extension") == "png" for el in ct_root)
if not has_png:
    default = ET.SubElement(ct_root, q(CT_NS, "Default"))
    default.set("Extension", "png")
    default.set("ContentType", "image/png")

insert_blocks, image_infos = build_insert_blocks(add_image_rel)
children = list(body)
insert_idx = None
for idx, child in enumerate(children):
    if child.tag == w("p"):
        text = "".join((t.text or "") for t in child.findall(".//" + w("t"))).strip()
        if text.startswith("3.4 "):
            insert_idx = idx
            break
if insert_idx is None:
    raise RuntimeError("Could not find 3.4 insertion point")

for offset, block in enumerate(insert_blocks):
    body.insert(insert_idx + offset, block)

if OUT.exists():
    OUT.unlink()
with zipfile.ZipFile(SRC, "r") as zin, zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zout:
    replacements = {
        "word/document.xml": ET.tostring(doc_root, encoding="utf-8", xml_declaration=True),
        "word/_rels/document.xml.rels": ET.tostring(rels_root, encoding="utf-8", xml_declaration=True),
        "[Content_Types].xml": ET.tostring(ct_root, encoding="utf-8", xml_declaration=True),
    }
    for item in zin.infolist():
        if item.filename in replacements:
            continue
        zout.writestr(item, zin.read(item.filename))
    for name, data in replacements.items():
        zout.writestr(name, data)
    for img, _ in image_infos:
        zout.write(img, f"word/media/{Path(img).name}")

print(OUT.resolve())
