"""PDF Cutter: cut PDF and PowerPoint files into smaller pieces.

Run it with:  python app.py [files...]
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
import traceback
from pathlib import Path

import cutter


def gui_self_test() -> None:
    """Open the real window, cut a file through it and close it again."""
    from pypdf import PdfWriter

    from ui.window import PdfCutterWindow

    with tempfile.TemporaryDirectory() as tmp:
        sample = Path(tmp) / "sample.pdf"
        writer = PdfWriter()
        for _ in range(10):
            writer.add_blank_page(width=200, height=200)
        with open(sample, "wb") as fh:
            writer.write(fh)

        window = PdfCutterWindow([str(sample)])
        try:
            window.update()
            if os.environ.get("PDFCUTTER_REQUIRE_DND") and not window.dnd_enabled:
                raise RuntimeError("drag and drop support failed to load")
            window.values["size"].set("4")
            window.refresh()
            window.start_cut()
            deadline = time.monotonic() + 60
            while (window.busy or not window.finished) and time.monotonic() < deadline:
                window.update()
                time.sleep(0.02)
        finally:
            window.destroy()

        names = sorted(p.name for p in Path(tmp).iterdir())
        if names != ["sample.pdf", "sample1.pdf", "sample2.pdf", "sample3.pdf"]:
            raise RuntimeError(f"GUI self-test produced {names}")


def main() -> None:
    if "--self-test" in sys.argv:  # used by the build, see .github/workflows/build.yml
        try:
            cutter.self_test()
            gui_self_test()
        except Exception:
            if sys.stderr:
                traceback.print_exc()
            os._exit(1)
        if sys.stdout:
            print("self-test OK")
        os._exit(0)

    from ui.window import PdfCutterWindow

    # Files passed on the command line (or dropped onto the .exe) are added right away.
    initial = [arg for arg in sys.argv[1:] if Path(arg).is_file()]
    PdfCutterWindow(initial).mainloop()


if __name__ == "__main__":
    main()
