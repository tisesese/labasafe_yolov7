"""
eval_ablation.py
读取四组消融实验的 runs/train/ablation_*/results.txt，
提取最佳 epoch 指标并写入 ablation_results.csv。

用法：
    python eval_ablation.py [--runs_dir runs/train] [--output ablation_results.csv]
"""

import argparse
import csv
import os
import re
import time
from pathlib import Path

import numpy as np


# ─────────────────────────── 实验配置 ───────────────────────────
PRESETS = {
    "run1": [
    {"name": "ablation_baseline_run1", "attention": "none",  "loss": "bce"},
    {"name": "ablation_se_run1",       "attention": "se",    "loss": "bce"},
    {"name": "ablation_focal_run1",    "attention": "none",  "loss": "focal"},
    {"name": "ablation_se_focal_run1", "attention": "se",    "loss": "focal"},
    ],
    "clean": [
        {"name": "ablation_clean_baseline_full", "attention": "none",  "loss": "bce"},
        {"name": "ablation_clean_se_full",       "attention": "se",    "loss": "bce"},
        {"name": "ablation_clean_focal_full",    "attention": "none",  "loss": "focal"},
        {"name": "ablation_clean_se_focal_full", "attention": "se",    "loss": "focal"},
    ],
}

CSV_HEADER = [
    "experiment", "attention", "loss",
    "best_epoch",
    "P", "R", "mAP@0.5", "mAP@0.5:0.95",
    "val_box_loss", "val_obj_loss", "val_cls_loss",
    "model_size_MB",
]


def parse_results_txt(results_txt: Path):
    """解析 results.txt，返回各 epoch 的指标矩阵。
    列顺序（每行 7 个值，空格分隔）：
        P  R  mAP@.5  mAP@.5:.95  val_box  val_ob j  val_cls
    """
    rows = []
    with open(results_txt, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # 取行末的数字字段（过滤掉前面的 epoch/mem 字符串）
            nums = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", line)
            if len(nums) >= 7:
                rows.append([float(x) for x in nums[-7:]])
    return np.array(rows) if rows else None


def best_row(data: np.ndarray):
    """以 mAP@0.5（第 3 列，index 2）为准取最佳 epoch。"""
    best_idx = int(np.argmax(data[:, 2]))
    return best_idx + 1, data[best_idx]  # (1-based epoch, values)


def model_size_mb(weights_path: Path):
    if weights_path.exists():
        return round(weights_path.stat().st_size / 1e6, 2)
    return "N/A"


def main():
    parser = argparse.ArgumentParser(description="Collect ablation experiment results")
    parser.add_argument("--runs_dir", type=str, default="runs/train",
                        help="Directory containing ablation_* experiment folders")
    parser.add_argument("--output", type=str, default="ablation_results.csv",
                        help="Output CSV file path")
    parser.add_argument("--preset", type=str, default="run1", choices=sorted(PRESETS),
                        help="Experiment name preset to collect")
    args = parser.parse_args()

    runs_dir = Path(args.runs_dir)
    rows = []

    for exp in PRESETS[args.preset]:
        exp_dir = runs_dir / exp["name"]
        results_txt = exp_dir / "results.txt"

        if not results_txt.exists():
            print(f"[WARN] {results_txt} not found, skipping {exp['name']}")
            continue

        data = parse_results_txt(results_txt)
        if data is None or len(data) == 0:
            print(f"[WARN] No data in {results_txt}, skipping")
            continue

        ep, vals = best_row(data)
        p, r, map50, map5095, vbox, vobj, vcls = vals

        best_weights = exp_dir / "weights" / "best.pt"
        size_mb = model_size_mb(best_weights)

        rows.append({
            "experiment":      exp["name"],
            "attention":       exp["attention"],
            "loss":            exp["loss"],
            "best_epoch":      ep,
            "P":               round(p, 4),
            "R":               round(r, 4),
            "mAP@0.5":         round(map50, 4),
            "mAP@0.5:0.95":    round(map5095, 4),
            "val_box_loss":    round(vbox, 4),
            "val_obj_loss":    round(vobj, 4),
            "val_cls_loss":    round(vcls, 4),
            "model_size_MB":   size_mb,
        })
        print(f"[OK]  {exp['name']:25s}  mAP@0.5={map50:.4f}  mAP@0.5:0.95={map5095:.4f}  epoch={ep}")

    if not rows:
        print("[ERROR] No experiment results found. Have you run run_ablation.bat first?")
        return

    output = Path(args.output)
    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADER)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nResults saved to: {output.resolve()}")


if __name__ == "__main__":
    main()
