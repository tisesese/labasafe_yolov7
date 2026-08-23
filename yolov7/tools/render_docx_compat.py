# -*- coding: utf-8 -*-
import argparse
import os
import shutil
import subprocess
from pathlib import Path

from pdf2image import convert_from_path, pdfinfo_from_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("docx")
    parser.add_argument("--output_dir", default="render_out")
    parser.add_argument("--poppler_path", default="")
    parser.add_argument("--soffice", default="soffice.com")
    parser.add_argument("--dpi", type=int, default=140)
    args = parser.parse_args()

    docx = Path(args.docx).resolve()
    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    temp_root = (Path.cwd() / "render_work").resolve()
    if temp_root.exists():
        shutil.rmtree(str(temp_root), ignore_errors=True)
    temp_root.mkdir(parents=True, exist_ok=True)
    try:
        work_docx = temp_root / "input.docx"
        shutil.copy2(str(docx), str(work_docx))
        pdf_dir = temp_root / "pdf"
        profile_dir = temp_root / "lo_profile"
        pdf_dir.mkdir()
        profile_dir.mkdir()

        profile_uri = profile_dir.as_uri()
        cmd = [
            args.soffice,
            "-env:UserInstallation=" + profile_uri,
            "--headless",
            "--nologo",
            "--nofirststartwizard",
            "--nolockcheck",
            "--convert-to",
            "pdf",
            "--outdir",
            str(pdf_dir),
            str(work_docx),
        ]
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=240,
        )
        print("soffice_exit=", proc.returncode)
        if proc.stdout:
            print(proc.stdout)
        if proc.stderr:
            print(proc.stderr)
        pdfs = list(pdf_dir.glob("*.pdf"))
        if not pdfs:
            raise RuntimeError("LibreOffice did not produce a PDF")
        pdf = pdfs[0]
        final_pdf = out_dir / (docx.stem + ".pdf")
        shutil.copy2(str(pdf), str(final_pdf))

        info = pdfinfo_from_path(str(pdf), poppler_path=args.poppler_path or None)
        print("pdf_pages=", info.get("Pages"))

        pages = convert_from_path(
            str(pdf),
            dpi=args.dpi,
            fmt="png",
            output_folder=str(out_dir),
            output_file="page",
            paths_only=True,
            poppler_path=args.poppler_path or None,
        )
        renamed = []
        for idx, page_path in enumerate(sorted(Path(p) for p in pages), start=1):
            target = out_dir / ("page-%03d.png" % idx)
            if target.exists():
                target.unlink()
            page_path.replace(target)
            renamed.append(target)
        print("png_pages=", len(renamed))
        for p in renamed:
            print(p)
        print("pdf=", final_pdf)
    finally:
        # Keep the working directory for debugging if conversion fails.
        pass


if __name__ == "__main__":
    main()
