import argparse
import hashlib
import json
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def parse_key(path: Path):
    match = re.search(r"^(.*?)(\d+)$", path.stem)
    if match:
        prefix, number = match.groups()
        return prefix, int(number), path.name
    return path.stem, -1, path.name


def file_md5(path: Path):
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_label_counts(label_path: Path):
    counts = Counter()
    with label_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            parts = line.strip().split()
            if parts:
                counts[parts[0]] += 1
    return counts


def collect_samples(src: Path):
    image_dir = src / "images"
    label_dir = src / "labels"
    samples = []
    skipped_images = []
    duplicate_images = []
    seen_hashes = {}

    for image_path in sorted(image_dir.iterdir(), key=parse_key):
        if not image_path.is_file() or image_path.suffix.lower() not in IMAGE_EXTS:
            continue

        label_path = label_dir / f"{image_path.stem}.txt"
        if not label_path.exists():
            skipped_images.append(image_path.name)
            continue

        digest = file_md5(image_path)
        if digest in seen_hashes:
            duplicate_images.append({"kept": seen_hashes[digest], "dropped": image_path.name})
            continue
        seen_hashes[digest] = image_path.name

        prefix, number, _ = parse_key(image_path)
        samples.append({
            "image": image_path,
            "label": label_path,
            "prefix": prefix,
            "number": number,
            "hash": digest,
            "classes": read_label_counts(label_path),
        })

    paired_stems = {p.stem for p in image_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS}
    orphan_labels = sorted(p.name for p in label_dir.glob("*.txt") if p.stem not in paired_stems)
    return samples, skipped_images, orphan_labels, duplicate_images


def make_chunks(samples, chunk_size):
    by_prefix = defaultdict(list)
    for sample in samples:
        by_prefix[sample["prefix"]].append(sample)

    chunks = []
    for prefix, items in sorted(by_prefix.items()):
        items = sorted(items, key=lambda x: (x["number"], x["image"].name))
        for i in range(0, len(items), chunk_size):
            chunk_items = items[i:i + chunk_size]
            counts = Counter()
            for item in chunk_items:
                counts.update(item["classes"])
            chunks.append({
                "prefix": prefix,
                "start": chunk_items[0]["number"],
                "end": chunk_items[-1]["number"],
                "samples": chunk_items,
                "classes": counts,
            })
    return chunks


def split_chunks(chunks, ratios):
    splits = {"train": [], "val": [], "test": []}
    cycle = ("train", "val", "test", "train", "train", "train", "train")

    by_prefix = defaultdict(list)
    for chunk in chunks:
        by_prefix[chunk["prefix"]].append(chunk)

    for prefix, prefix_chunks in sorted(by_prefix.items()):
        prefix_chunks = sorted(prefix_chunks, key=lambda c: (c["start"], c["end"]))
        for i, chunk in enumerate(prefix_chunks):
            splits[cycle[i % len(cycle)]].append(chunk)

    for split in splits:
        splits[split].sort(key=lambda c: (c["prefix"], c["start"]))
    return splits


def copy_split(splits, out: Path, names):
    out_abs = out.resolve()
    for split in ("train", "val", "test"):
        (out / "images" / split).mkdir(parents=True, exist_ok=True)
        (out / "labels" / split).mkdir(parents=True, exist_ok=True)
        for chunk in splits[split]:
            for sample in chunk["samples"]:
                shutil.copy2(sample["image"], out / "images" / split / sample["image"].name)
                shutil.copy2(sample["label"], out / "labels" / split / sample["label"].name)

    data_yaml = (
        f"train: {out_abs / 'images' / 'train'}\n"
        f"val: {out_abs / 'images' / 'val'}\n"
        f"test: {out_abs / 'images' / 'test'}\n\n"
        f"nc: {len(names)}\n"
        f"names: {names}\n"
    )
    (out / "data.yaml").write_text(data_yaml, encoding="utf-8")


def summarize(splits):
    summary = {}
    for split, chunks in splits.items():
        sample_count = sum(len(c["samples"]) for c in chunks)
        class_counts = Counter()
        for chunk in chunks:
            class_counts.update(chunk["classes"])
        summary[split] = {
            "images": sample_count,
            "objects": sum(class_counts.values()),
            "classes": dict(sorted(class_counts.items())),
            "chunks": [
                {
                    "prefix": c["prefix"],
                    "start": c["start"],
                    "end": c["end"],
                    "images": len(c["samples"]),
                    "classes": dict(sorted(c["classes"].items())),
                }
                for c in chunks
            ],
        }
    return summary


def main():
    parser = argparse.ArgumentParser(description="Split a YOLO dataset by sequence chunks.")
    parser.add_argument("--src", type=Path, default=Path("mydata"))
    parser.add_argument("--out", type=Path, default=Path("mydata_YOLO_clean"))
    parser.add_argument("--chunk-size", type=int, default=60)
    parser.add_argument("--train", type=float, default=0.70)
    parser.add_argument("--val", type=float, default=0.15)
    parser.add_argument("--test", type=float, default=0.15)
    parser.add_argument("--names", nargs="+", default=["fire", "person", "board card"])
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    ratio_sum = args.train + args.val + args.test
    if abs(ratio_sum - 1.0) > 1e-6:
        raise ValueError(f"Ratios must sum to 1.0, got {ratio_sum}")
    if args.out.exists():
        if not args.overwrite:
            raise FileExistsError(f"{args.out} already exists. Use --overwrite to replace it.")
        shutil.rmtree(args.out)

    samples, skipped_images, orphan_labels, duplicates = collect_samples(args.src)
    chunks = make_chunks(samples, args.chunk_size)
    splits = split_chunks(chunks, {"train": args.train, "val": args.val, "test": args.test})
    copy_split(splits, args.out, args.names)

    report = {
        "source": str(args.src.resolve()),
        "output": str(args.out.resolve()),
        "chunk_size": args.chunk_size,
        "ratios": {"train": args.train, "val": args.val, "test": args.test},
        "used_images_after_dedup": len(samples),
        "skipped_images_without_label": skipped_images,
        "orphan_labels_without_image": orphan_labels,
        "dropped_duplicate_images": duplicates,
        "summary": summarize(splits),
    }
    report_path = args.out / "split_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({
        "output": str(args.out),
        "used_images_after_dedup": len(samples),
        "dropped_duplicate_images": len(duplicates),
        "orphan_labels_without_image": len(orphan_labels),
        "summary": report["summary"],
        "report": str(report_path),
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
