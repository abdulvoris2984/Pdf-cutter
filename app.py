"""PDF Cutter: cut PDF and PowerPoint files into smaller pieces.

Run it with:  python app.py
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import cutter

APP_TITLE = "PDF Cutter"
PREVIEW_MAX_PARTS = 8  # per file; longer plans are shortened with "... and N more"


def unit_for(path: Path, count: int) -> str:
    word = "slide" if path.suffix.lower() == ".pptx" else "page"
    return word if count == 1 else word + "s"


def describe_range(path: Path, start: int, end: int) -> str:
    if start == end:
        return f"{unit_for(path, 1)} {start}"
    return f"{unit_for(path, 2)} {start}–{end}"


def open_folder(folder: Path) -> None:
    if sys.platform.startswith("win"):
        os.startfile(folder)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(folder)])
    else:
        subprocess.Popen(["xdg-open", str(folder)])


class PdfCutterApp:
    def __init__(self, root: tk.Tk, initial_files: list[str] | tuple[str, ...] = ()):
        self.root = root
        self.files: list[Path] = []
        self.page_counts: dict[Path, int] = {}
        self.events: queue.Queue = queue.Queue()
        self.busy = False
        self.last_output_dir: Path | None = None

        self.mode = tk.StringVar(value="size")
        self.values = {
            "size": tk.StringVar(value="20"),
            "count": tk.StringVar(value="4"),
            "ranges": tk.StringVar(value="1-20, 21-40"),
        }
        self.output_choice = tk.StringVar(value="same")
        self.output_dir = tk.StringVar()
        self.status = tk.StringVar(value="Add a PDF or PowerPoint file to get started.")

        self._build_ui()

        # Typing in a box selects its option, and every change updates the preview.
        for mode, var in self.values.items():
            var.trace_add("write", lambda *_, m=mode: self.mode.set(m))
        for var in (self.mode, self.output_choice, self.output_dir):
            var.trace_add("write", lambda *_: self.refresh_preview())
        self.output_dir.trace_add("write", lambda *_: self.output_choice.set("custom"))

        self.add_files(initial_files)
        self.refresh_preview()

    # ------------------------------------------------------------------ UI --

    def _build_ui(self) -> None:
        root = self.root
        root.title(APP_TITLE)
        root.minsize(600, 620)

        base_font = tkfont.nametofont("TkDefaultFont")
        size = base_font.cget("size")
        self.bold_font = base_font.copy()
        self.bold_font.configure(weight="bold")
        self.big_font = base_font.copy()
        self.big_font.configure(size=size + 2 if size > 0 else size - 3, weight="bold")

        style = ttk.Style(root)
        style.configure("Cut.TButton", font=self.big_font, padding=(18, 6))
        style.configure("Hint.TLabel", foreground="gray")

        main = ttk.Frame(root, padding=16)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)

        # 1. Files -----------------------------------------------------------
        files_box = ttk.LabelFrame(main, text=" 1. Files to cut ", padding=10)
        files_box.grid(row=0, column=0, sticky="nsew")
        files_box.columnconfigure(0, weight=1)

        self.file_list = tk.Listbox(files_box, height=5, selectmode="extended", activestyle="none")
        self.file_list.grid(row=0, column=0, sticky="nsew")
        self.file_list.bind("<Delete>", lambda _e: self.remove_selected())
        self.file_list.bind("<BackSpace>", lambda _e: self.remove_selected())
        scroll = ttk.Scrollbar(files_box, orient="vertical", command=self.file_list.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.file_list.configure(yscrollcommand=scroll.set)

        file_buttons = ttk.Frame(files_box)
        file_buttons.grid(row=0, column=2, sticky="n", padx=(10, 0))
        self.add_button = ttk.Button(file_buttons, text="Add files…", command=self.choose_files)
        self.add_button.pack(fill="x")
        ttk.Button(file_buttons, text="Remove", command=self.remove_selected).pack(fill="x", pady=4)
        ttk.Button(file_buttons, text="Clear", command=self.clear_files).pack(fill="x")

        # 2. How to cut ------------------------------------------------------
        how = ttk.LabelFrame(main, text=" 2. How to cut ", padding=10)
        how.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        options = [
            ("size", "Pages per file:", "e.g. 20 → 80 pages become 4 files of 20"),
            ("count", "Number of files:", "e.g. 4 → 80 pages become 4 files of 20"),
            ("ranges", "Custom ranges:", "one file per range, e.g. 1-25, 26-50, 51-"),
        ]
        for row, (mode, label, hint) in enumerate(options):
            ttk.Radiobutton(how, text=label, value=mode, variable=self.mode).grid(
                row=row, column=0, sticky="w", pady=3
            )
            if mode == "ranges":
                box = ttk.Entry(how, textvariable=self.values[mode], width=22)
            else:
                box = ttk.Spinbox(how, from_=1, to=9999, textvariable=self.values[mode], width=8)
            box.grid(row=row, column=1, sticky="w", padx=8)
            box.bind("<FocusIn>", lambda _e, m=mode: self.mode.set(m))
            ttk.Label(how, text=hint, style="Hint.TLabel").grid(row=row, column=2, sticky="w")

        # 3. Where to save ---------------------------------------------------
        out = ttk.LabelFrame(main, text=" 3. Save the pieces ", padding=10)
        out.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        out.columnconfigure(1, weight=1)
        ttk.Radiobutton(
            out, text="In the same folder as the original", value="same", variable=self.output_choice
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))
        ttk.Radiobutton(out, text="In this folder:", value="custom", variable=self.output_choice).grid(
            row=1, column=0, sticky="w"
        )
        ttk.Entry(out, textvariable=self.output_dir).grid(row=1, column=1, sticky="ew", padx=8)
        ttk.Button(out, text="Browse…", command=self.choose_output_dir).grid(row=1, column=2)

        # Preview ------------------------------------------------------------
        preview_box = ttk.LabelFrame(main, text=" Preview ", padding=10)
        preview_box.grid(row=3, column=0, sticky="nsew", pady=(12, 0))
        preview_box.columnconfigure(0, weight=1)
        preview_box.rowconfigure(0, weight=1)
        main.rowconfigure(3, weight=1)

        self.preview = tk.Text(
            preview_box, height=9, wrap="word", borderwidth=0, highlightthickness=0, cursor="arrow",
            font="TkDefaultFont", tabs=(24, 170), padx=6, pady=4,
        )
        self.preview.grid(row=0, column=0, sticky="nsew")
        preview_scroll = ttk.Scrollbar(preview_box, orient="vertical", command=self.preview.yview)
        preview_scroll.grid(row=0, column=1, sticky="ns")
        self.preview.configure(yscrollcommand=preview_scroll.set, state="disabled")
        self.preview.tag_configure("header", font=self.bold_font)
        self.preview.tag_configure("error", foreground="#d32f2f")
        self.preview.tag_configure("muted", foreground="gray")

        # Bottom bar ---------------------------------------------------------
        bottom = ttk.Frame(main)
        bottom.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        bottom.columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(bottom, mode="determinate")
        self.progress.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        ttk.Label(bottom, textvariable=self.status, wraplength=360, justify="left").grid(
            row=1, column=0, sticky="w"
        )
        self.open_button = ttk.Button(
            bottom, text="Open folder", command=self.open_output_folder, state="disabled"
        )
        self.open_button.grid(row=1, column=1, padx=8)
        self.cut_button = ttk.Button(bottom, text="Cut!", style="Cut.TButton", command=self.start_cut)
        self.cut_button.grid(row=1, column=2)

        root.bind("<Return>", lambda _e: self.start_cut())
        root.bind("<Control-o>", lambda _e: self.choose_files())
        if sys.platform == "darwin":
            root.bind("<Command-o>", lambda _e: self.choose_files())

    # --------------------------------------------------------------- files --

    def choose_files(self) -> None:
        if self.busy:
            return
        paths = filedialog.askopenfilenames(
            parent=self.root,
            title="Choose PDF or PowerPoint files",
            filetypes=[
                ("PDF and PowerPoint", "*.pdf *.pptx"),
                ("PDF", "*.pdf"),
                ("PowerPoint", "*.pptx"),
                ("All files", "*.*"),
            ],
        )
        self.add_files(paths)

    def add_files(self, paths) -> None:
        problems = []
        for raw in paths:
            path = Path(raw).expanduser().resolve()
            if path in self.files:
                continue
            try:
                self.page_counts[path] = cutter.count_pages(path)
            except cutter.CutterError as exc:
                problems.append(str(exc))
                continue
            self.files.append(path)
            if not self.output_dir.get():
                self.output_dir.set(str(path.parent))
                self.output_choice.set("same")  # setting output_dir switched it to "custom"
        self._refresh_file_list()
        if problems:
            messagebox.showwarning(APP_TITLE, "\n\n".join(problems), parent=self.root)

    def remove_selected(self) -> None:
        if self.busy:
            return
        for index in reversed(self.file_list.curselection()):
            del self.files[index]
        self._refresh_file_list()

    def clear_files(self) -> None:
        if self.busy:
            return
        self.files.clear()
        self._refresh_file_list()

    def _refresh_file_list(self) -> None:
        self.file_list.delete(0, "end")
        for path in self.files:
            count = self.page_counts[path]
            self.file_list.insert("end", f"{path.name}   ({count} {unit_for(path, count)})")
        if self.files:
            self.status.set("Check the preview, then click Cut!")
        else:
            self.status.set("Add a PDF or PowerPoint file to get started.")
        self.refresh_preview()

    def choose_output_dir(self) -> None:
        folder = filedialog.askdirectory(
            parent=self.root, title="Where should the pieces go?", initialdir=self.output_dir.get() or None
        )
        if folder:
            self.output_dir.set(folder)
            self.output_choice.set("custom")

    # ------------------------------------------------------------- planning --

    def plan_for(self, path: Path) -> list[cutter.Range]:
        mode = self.mode.get()
        return cutter.make_plan(self.page_counts[path], mode, self.values[mode].get(), unit_for(path, 2))

    def target_dir(self) -> Path | None:
        if self.output_choice.get() == "custom" and self.output_dir.get().strip():
            return Path(self.output_dir.get().strip()).expanduser()
        return None

    def refresh_preview(self) -> None:
        lines: list[tuple[str, str]] = []  # (text, tag)
        if not self.files:
            lines.append(('Nothing to cut yet. Click "Add files…" and pick a PDF or PowerPoint file.', "muted"))
        if self.output_choice.get() == "custom" and not self.output_dir.get().strip():
            lines.append(("Choose a folder to save the pieces in (step 3).", "error"))

        for path in self.files:
            total = self.page_counts[path]
            try:
                plan = self.plan_for(path)
            except cutter.CutterError as exc:
                lines.append((f"{path.name}: {exc}", "error"))
                lines.append(("", ""))
                continue
            targets = cutter.output_paths(path, len(plan), self.target_dir())
            pieces = "1 file" if len(plan) == 1 else f"{len(plan)} files"
            lines.append((f"{path.name} ({total} {unit_for(path, total)}) → {pieces}", "header"))
            shown = len(plan) if len(plan) <= PREVIEW_MAX_PARTS else PREVIEW_MAX_PARTS - 1
            for (start, end), target in zip(plan[:shown], targets):
                lines.append((f"\t{target.name}\t{describe_range(path, start, end)}", ""))
            if shown < len(plan):
                lines.append((f"\t… and {len(plan) - shown} more, up to {targets[-1].name}", "muted"))
            lines.append(("", ""))

        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        for text, tag in lines:
            self.preview.insert("end", text + "\n", tag)
        self.preview.configure(state="disabled")

    # ------------------------------------------------------------- cutting --

    def start_cut(self) -> None:
        if self.busy:
            return
        if not self.files:
            messagebox.showinfo(APP_TITLE, "Add a PDF or PowerPoint file first.", parent=self.root)
            return
        if self.output_choice.get() == "custom" and not self.output_dir.get().strip():
            messagebox.showinfo(APP_TITLE, "Choose a folder to save the pieces in.", parent=self.root)
            return

        jobs, problems = [], []
        for path in self.files:
            try:
                jobs.append((path, self.plan_for(path)))
            except cutter.CutterError as exc:
                problems.append(f"{path.name}: {exc}")
        if problems:
            messagebox.showerror(APP_TITLE, "Please fix this first:\n\n" + "\n".join(problems), parent=self.root)
            return

        out_dir = self.target_dir()
        targets = [t for path, plan in jobs for t in cutter.output_paths(path, len(plan), out_dir)]
        clash = next((t for t in targets if t in self.files), None)
        if clash:
            messagebox.showerror(
                APP_TITLE,
                f"Cutting would overwrite {clash.name}, which is one of the files you are cutting. "
                "Remove it from the list or save the pieces in another folder.",
                parent=self.root,
            )
            return
        if len(set(targets)) != len(targets):
            messagebox.showerror(
                APP_TITLE,
                "Two of your files have the same name, so their pieces would overwrite each other. "
                'Choose "In the same folder as the original" or cut them one at a time.',
                parent=self.root,
            )
            return
        existing = [t for t in targets if t.exists()]
        if existing:
            names = ", ".join(t.name for t in existing[:3]) + (" …" if len(existing) > 3 else "")
            if not messagebox.askyesno(
                APP_TITLE,
                f"{len(existing)} file(s) already exist ({names}).\n\nReplace them?",
                parent=self.root,
            ):
                return

        self._set_busy(True)
        self.progress.configure(maximum=len(targets), value=0)
        threading.Thread(target=self._cut_worker, args=(jobs, out_dir), daemon=True).start()
        self.root.after(50, self._poll_events)

    def _cut_worker(self, jobs, out_dir: Path | None) -> None:
        """Runs in a background thread so the window stays responsive."""
        total_parts = sum(len(plan) for _, plan in jobs)
        finished = 0
        written: list[Path] = []
        errors: list[str] = []
        for path, plan in jobs:
            self.events.put(("status", f"Cutting {path.name}…"))
            base = finished

            def report(done: int, _total: int, base: int = base) -> None:
                self.events.put(("progress", base + done, total_parts))

            try:
                written += cutter.split_file(path, plan, out_dir, progress=report)
            except cutter.CutterError as exc:
                errors.append(str(exc))
            except Exception as exc:  # e.g. no permission to write in the folder
                errors.append(f"{path.name}: {exc}")
            finished = base + len(plan)
            self.events.put(("progress", finished, total_parts))
        self.events.put(("done", written, errors))

    def _poll_events(self) -> None:
        try:
            while True:
                kind, *data = self.events.get_nowait()
                if kind == "status":
                    self.status.set(data[0])
                elif kind == "progress":
                    self.progress.configure(value=data[0], maximum=data[1])
                elif kind == "done":
                    self._finish(*data)
                    return
        except queue.Empty:
            pass
        self.root.after(50, self._poll_events)

    def _finish(self, written: list[Path], errors: list[str]) -> None:
        self._set_busy(False)
        if written:
            self.last_output_dir = written[-1].parent
            self.open_button.configure(state="normal")
        count = "1 file" if len(written) == 1 else f"{len(written)} files"
        if errors:
            self.status.set(f"Finished with problems. Created {count}.")
            messagebox.showerror(
                APP_TITLE, "Some files couldn't be cut:\n\n" + "\n\n".join(errors), parent=self.root
            )
        else:
            self.status.set(f"Done! Created {count} in {self.last_output_dir}.")

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.cut_button.configure(state=state)
        self.add_button.configure(state=state)
        self.root.configure(cursor="watch" if busy else "")

    def open_output_folder(self) -> None:
        if self.last_output_dir:
            open_folder(self.last_output_dir)


def main() -> None:
    if "--self-test" in sys.argv:  # used by the build, see .github/workflows/build.yml
        try:
            cutter.self_test()
        except Exception:
            if sys.stderr:
                traceback.print_exc()
            os._exit(1)
        if sys.stdout:
            print("self-test OK")
        os._exit(0)

    if sys.platform.startswith("win"):
        try:  # sharp text on high-DPI Windows screens
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    root = tk.Tk()
    # Files passed on the command line (or dropped onto the .exe) are added right away.
    initial = [arg for arg in sys.argv[1:] if Path(arg).is_file()]
    PdfCutterApp(root, initial)
    root.mainloop()


if __name__ == "__main__":
    main()
