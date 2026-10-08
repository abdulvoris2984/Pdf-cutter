"""Tests that drive the real window. They need a display (CI uses xvfb-run)."""

import sys
import time
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

tk = pytest.importorskip("tkinter")
pytest.importorskip("customtkinter")

from ui.widgets import PreviewCard  # noqa: E402
from ui.window import PdfCutterWindow  # noqa: E402


@pytest.fixture(scope="module")
def window():
    try:
        win = PdfCutterWindow()
    except tk.TclError as exc:
        pytest.skip(f"no display available: {exc}")
    yield win
    win.destroy()


@pytest.fixture
def win(window):
    """The shared window, reset to its starting state."""
    window.clear_files()
    window.mode_switch.set("Pages per file")
    window._set_mode("Pages per file")
    window.values["size"].set("20")
    window.values["count"].set("4")
    window.finished = False
    window.refresh()
    return window


@pytest.fixture
def exam(tmp_path):
    path = tmp_path / "exam.pdf"
    writer = PdfWriter()
    for _ in range(80):
        writer.add_blank_page(width=100, height=100)
    with open(path, "wb") as fh:
        writer.write(fh)
    return path


def cards(win):
    return [c for c in win.preview.winfo_children() if isinstance(c, PreviewCard)]


def test_empty_window_cannot_cut(win):
    assert cards(win) == []
    assert win.cut_button.cget("state") == "disabled"
    assert "Add a PDF" in win.status_label.cget("text")


def test_adding_a_file_shows_the_plan(win, exam):
    win.add_files([exam])
    win.refresh()
    assert len(cards(win)) == 1
    assert win.cut_button.cget("text") == "Cut into 4 files"
    assert win.summary_label.cget("text") == "4 new files"


def test_switching_mode_updates_the_plan(win, exam):
    win.add_files([exam])
    win.mode_switch.set("Number of files")
    win._set_mode("Number of files")
    win.values["count"].set("3")
    win.refresh()
    assert win.plan_for(win.files[0]) == [(1, 27), (28, 54), (55, 80)]
    assert win.cut_button.cget("text") == "Cut into 3 files"


def test_bad_ranges_disable_the_cut_button(win, exam):
    win.add_files([exam])
    win._set_mode("Custom ranges")
    win.values["ranges"].set("1-20, 90-")
    win.refresh()
    assert win.cut_button.cget("state") == "disabled"
    assert "needs fixing" in win.status_label.cget("text")


def test_unsupported_file_is_rejected(win, tmp_path, monkeypatch):
    warnings = []
    monkeypatch.setattr("ui.window.messagebox.showwarning", lambda *a, **k: warnings.append(a))
    notes = tmp_path / "notes.docx"
    notes.write_text("hi")
    win.add_files([notes])
    assert win.files == []
    assert warnings and "only PDF and PPTX" in warnings[0][1]


def test_remove_file(win, exam):
    win.add_files([exam])
    win.remove_file(win.files[0])
    win.refresh()
    assert win.files == [] and cards(win) == []


def test_cutting_through_the_window(win, exam):
    win.add_files([exam])
    win.refresh()
    win.start_cut()
    deadline = time.monotonic() + 30
    while (win.busy or not win.finished) and time.monotonic() < deadline:
        win.update()
        time.sleep(0.01)

    outputs = [exam.with_name(f"exam{i}.pdf") for i in range(1, 5)]
    assert all(len(PdfReader(p).pages) == 20 for p in outputs)
    assert win.status_label.cget("text").startswith("Done! Created 4 files")
    assert win.open_button.winfo_ismapped()
