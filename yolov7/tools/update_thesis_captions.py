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


def wtag(name: str) -> str:
    return f"{{{W_NS}}}{name}"


def paragraph_text(p: ET.Element) -> str:
    return "".join(t.text or "" for t in p.findall(".//w:t", NS))


def has_image(p: ET.Element) -> bool:
    return bool(p.findall(".//a:blip", NS)) or bool(p.findall(".//w:pict", NS))


def set_plain_paragraph(p: ET.Element, text: str) -> None:
    ppr = p.find("w:pPr", NS)
    preserved_ppr = copy.deepcopy(ppr) if ppr is not None else None
    for child in list(p):
        p.remove(child)
    if preserved_ppr is not None:
        p.append(preserved_ppr)
    run = ET.SubElement(p, wtag("r"))
    t = ET.SubElement(run, wtag("t"))
    t.text = text


def clear_text_in_image_paragraph(p: ET.Element) -> None:
    for t in p.findall(".//w:t", NS):
        t.text = ""


def replace_text(p: ET.Element, replacements: list[tuple[str, str]]) -> bool:
    old = paragraph_text(p)
    new = old
    for src, dst in replacements:
        new = new.replace(src, dst)
    if new == old:
        return False
    nodes = p.findall(".//w:t", NS)
    if not nodes:
        return False
    nodes[0].text = new
    for node in nodes[1:]:
        node.text = ""
    return True


def next_nonempty_paragraph(children: list[ET.Element], start: int) -> ET.Element | None:
    for child in children[start + 1 :]:
        if not child.tag.endswith("}p"):
            if child.tag.endswith("}tbl"):
                return None
            continue
        text = paragraph_text(child).strip()
        if text:
            return child
    return None


def make_caption_paragraph(template: ET.Element | None, caption: str) -> ET.Element:
    p = ET.Element(wtag("p"))
    if template is not None:
        ppr = template.find("w:pPr", NS)
        if ppr is not None:
            p.append(copy.deepcopy(ppr))
    run = ET.SubElement(p, wtag("r"))
    t = ET.SubElement(run, wtag("t"))
    t.text = caption
    return p


def find_source() -> Path:
    preferred = Path("苏绍俊毕业论文最新_参考文献标注完善.docx")
    if preferred.exists():
        return preferred
    candidates = [p for p in Path(".").glob("*.docx") if "图表题注完善" not in p.name]
    if not candidates:
        raise FileNotFoundError("No source DOCX found.")
    return max(candidates, key=lambda p: p.stat().st_mtime)


FIGURE_CAPTIONS = {
    1: ("following", "图2-1 华为昇腾 Atlas 200I DK A2 开发者套件"),
    2: ("following", "图2-2 Atlas 200I DK A2 硬件系统框图"),
    3: ("following", "图2-3 常见视觉传感器方案对比"),
    4: ("following", "图2-4 Type-C 接口连接示意图"),
    5: ("following", "图2-5 宿主机与边缘端协同开发架构"),
    6: ("following", "图2-6 Atlas 200I DK A2 软件运行环境"),
    7: ("following", "图2-7 系统软件主流程"),
    8: ("following", "图3-1 YOLOv7 网络结构图"),
    9: ("image", "图3-2 实验室复杂背景下目标检测示例"),
    10: ("following", "图3-3 Baseline 模型训练结果曲线"),
    11: ("image", "图3-4 SE 模型训练结果曲线"),
    12: ("following", "图3-5 Focal Loss 模型训练结果曲线"),
    13: ("following", "图3-6 SE-Focal Loss 模型训练结果曲线"),
    14: ("following", "图3-7 消融实验检测精度对比"),
    15: ("following", "图3-8 消融实验验证损失对比"),
    16: ("image", "图3-9 mAP@0.5 指标汇总对比"),
    17: ("following", "图4-1 AMCT 部署场景架构"),
    18: ("following", "图4-2 Ascend EP 部署架构"),
    19: ("following", "图4-3 ATC 工具功能架构"),
    20: ("following", "图4-4 模型部署流程"),
    21: ("following", "图4-5 AMCT 量化运行流程"),
    22: ("following", "图4-6 训练后量化参数校准原理"),
    23: ("image", "图4-7 量化前后模型大小对比"),
    24: ("following", "图4-8 系统人机交互界面布局"),
    25: ("image", "图5-1 危险区域入侵正常监控状态"),
    26: ("following", "图5-2 危险区域边缘抗扰过滤状态"),
    27: ("image", "图5-3 危险区域越界告警触发状态"),
    28: ("following", "图5-4 开发板正常余量状态"),
    29: ("following", "图5-5 开发板缺失告警触发状态"),
    30: ("image", "图5-6 复杂背景下火焰检测效果一"),
    31: ("following", "图5-7 复杂背景下火焰检测效果二"),
    32: ("following", "图6-1 实验室监控系统实地运行场景"),
}


TABLE_CAPTIONS = {
    1: "表3-1 数据集划分与类别分布",
    2: "表3-2 消融实验验证集结果对比",
    3: "表3-3 独立测试集检测结果对比",
    4: "表3-4 模型大小与参数量对比",
    5: "表5-1 实验环境配置",
}


