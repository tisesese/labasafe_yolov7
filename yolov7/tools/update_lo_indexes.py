import sys
from pathlib import Path

import uno
from com.sun.star.beans import PropertyValue


def prop(name, value):
    p = PropertyValue()
    p.Name = name
    p.Value = value
    return p


def connect_context(pipe_name: str):
    local_ctx = uno.getComponentContext()
    resolver = local_ctx.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver", local_ctx
    )
    return resolver.resolve(
        f"uno:pipe,name={pipe_name};urp;StarOffice.ComponentContext"
    )


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit("usage: update_lo_indexes.py input.docx output.docx [pipe_name]")

    src = Path(sys.argv[1]).resolve()
    dst = Path(sys.argv[2]).resolve()

    pipe_name = sys.argv[3] if len(sys.argv) > 3 else "codex_lo_pipe"
    ctx = connect_context(pipe_name)
    smgr = ctx.ServiceManager
    desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)

    doc = desktop.loadComponentFromURL(
        uno.systemPathToFileUrl(str(src)),
        "_blank",
        0,
        (prop("Hidden", True), prop("ReadOnly", False)),
    )
    if doc is None:
        raise RuntimeError(f"Could not open {src}")

    try:
        if hasattr(doc, "refresh"):
            doc.refresh()
        indexes = doc.getDocumentIndexes()
        for i in range(indexes.getCount()):
            indexes.getByIndex(i).update()

        doc.storeAsURL(
            uno.systemPathToFileUrl(str(dst)),
            (prop("FilterName", "Office Open XML Text"), prop("Overwrite", True)),
        )
    finally:
        doc.close(True)


if __name__ == "__main__":
    main()
