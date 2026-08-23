"""
plot_ablation.py
读取 ablation_results.csv，生成两张对比图：
  1. 精度对比图（mAP@0.5 / mAP@0.5:0.95 / Precision / Recall 分组柱状图）
  2. 损失对比图（val_box / val_obj / val_cls 分组柱状图）

用法：
    python plot_ablation.py [--csv ablation_results.csv] [--out_dir figures]
"""

import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # 无 GUI 模式
import matplotlib.pyplot as plt
import numpy as np


def load_csv(csv_path: Path):
    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # 将数值字段转为 float（非数值保留字符串）
            converted = {}
            for k, v in row.items():
                try:
                    converted[k] = float(v)
                except ValueError:
                    converted[k] = v
            rows.append(converted)
    return rows


def grouped_bar(ax, data, metrics, labels, colors, title, ylabel):
    """在 ax 上绘制分组柱状图。
    data    : list of dicts, 每个 dict 对应一个实验
    metrics : list of str, 需要绘制的指标字段名
    labels  : 指标显示名称
    """
    n_exp = len(data)
    n_met = len(metrics)
    x = np.arange(n_exp)
    width = 0.8 / n_met

    for i, (metric, label, color) in enumerate(zip(metrics, labels, colors)):
        vals = [row.get(metric, 0) for row in data]
        offset = (i - n_met / 2 + 0.5) * width
        bars = ax.bar(x + offset, vals, width, label=label, color=color, alpha=0.85)
        # 在柱顶标注数值
        for bar, v in zip(bars, vals):
            if isinstance(v, (int, float)):
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + 0.002,
                        f"{v:.3f}",
                        ha="center", va="bottom", fontsize=7)

    exp_names = [row.get("experiment", f"exp{i}") for i, row in enumerate(data)]
    # 简化实验名称显示
    exp_names = [n.replace("ablation_", "") for n in exp_names]

    ax.set_xticks(x)
    ax.set_xticklabels(exp_names, rotation=15, ha="right")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend(loc="lower right", fontsize=8)
    ax.set_ylim(0, 1.05)
    ax.grid(axis="y", linestyle="--", alpha=0.4)


def main():
    parser = argparse.ArgumentParser(description="Plot ablation experiment results")
    parser.add_argument("--csv",     type=str, default="ablation_results.csv",
                        help="Path to ablation_results.csv")
    parser.add_argument("--out_dir", type=str, default="figures",
                        help="Directory to save output figures")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"[ERROR] {csv_path} not found. Run eval_ablation.py first.")
        return

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    data = load_csv(csv_path)
    if not data:
        print("[ERROR] CSV is empty.")
        return

    # ── 图 1：精度对比 ─────────────────────────────────────────
    fig1, ax1 = plt.subplots(figsize=(10, 5))
    grouped_bar(
        ax=ax1,
        data=data,
        metrics=["mAP@0.5", "mAP@0.5:0.95", "P", "R"],
        labels=["mAP@0.5", "mAP@0.5:0.95", "Precision", "Recall"],
        colors=["#4C72B0", "#DD8452", "#55A868", "#C44E52"],
        title="Ablation: Detection Accuracy Comparison",
        ylabel="Score",
    )
    fig1.tight_layout()
    out1 = out_dir / "ablation_accuracy.png"
    fig1.savefig(out1, dpi=150)
    print(f"Saved: {out1.resolve()}")

    # ── 图 2：验证损失对比 ──────────────────────────────────────
    fig2, ax2 = plt.subplots(figsize=(10, 5))
    # 损失值通常在 0~0.2 范围，调整 ylim
    data_loss = data
    metrics_loss = ["val_box_loss", "val_obj_loss", "val_cls_loss"]
    n_exp = len(data_loss)
    n_met = len(metrics_loss)
    x = np.arange(n_exp)
    width = 0.8 / n_met
    colors_loss = ["#8172B2", "#937860", "#DA8BC3"]
    labels_loss = ["Box Loss", "Obj Loss", "Cls Loss"]

    max_val = 0.0
    for i, (metric, label, color) in enumerate(zip(metrics_loss, labels_loss, colors_loss)):
        vals = [row.get(metric, 0) for row in data_loss]
        offset = (i - n_met / 2 + 0.5) * width
        bars = ax2.bar(x + offset, vals, width, label=label, color=color, alpha=0.85)
        max_val = max(max_val, max(v for v in vals if isinstance(v, float)))
        for bar, v in zip(bars, vals):
            if isinstance(v, (int, float)):
                ax2.text(bar.get_x() + bar.get_width() / 2,
                         bar.get_height() + max_val * 0.01,
                         f"{v:.3f}",
                         ha="center", va="bottom", fontsize=7)

    exp_names = [row.get("experiment", f"exp{i}").replace("ablation_", "")
                 for i, row in enumerate(data_loss)]
    ax2.set_xticks(x)
    ax2.set_xticklabels(exp_names, rotation=15, ha="right")
    ax2.set_ylabel("Loss")
    ax2.set_title("Ablation: Validation Loss Comparison")
    ax2.legend(loc="upper right", fontsize=8)
    ax2.set_ylim(0, max_val * 1.2 + 0.01)
    ax2.grid(axis="y", linestyle="--", alpha=0.4)

    fig2.tight_layout()
    out2 = out_dir / "ablation_loss.png"
    fig2.savefig(out2, dpi=150)
    print(f"Saved: {out2.resolve()}")

    # ── 图 3：mAP@0.5 单指标汇总水平条形图 ─────────────────────
    fig3, ax3 = plt.subplots(figsize=(8, 4))
    exp_names_short = [row.get("experiment", "").replace("ablation_", "") for row in data]
    map50_vals = [row.get("mAP@0.5", 0) for row in data]
    colors_bar = ["#4C72B0", "#55A868", "#DD8452", "#C44E52"]
    bars = ax3.barh(exp_names_short, map50_vals,
                    color=colors_bar[:len(data)], alpha=0.85)
    for bar, v in zip(bars, map50_vals):
        ax3.text(v + 0.002, bar.get_y() + bar.get_height() / 2,
                 f"{v:.4f}", va="center", fontsize=9)
    ax3.set_xlabel("mAP@0.5")
    ax3.set_title("Ablation: mAP@0.5 Summary")
    ax3.set_xlim(0, 1.05)
    ax3.grid(axis="x", linestyle="--", alpha=0.4)
    fig3.tight_layout()
    out3 = out_dir / "ablation_map50_summary.png"
    fig3.savefig(out3, dpi=150)
    print(f"Saved: {out3.resolve()}")

    print(f"\nAll figures saved in: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
