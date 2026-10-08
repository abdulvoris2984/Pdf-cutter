"""The PDF Cutter main window."""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image

import cutter

from . import theme
from .theme import asset
from .widgets import DropZone, PreviewCard, Stepper, section_label, shorten_path

APP_TITLE = "PDF Cutter"
MODES = {"Pages per file": "size", "Number of files": "count", "Custom ranges": "ranges"}
MODE_HINTS = {
    "size": "pages in each file",
    "count": "files of (almost) equal size",
    "ranges": "One file per range. 51- means page 51 to the end.",
}
SAVE_SAME, SAVE_OTHER = "Next to the original", "Other folder"


def open_folder(folder: Path) -> None:
    if sys.platform.startswith("win"):
        os.startfile(folder)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(folder)])
    else:
        subprocess.Popen(["xdg-open", str(folder)])


class PdfCutterWindow(ctk.CTk):
    def __init__(self, initial_files=()):
        super().__init__(fg_color=theme.BG)
        self.title(APP_TITLE)
        self.geometry("1040x680")
        self.minsize(940, 620)
        self._set_icon()

        self.fonts = theme.Fonts()
        logo = Image.open(asset("icon.png"))
        self.logo = ctk.CTkImage(logo, size=(44, 44))
        self.empty_logo = ctk.CTkImage(logo, size=(88, 88))
        self.drop_icon = ctk.CTkImage(Image.open(asset("drop.png")), size=(40, 40))

        self.files: list[Path] = []
        self.page_counts: dict[Path, int] = {}
        self.events: queue.Queue = queue.Queue()
        self.busy = False
        self.finished = False  # show the "Done!" message until something changes
        self.last_output_dir: Path | None = None
        self.output_dir: Path | None = None
        self._refresh_job: str | None = None

        self.mode = "size"
        self.values = {
            "size": tk.StringVar(value="20"),
            "count": tk.StringVar(value="4"),
            "ranges": tk.StringVar(value="1-20, 21-40"),
        }

        self._build()
        for var in self.values.values():
            var.trace_add("write", lambda *_: self.schedule_refresh())
        ctk.AppearanceModeTracker.add(self._on_appearance_change)
        self.dnd_enabled = self._enable_drag_and_drop()

        self.bind("<Return>", lambda _e: self.start_cut())
        self.bind("<Control-o>", lambda _e: self.choose_files())
        if sys.platform == "darwin":
            self.bind("<Command-o>", lambda _e: self.choose_files())

        self.add_files(initial_files)
        self.refresh()

    # ----------------------------------------------------------- building --

    def _set_icon(self) -> None:
        try:
            if sys.platform.startswith("win"):
                self.iconbitmap(str(asset("icon.ico")))
            else:
                self._icon_photo = tk.PhotoImage(file=str(asset("icon.png"))).subsample(4)
                self.iconphoto(True, self._icon_photo)
        except tk.TclError:
            pass

    def _build(self) -> None:
        f = self.fonts
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=24, pady=(18, 20))
        self.body.columnconfigure(1, weight=1)
        self.body.rowconfigure(1, weight=1)

        # Header ---------------------------------------------------------------
        header = ctk.CTkFrame(self.body, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 16))
        header.columnconfigure(2, weight=1)
        ctk.CTkLabel(header, text="", image=self.logo).grid(row=0, column=0, rowspan=2, padx=(0, 14))
        ctk.CTkLabel(header, text=APP_TITLE, font=f.title, text_color=theme.TEXT, height=28).grid(
            row=0, column=1, sticky="sw"
        )
        ctk.CTkLabel(
            header, text="Split PDFs and slide decks into smaller files", font=f.subtitle,
            text_color=theme.MUTED, height=20,
        ).grid(row=1, column=1, sticky="nw")
        self.theme_switch = self._segmented(header, ["Light", "Dark"], self._set_theme, width=150)
        self.theme_switch.configure(fg_color=theme.TRACK, unselected_color=theme.TRACK)
        self.theme_switch.set(ctk.get_appearance_mode())
        self.theme_switch.grid(row=0, column=3, rowspan=2, sticky="e")

        # Settings card (left) ---------------------------------------------------
        left = self._card(self.body, width=400)
        left.grid(row=1, column=0, sticky="ns", padx=(0, 16))
        left.grid_propagate(False)
        left.columnconfigure(0, weight=1)
        pad = dict(padx=22, sticky="ew")

        section_label(left, "Files", f).grid(row=0, column=0, pady=(20, 8), **pad)
        self.drop_zone = DropZone(left, f, self.drop_icon, self.choose_files)
        self.drop_zone.grid(row=1, column=0, **pad)
        files_line = ctk.CTkFrame(left, fg_color="transparent", height=30)
        files_line.grid(row=2, column=0, pady=(4, 0), **pad)
        files_line.columnconfigure(0, weight=1)
        self.files_label = ctk.CTkLabel(files_line, text="", font=f.small, text_color=theme.MUTED, anchor="w")
        self.files_label.grid(row=0, column=0, sticky="w")
        self.clear_button = self._link_button(files_line, "Clear all", self.clear_files)
        self.clear_button.grid(row=0, column=1, sticky="e")

        section_label(left, "Cut into", f).grid(row=3, column=0, pady=(14, 8), **pad)
        self.mode_switch = self._segmented(left, list(MODES), self._set_mode)
        self.mode_switch.set("Pages per file")
        self.mode_switch.grid(row=4, column=0, **pad)

        options = ctk.CTkFrame(left, fg_color="transparent")
        options.grid(row=5, column=0, pady=(12, 0), **pad)
        options.columnconfigure(0, weight=1)
        self.option_rows = {}
        for mode in ("size", "count"):
            row = ctk.CTkFrame(options, fg_color="transparent")
            Stepper(row, self.values[mode], f).grid(row=0, column=0)
            ctk.CTkLabel(row, text=MODE_HINTS[mode], font=f.body, text_color=theme.MUTED).grid(
                row=0, column=1, padx=12
            )
            self.option_rows[mode] = row
        ranges_row = ctk.CTkFrame(options, fg_color="transparent")
        ranges_row.columnconfigure(0, weight=1)
        ctk.CTkEntry(
            ranges_row, textvariable=self.values["ranges"], height=36, corner_radius=10, border_width=0,
            fg_color=theme.FIELD, text_color=theme.TEXT, font=f.body,
        ).grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(
            ranges_row, text=MODE_HINTS["ranges"], font=f.small, text_color=theme.MUTED, anchor="w", height=22
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.option_rows["ranges"] = ranges_row
        for row in self.option_rows.values():
            row.grid(row=0, column=0, sticky="ew")
            row.grid_remove()
        self.option_rows["size"].grid()

        section_label(left, "Save to", f).grid(row=6, column=0, pady=(18, 8), **pad)
        self.save_switch = self._segmented(left, [SAVE_SAME, SAVE_OTHER], self._set_save_mode)
        self.save_switch.set(SAVE_SAME)
        self.save_switch.grid(row=7, column=0, **pad)
        save_line = ctk.CTkFrame(left, fg_color="transparent")
        save_line.grid(row=8, column=0, pady=(6, 20), **pad)
        save_line.columnconfigure(0, weight=1)
        self.save_label = ctk.CTkLabel(save_line, text="", font=f.small, text_color=theme.MUTED, anchor="w")
        self.save_label.grid(row=0, column=0, sticky="w")
        self.change_button = self._link_button(save_line, "Change…", self.choose_output_dir)
        self.change_button.grid(row=0, column=1, sticky="e")

        # Preview card (right) ---------------------------------------------------
        right = self._card(self.body)
        right.grid(row=1, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        top = ctk.CTkFrame(right, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=22, pady=(20, 8))
        top.columnconfigure(0, weight=1)
        section_label(top, "Preview", f).grid(row=0, column=0, sticky="w")
        self.summary_label = ctk.CTkLabel(top, text="", font=f.small, text_color=theme.MUTED, height=18)
        self.summary_label.grid(row=0, column=1, sticky="e")
        self.preview = ctk.CTkScrollableFrame(
            right, fg_color="transparent", scrollbar_button_color=theme.FIELD_HOVER,
            scrollbar_button_hover_color=theme.BORDER,
        )
        self.preview.grid(row=1, column=0, sticky="nsew", padx=(12, 8), pady=(0, 14))
        self.preview.columnconfigure(0, weight=1)
        self.preview.bind("<Configure>", lambda _e: self._update_scrollbar(), add="+")
        right.bind("<Configure>", lambda _e: self._update_scrollbar(), add="+")

        # Footer ---------------------------------------------------------------
        footer = self._card(self.body)
        footer.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(16, 0))
        footer.columnconfigure(0, weight=1)
        self.status_label = ctk.CTkLabel(footer, text="", font=f.body, text_color=theme.TEXT, anchor="w")
        self.status_label.grid(row=0, column=0, sticky="ew", padx=(22, 12), pady=(16, 0))
        self.progress = ctk.CTkProgressBar(
            footer, height=6, corner_radius=3, fg_color=theme.FIELD, progress_color=theme.ACCENT
        )
        self.progress.set(0)
        self.progress.grid(row=1, column=0, sticky="ew", padx=(22, 12), pady=(4, 16))
        self.open_button = ctk.CTkButton(
            footer, text="Open folder", width=120, height=42, corner_radius=12, font=f.body_bold,
            fg_color=theme.FIELD, hover_color=theme.FIELD_HOVER, text_color=theme.TEXT,
            command=self.open_output_folder,
        )
        self.open_button.grid(row=0, column=1, rowspan=2, padx=(0, 10))
        self.open_button.grid_remove()
        self.cut_button = ctk.CTkButton(
            footer, text="Cut", width=180, height=42, corner_radius=12, font=f.button,
            fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER, text_color=theme.ON_ACCENT,
            text_color_disabled=theme.MUTED, command=self.start_cut,
        )
        self.cut_button.grid(row=0, column=2, rowspan=2, padx=(0, 16), pady=14)

    def _card(self, master, **kwargs) -> ctk.CTkFrame:
        return ctk.CTkFrame(
            master, fg_color=theme.CARD, border_width=1, border_color=theme.BORDER, corner_radius=18, **kwargs
        )

    def _segmented(self, master, values, command, width=140) -> ctk.CTkSegmentedButton:
        return ctk.CTkSegmentedButton(
            master, values=values, command=command, width=width, height=36, corner_radius=10, border_width=3,
            font=self.fonts.small, fg_color=theme.FIELD, selected_color=theme.SELECTED,
            selected_hover_color=theme.SELECTED, unselected_color=theme.FIELD,
            unselected_hover_color=theme.FIELD_HOVER, text_color=theme.TEXT, dynamic_resizing=False,
        )

    def _link_button(self, master, text, command) -> ctk.CTkButton:
        return ctk.CTkButton(
            master, text=text, command=command, width=0, height=26, corner_radius=8, font=self.fonts.small,
            fg_color="transparent", hover_color=theme.FIELD, text_color=theme.ACCENT,
        )

    def _enable_drag_and_drop(self) -> bool:
        """Let people drop files anywhere on the window (needs the tkinterdnd2 package)."""
        try:
            from tkinterdnd2 import DND_FILES, TkinterDnD

            TkinterDnD._require(self)
            self.body.drop_target_register(DND_FILES)
        except Exception:
            return False

        def highlight(event, on: bool):
            self.drop_zone.set_highlight(on and not self.busy)
            return event.action

        self.body.dnd_bind("<<DropEnter>>", lambda e: highlight(e, True))
        self.body.dnd_bind("<<DropLeave>>", lambda e: highlight(e, False))
        self.body.dnd_bind("<<Drop>>", self._on_drop)
        return True

    def _on_drop(self, event):
        self.drop_zone.set_highlight(False)
        if not self.busy:
            self.add_files(self.tk.splitlist(event.data))
        return event.action

    # ------------------------------------------------------------ settings --

    def _set_theme(self, value: str) -> None:
        ctk.set_appearance_mode(value)

    def _on_appearance_change(self, mode: str) -> None:
        if self.theme_switch.get() != mode:
            self.theme_switch.set(mode)
        self.schedule_refresh(user_change=False)  # the preview bars are drawn by hand

    def _set_mode(self, label: str) -> None:
        self.mode = MODES[label]
        for mode, row in self.option_rows.items():
            row.grid() if mode == self.mode else row.grid_remove()
        self.schedule_refresh()

    def _set_save_mode(self, value: str) -> None:
        if value == SAVE_OTHER and self.output_dir is None:
            self.choose_output_dir()
            if self.output_dir is None:  # cancelled
                self.save_switch.set(SAVE_SAME)
        self.schedule_refresh()

    def choose_output_dir(self) -> None:
        start = self.output_dir or (self.files[0].parent if self.files else None)
        folder = filedialog.askdirectory(parent=self, title="Where should the pieces go?", initialdir=start)
        if folder:
            self.output_dir = Path(folder)
            self.save_switch.set(SAVE_OTHER)
            self.schedule_refresh()

    def target_dir(self) -> Path | None:
        return self.output_dir if self.save_switch.get() == SAVE_OTHER else None

    # --------------------------------------------------------------- files --

    def choose_files(self) -> None:
        if self.busy:
            return
        paths = filedialog.askopenfilenames(
            parent=self,
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
        self.schedule_refresh()
        if problems:
            messagebox.showwarning(APP_TITLE, "\n\n".join(problems), parent=self)

    def remove_file(self, path: Path) -> None:
        if not self.busy and path in self.files:
            self.files.remove(path)
            self.schedule_refresh()

    def clear_files(self) -> None:
        if not self.busy:
            self.files.clear()
            self.schedule_refresh()

    # ------------------------------------------------------------- preview --

    def plan_for(self, path: Path) -> list[cutter.Range]:
        unit = "slides" if path.suffix.lower() == ".pptx" else "pages"
        return cutter.make_plan(self.page_counts[path], self.mode, self.values[self.mode].get(), unit)

    def schedule_refresh(self, user_change: bool = True) -> None:
        """Rebuild the preview shortly; quick typing only triggers one rebuild."""
        if user_change and not self.busy:
            self.finished = False
        if self._refresh_job:
            self.after_cancel(self._refresh_job)
        self._refresh_job = self.after(80, self.refresh)

    def refresh(self) -> None:
        self._refresh_job = None
        f = self.fonts

        count = len(self.files)
        self.files_label.configure(
            text="No files yet" if not count else f"{count} file{'s' if count != 1 else ''} added"
        )
        self.clear_button.grid() if count else self.clear_button.grid_remove()

        if self.target_dir():
            self.save_label.configure(text=shorten_path(self.target_dir(), 44))
            self.change_button.grid()
        else:
            self.save_label.configure(text="The pieces are saved next to each original file.")
            self.change_button.grid_remove()

        for child in self.preview.winfo_children():
            child.destroy()

        total_outputs, problems = 0, 0
        if not self.files:
            empty = ctk.CTkFrame(self.preview, fg_color="transparent")
            empty.grid(row=0, column=0, pady=(90, 0))
            ctk.CTkLabel(empty, text="", image=self.empty_logo).pack()
            ctk.CTkLabel(
                empty, text="Nothing to cut yet", font=f.body_bold, text_color=theme.TEXT, height=24
            ).pack(pady=(14, 0))
            ctk.CTkLabel(
                empty, text="Add a file and you'll see exactly how it will be cut.", font=f.small,
                text_color=theme.MUTED,
            ).pack()

        for row, path in enumerate(self.files):
            card_args = dict(path=path, total=self.page_counts[path], on_remove=lambda p=path: self.remove_file(p))
            try:
                plan = self.plan_for(path)
            except cutter.CutterError as exc:
                problems += 1
                card = PreviewCard(self.preview, f, error=str(exc), **card_args)
            else:
                total_outputs += len(plan)
                targets = cutter.output_paths(path, len(plan), self.target_dir())
                card = PreviewCard(self.preview, f, plan=plan, targets=targets, **card_args)
            card.grid(row=row, column=0, sticky="ew", padx=(0, 6), pady=(0, 12))

        self.after_idle(self._update_scrollbar)
        if self.files and not problems:
            self.summary_label.configure(text=f"{total_outputs} new file{'s' if total_outputs != 1 else ''}")
        else:
            self.summary_label.configure(text="")
        self._update_footer(total_outputs, problems)

    def _update_scrollbar(self) -> None:
        """Only show the preview's scrollbar when there is something to scroll."""
        try:
            canvas, scrollbar = self.preview._parent_canvas, self.preview._scrollbar
            content = self.preview.winfo_reqheight()
            visible = canvas.winfo_height()
        except (AttributeError, tk.TclError):
            return
        scrollbar.grid() if content > visible else scrollbar.grid_remove()

    def _update_footer(self, total_outputs: int, problems: int) -> None:
        ready = bool(self.files) and not problems and not self.busy
        if self.busy:
            text = "Cutting…"
        elif total_outputs and ready:
            text = f"Cut into {total_outputs} file{'s' if total_outputs != 1 else ''}"
        else:
            text = "Cut"
        self.cut_button.configure(
            text=text,
            state="normal" if ready else "disabled",
            fg_color=theme.ACCENT if ready or self.busy else theme.FIELD,
            text_color_disabled=theme.ON_ACCENT_DIM if self.busy else theme.MUTED,
        )

        if self.busy or self.finished:
            return  # the worker is reporting progress / the "Done!" message stays
        self.progress.grid_remove()
        self.open_button.grid_remove()
        if not self.files:
            self._set_status("Add a PDF or PowerPoint file to get started.")
        elif problems:
            self._set_status("Something in the preview needs fixing first.", theme.ERROR)
        else:
            self._set_status("Ready! Check the preview, then press Cut.")

    def _set_status(self, text: str, color=theme.TEXT) -> None:
        self.status_label.configure(text=text, text_color=color)

    # ------------------------------------------------------------- cutting --

    def start_cut(self) -> None:
        if self.busy or str(self.cut_button.cget("state")) == "disabled":
            return
        try:
            jobs = [(path, self.plan_for(path)) for path in self.files]
        except cutter.CutterError:
            return
        if not jobs:
            return

        out_dir = self.target_dir()
        targets = [t for path, plan in jobs for t in cutter.output_paths(path, len(plan), out_dir)]
        clash = next((t for t in targets if t in self.files), None)
        if clash:
            messagebox.showerror(
                APP_TITLE,
                f"Cutting would overwrite {clash.name}, which is one of the files you are cutting. "
                "Remove it from the list or save the pieces in another folder.",
                parent=self,
            )
            return
        if len(set(targets)) != len(targets):
            messagebox.showerror(
                APP_TITLE,
                "Two of your files have the same name, so their pieces would overwrite each other. "
                f'Choose "{SAVE_SAME}" or cut them one at a time.',
                parent=self,
            )
            return
        existing = [t for t in targets if t.exists()]
        if existing:
            names = ", ".join(t.name for t in existing[:3]) + (" …" if len(existing) > 3 else "")
            if not messagebox.askyesno(
                APP_TITLE, f"{len(existing)} file(s) already exist ({names}).\n\nReplace them?", parent=self
            ):
                return

        self.busy, self.finished = True, False
        self.open_button.grid_remove()
        self.progress.set(0)
        self.progress.grid()
        self.refresh()
        threading.Thread(target=self._cut_worker, args=(jobs, out_dir), daemon=True).start()
        self.after(50, self._poll_events)

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
                self.events.put(("progress", (base + done) / total_parts))

            try:
                written += cutter.split_file(path, plan, out_dir, progress=report)
            except cutter.CutterError as exc:
                errors.append(str(exc))
            except Exception as exc:  # e.g. no permission to write in the folder
                errors.append(f"{path.name}: {exc}")
            finished = base + len(plan)
            self.events.put(("progress", finished / total_parts))
        self.events.put(("done", written, errors))

    def _poll_events(self) -> None:
        try:
            while True:
                kind, *data = self.events.get_nowait()
                if kind == "status":
                    self._set_status(data[0])
                elif kind == "progress":
                    self.progress.set(data[0])
                elif kind == "done":
                    self._finish(*data)
                    return
        except queue.Empty:
            pass
        self.after(50, self._poll_events)

    def _finish(self, written: list[Path], errors: list[str]) -> None:
        self.busy, self.finished = False, True
        count = f"{len(written)} file{'s' if len(written) != 1 else ''}"
        if written:
            self.last_output_dir = written[-1].parent
            self.open_button.grid()
        if errors:
            self._set_status(f"Finished with problems. Created {count}.", theme.ERROR)
        else:
            self._set_status(f"Done! Created {count} in {self.last_output_dir.name or self.last_output_dir}.", theme.SUCCESS)
        self.refresh()
        if errors:
            messagebox.showerror(APP_TITLE, "Some files couldn't be cut:\n\n" + "\n\n".join(errors), parent=self)

    def open_output_folder(self) -> None:
        if self.last_output_dir:
            open_folder(self.last_output_dir)