CONTEXT_REPLACEMENTS = [
    ("Atlas 200I DK A2 硬件系统以", [("如图 2 所示", "如图2-2所示")]),
    ("交叉开发拓扑结构", [("如图 2-A 的物理连接与图 2-B 的交叉开发拓扑结构所示", "如图2-4的物理连接与图2-5的交叉开发拓扑结构所示")]),
    ("宿主机主要承担视觉算法", [("如图 2-B 左侧所示", "如图2-5左侧所示")]),
    ("运行环境与软件栈配置", [("如图 2-C 所示", "如图2-6所示")]),
    ("最小化依赖", [("如图 2-B 右侧所示", "如图2-5右侧所示")]),
    ("系统的软件主流程", [("系统的软件主流程如图 2 所示", "系统的软件主流程如图2-7所示")]),
    ("四组模型在 Precision", [("图3-1展示", "图3-7展示"), ("图3-2展示", "图3-8展示"), ("图3-3进一步", "图3-9进一步")]),
    ("功能架构如图1所示", [("如图1所示", "如图4-3所示")]),
    ("AMCT将量化和模型转换分开", [("其运行原理如下图所示", "其运行原理如图4-5所示")]),
    ("离线计算出数据的量化参数", [("其原理如下图所示", "其原理如图4-6所示")]),
    ("主界面布局", [("如图 4所示", "如图4-8所示")]),
    ("正常监控状态", [("如图 5-X (a) 所示", "如图5-1所示")]),
    ("边缘抗扰过滤", [("如图 5-X (b) 所示", "如图5-2所示")]),
    ("越界告警触发", [("如图 5-X (c) 所示", "如图5-3所示")]),
    ("正常余量状态", [("如图 5-X (a) 所示", "如图5-4所示")]),
    ("资产缺失告警触发", [("如图 5-X (b) 所示", "如图5-5所示")]),
    ("复杂背景下的微小火情检测", [("如图 5-X (a) 和图 5-X (b) 所示", "如图5-6和图5-7所示")]),
]


def main() -> None:
    source = find_source()
    output = source.with_name(source.stem + "_图表题注完善.docx")
    tmp = Path("_tmp_thesis_caption_edit")
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

    children = list(body)
    figure_count = 0
    caption_template = None
    main_start_index = 0
    for i, child in enumerate(children):
        if child.tag.endswith("}p") and paragraph_text(child).strip().startswith("第2章"):
            main_start_index = i
            break

    for child in children:
        if child.tag.endswith("}p") and paragraph_text(child).strip().startswith("图"):
            caption_template = child
            break

    image_items = [
        (idx, child)
        for idx, child in enumerate(children)
        if idx >= main_start_index and child.tag.endswith("}p") and has_image(child)
    ]
    figure_count = len(image_items)
    for figure_no, (_, child) in reversed(list(enumerate(image_items, start=1))):
        if figure_no not in FIGURE_CAPTIONS:
            continue
        mode, caption = FIGURE_CAPTIONS[figure_no]
        current_children = list(body)
        current_idx = current_children.index(child)
        if mode == "image":
            clear_text_in_image_paragraph(child)
            body.insert(current_idx + 1, make_caption_paragraph(caption_template, caption))
        else:
            target = next_nonempty_paragraph(current_children, current_idx)
            if target is not None and paragraph_text(target).strip().startswith("图"):
                set_plain_paragraph(target, caption)
            else:
                body.insert(current_idx + 1, make_caption_paragraph(caption_template, caption))

    children = list(body)
    table_count = 0
    table_caption_template = None
    for child in children:
        if child.tag.endswith("}p") and paragraph_text(child).strip().startswith("表"):
            table_caption_template = child
            break

    for idx, child in enumerate(list(body)):
        if not child.tag.endswith("}tbl"):
            continue
        # Skip signature tables before the main text; the first real data table starts after Chapter 3.
        flat_text = " ".join(t.text or "" for t in child.findall(".//w:t", NS))
        if "作者签名" in flat_text or "导师签名" in flat_text:
            continue
        table_count += 1
        caption = TABLE_CAPTIONS.get(table_count)
        if not caption:
            continue
        current_children = list(body)
        target = next_nonempty_paragraph(current_children, current_children.index(child))
        immediate_next = current_children[current_children.index(child) + 1] if current_children.index(child) + 1 < len(current_children) else None
        if target is not None and paragraph_text(target).strip().startswith("表"):
            set_plain_paragraph(target, caption)
        elif immediate_next is not None and immediate_next.tag.endswith("}p") and not paragraph_text(immediate_next).strip():
            set_plain_paragraph(immediate_next, caption)
        else:
            body.insert(current_children.index(child) + 1, make_caption_paragraph(table_caption_template, caption))

    for p in body.findall("w:p", NS):
        text = paragraph_text(p)
        if not text:
            continue
        for keyword, replacements in CONTEXT_REPLACEMENTS:
            if keyword in text:
                replace_text(p, replacements)
                break

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
    print(f"figures={figure_count}")
    print(f"tables={table_count}")


if __name__ == "__main__":
    main()
