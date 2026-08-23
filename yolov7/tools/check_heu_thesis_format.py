import os
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS = {"w": W_NS, "a": A_NS}


def wtag(name: str) -> str:
    return f"{{{W_NS}}}{name}"


def text_of(el: ET.Element) -> str:
    return "".join(t.text or "" for t in el.findall(".//w:t", NS)).strip()


def mm_from_twips(v: str | None) -> float | None:
    if v is None:
        return None
    return round(int(v) / 56.6929133858, 2)


def find_current_docx() -> Path:
    candidates = [
        p
        for p in Path(".").glob("*.docx")
        if not p.name.startswith("~$")
        and "摘要完善" not in p.name
        and "参考" not in p.name
        and "图表" not in p.name
        and "保留结果图片" not in p.name
        and "current" not in p.name
        and "thesis" not in p.name
    ]
    if not candidates:
        candidates = [p for p in Path(".").glob("*.docx") if not p.name.startswith("~$")]
    return max(candidates, key=lambda p: p.stat().st_mtime)


def count_chinese_chars(s: str) -> int:
    return sum(1 for ch in s if "\u4e00" <= ch <= "\u9fff")


def word_count_en(s: str) -> int:
    return len(re.findall(r"[A-Za-z]+(?:[-'][A-Za-z]+)?|\d+(?:\.\d+)?", s))


def main() -> None:
    docx = find_current_docx()
    with zipfile.ZipFile(docx) as z:
        names = z.namelist()
        document = ET.fromstring(z.read("word/document.xml"))
        styles = ET.fromstring(z.read("word/styles.xml")) if "word/styles.xml" in names else None
        headers = {
            n: ET.fromstring(z.read(n))
            for n in names
            if n.startswith("word/header") and n.endswith(".xml")
        }
        footers = {
            n: ET.fromstring(z.read(n))
            for n in names
            if n.startswith("word/footer") and n.endswith(".xml")
        }

    body = document.find(".//w:body", NS)
    children = list(body)
    paragraphs = [c for c in children if c.tag == wtag("p")]
    para_texts = [text_of(p) for p in paragraphs]

    print(f"docx={docx.name}")
    print(f"zip_ok={bool(names)}")
    print(f"paragraphs={len(paragraphs)}")
    print(f"tables={sum(1 for c in children if c.tag == wtag('tbl'))}")
    print(f"images={len(document.findall('.//a:blip', NS))}")

    print("\n[section_margins_mm]")
    for i, sect in enumerate(document.findall(".//w:sectPr", NS), start=1):
        mar = sect.find("w:pgMar", NS)
        if mar is None:
            continue
        attrs = mar.attrib
        print(
            i,
            {
                k: mm_from_twips(attrs.get(wtag(k)))
                for k in ["top", "bottom", "left", "right", "header", "footer"]
            },
        )

    print("\n[key_structure]")
    for key in ["摘    要", "ABSTRACT", "目    录", "目 录", "目录", "第1章", "结    论", "参考文献", "致    谢"]:
        hits = [(i, t) for i, t in enumerate(para_texts) if t == key or t.startswith(key)]
        print(key, hits[:3])

    title = next((t for t in para_texts if t.startswith("基于嵌入式")), "")
    print("\n[title]")
    print(title)
    print("chinese_chars=", count_chinese_chars(title))

    print("\n[abstract]")
    ch_abs = para_texts[para_texts.index("摘    要") + 1] if "摘    要" in para_texts else ""
    ch_kw = next((t for t in para_texts if t.startswith("关键词")), "")
    en_abs = para_texts[para_texts.index("ABSTRACT") + 1] if "ABSTRACT" in para_texts else ""
    en_kw = next((t for t in para_texts if t.startswith("Keywords:")), "")
    print("chinese_chars=", count_chinese_chars(ch_abs), "text_len=", len(ch_abs))
    print("ch_keywords=", ch_kw)
    print("ch_keyword_sep_semicolon=", "；" in ch_kw)
    print("english_words=", word_count_en(en_abs))
    print("en_keywords=", en_kw)

    print("\n[headings]")
    chapter_heads = [t for t in para_texts if re.match(r"^第\d+章", t)]
    print("chapter_heads=", chapter_heads)
    print("has_chapter_summaries=", [t for t in para_texts if "本章小结" in t])

    print("\n[figures]")
    fig_caps = [(i, t) for i, t in enumerate(para_texts) if re.match(r"^图\d+[-.]\d+", t)]
    print("count=", len(fig_caps))
    print("separators=", Counter("-" if "-" in t.split()[0] else "." for _, t in fig_caps))
    for i, t in fig_caps[:40]:
        print(i, t)

    print("\n[tables]")
    table_caps = [(i, t) for i, t in enumerate(para_texts) if re.match(r"^表\d+[-.]\d+", t)]
    print("count=", len(table_caps))
    print("separators=", Counter("-" if "-" in t.split()[0] else "." for _, t in table_caps))
    # Locate table captions relative to table elements.
    tbl_positions = [idx for idx, c in enumerate(children) if c.tag == wtag("tbl")]
    for cap_idx, cap_text in table_caps:
        p_el = paragraphs[cap_idx]
        body_idx = children.index(p_el)
        before = children[body_idx - 1].tag == wtag("tbl") if body_idx > 0 else False
        after = children[body_idx + 1].tag == wtag("tbl") if body_idx + 1 < len(children) else False
        print(cap_idx, cap_text, "above_table=", after, "below_table=", before)

    print("\n[citations]")
    citation_runs = 0
    superscript_runs = 0
    for p in paragraphs:
        for r in p.findall("w:r", NS):
            r_text = "".join(t.text or "" for t in r.findall(".//w:t", NS))
            if re.search(r"\[[0-9,\-\s，]+\]", r_text):
                citation_runs += 1
                va = r.find("w:rPr/w:vertAlign", NS)
                if va is not None and va.attrib.get(wtag("val")) == "superscript":
                    superscript_runs += 1
    print("citation_runs=", citation_runs)
    print("superscript_runs=", superscript_runs)

    print("\n[references]")
    ref_start = next((i for i, t in enumerate(para_texts) if t == "参考文献"), None)
    if ref_start is None:
        print("no_reference_heading")
    else:
        refs = [t for t in para_texts[ref_start + 1 :] if re.match(r"^\[\d+\]", t)]
        print("ref_count=", len(refs))
        print("all_end_dot=", all(t.endswith(".") for t in refs))
        print("sample_refs=", refs[:5])

    print("\n[headers_footers]")
    for name, root in headers.items():
        print("header", name, text_of(root))
    for name, root in footers.items():
        print("footer", name, text_of(root))


if __name__ == "__main__":
    main()
