# -*- coding: utf-8 -*-
import copy
import os
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


def set_paragraph_text(p: ET.Element, text: str) -> None:
    ppr = p.find("w:pPr", NS)
    ppr_copy = copy.deepcopy(ppr) if ppr is not None else None
    for child in list(p):
        p.remove(child)
    if ppr_copy is not None:
        p.append(ppr_copy)
    r = ET.SubElement(p, wtag("r"))
    t = ET.SubElement(r, wtag("t"))
    t.text = text


def make_paragraph(text: str, template: ET.Element) -> ET.Element:
    p = ET.Element(wtag("p"))
    ppr = template.find("w:pPr", NS)
    if ppr is not None:
        p.append(copy.deepcopy(ppr))
    r = ET.SubElement(p, wtag("r"))
    t = ET.SubElement(r, wtag("t"))
    t.text = text
    return p


NEW_PARAS = [
    "上位机界面是边缘端检测结果面向用户呈现的主要入口，其设计目标不是替代底层推理程序，而是在不影响模型实时运行的前提下，完成输入源选择、检测模式切换、状态显示和告警提示等交互功能。根据系统部署环境和板端资源条件，本文采用 Python Tkinter 构建轻量级桌面界面，并结合 OpenCV 完成视频帧读取、目标框绘制和图像格式转换，从而降低界面对运行环境的依赖，便于在 Atlas 200I DK A2 开发板上直接运行与调试。",
    "界面程序的主入口由 app_main.py 调用 ui_app_main.py 中的 run_gui 函数完成。主界面采用固定区域布局，左侧为控制面板，提供 Camera、Video 和 Image 三种输入源选择方式，分别对应实时摄像头、本地视频文件和单张图片测试场景。用户确认输入源后，可在危险区域入侵告警、开发板数量清点和火灾火焰告警三种任务之间切换。中上方为系统状态区，用于显示当前检测模式、推理帧率、画面刷新帧率、开发板数量、危险区域入侵状态、火焰检测状态以及最近一次触发事件。右侧视频显示区用于呈现检测后的实时画面，包括目标边界框、类别标识和告警提示信息。系统人机交互界面布局如图4.8所示。",
    "为避免界面刷新与模型推理相互阻塞，系统采用“界面主线程 + 后台检测线程”的实现方式。Tkinter 主线程只负责响应用户操作和刷新界面控件，视频采集、模型加载、NPU 推理和告警状态计算均封装在 VideoWorker 后台对象中执行。后台线程通过 OpenCV 读取摄像头或视频帧，并调用 YOLOv7AscendInference 完成 AscendCL 模型推理；随后根据当前选择的任务模式，将检测结果分发至危险区域、开发板计数或火焰报警模块进行后处理。处理完成后的画面帧和状态信息分别写入 frame_queue 与 state_queue，主界面通过定时轮询方式取出最新数据并刷新显示。该设计将耗时的推理计算与界面事件循环解耦，保证了上位机在实时检测过程中仍能保持较好的响应性。",
    "在显示实现上，系统首先利用 OpenCV 在视频帧上绘制检测结果，再将 BGR 图像转换为 RGB 格式，并编码为 Tkinter 可显示的 PhotoImage 对象。对于危险区域入侵任务，界面会显示预设危险区域边界，当人员检测框与危险区域的重叠比例超过阈值时，目标框由普通状态切换为红色告警状态；对于开发板计数任务，界面实时显示当前识别到的开发板数量，当数量低于配置阈值时触发低库存提示；对于火灾检测任务，系统在检测到 fire 类目标时立即以红框标注火焰区域，并在状态栏显示火灾报警信息。三类任务均配有独立状态指示灯，指示灯仅在当前模式发生对应告警时闪烁，避免多任务信息混杂造成误判。",
    "此外，界面与业务逻辑之间保留了配置文件接口。系统从 system_config.json 中读取开发板数量阈值和危险区域重叠阈值，从 danger_zones.json 中读取危险区域坐标，并将危险区域入侵、开发板缺失和火灾告警分别记录到对应日志文件中。通过这种方式，界面层只负责交互与可视化，具体的目标检测、规则判断和日志记录由独立模块完成，增强了程序结构的可维护性。整体来看，该上位机界面在功能上满足了实验室安全监控的实时显示与人工交互需求，在实现上兼顾了板端部署的轻量化和系统运行的稳定性。",
]


def patch_docx(source: Path, output: Path) -> None:
    with zipfile.ZipFile(source, "r") as zin:
        root = ET.fromstring(zin.read("word/document.xml"))
        body = root.find(".//w:body", NS)
        if body is None:
            raise RuntimeError("Cannot find document body.")

        children = list(body)
        heading_idx = None
        for idx, child in enumerate(children):
            if child.tag == wtag("p") and text_of(child).startswith("4.3.4"):
                heading_idx = idx
                break
        if heading_idx is None:
            raise RuntimeError("Cannot find 4.3.4 heading.")

        heading = children[heading_idx]
        set_paragraph_text(heading, "4.3.4 人机交互界面设计与实现")

        normal_template = None
        for child in children[heading_idx + 1 :]:
            txt = text_of(child)
            if child.tag == wtag("p") and txt and not txt.startswith("图") and not txt.startswith("4.4"):
                normal_template = child
                break
        if normal_template is None:
            normal_template = heading

        # Remove old textual paragraphs in this subsection, but keep the figure paragraph and caption.
        idx = heading_idx + 1
        while idx < len(list(body)):
            child = list(body)[idx]
            txt = text_of(child)
            if txt.startswith("图4.8") or txt.startswith("4.4"):
                break
            if child.tag == wtag("p") and txt:
                body.remove(child)
                continue
            idx += 1

        insert_at = heading_idx + 1
        for para in reversed(NEW_PARAS):
            body.insert(insert_at, make_paragraph(para, normal_template))

        patched_document = ET.tostring(root, encoding="UTF-8", xml_declaration=True)
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == "word/document.xml":
                    data = patched_document
                zout.writestr(item, data)
    print(f"source={source}")
    print(f"output={output}")


def main() -> None:
    candidates = [
        p for p in Path(".").glob("苏绍俊毕业论文*.docx")
        if not p.name.startswith("~$") and "最终格式修正" in p.name
    ]
    if not candidates:
        candidates = [p for p in Path(".").glob("苏绍俊毕业论文*.docx") if not p.name.startswith("~$")]
    source = max(candidates, key=lambda p: p.stat().st_mtime)
    output = source.with_name("苏绍俊毕业论文最新_4.3.4人机交互界面更新.docx")
    patch_docx(source, output)


if __name__ == "__main__":
    main()
