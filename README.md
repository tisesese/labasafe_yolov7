# 基于嵌入式的实验室视频监控系统的设计与实现

本项目面向华为 Ascend 边缘设备，使用 YOLOv7 实现实验室安全视频监控，包含危险区域入侵检测、板卡计数和火焰报警等功能。

## 目录结构

- `lab_detection_system/`：Ascend 部署端应用、系统配置和最终 `.om` 模型
- `yolov7/`：YOLOv7 训练、评估、导出及相关实验代码

## 快速开始

部署端的环境准备、模型转换、路径配置与启动方式请参阅 [`lab_detection_system/文档说明.md`](lab_detection_system/文档说明.md)。

```bash
cd lab_detection_system
python3 app_main.py
```

训练依赖请参阅 [`yolov7/requirements.txt`](yolov7/requirements.txt)，训练和实验说明请参阅 [`yolov7/文档说明.md`](yolov7/文档说明.md)。

## 未纳入 Git 的文件

为避免仓库体积过大，原始数据集、测试视频、虚拟环境、训练过程输出、PyTorch/ONNX 权重和压缩包未纳入仓库。部署所需的 `lab_detection_system/model/best_aipp_new.om` 已保留。

