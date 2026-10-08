# PDF Cutter ✂️

A small desktop app that cuts big PDF or PowerPoint files into smaller ones.

**Example:** `exam.pdf` has 80 pages. Choose "20 pages per file" and you get
`exam1.pdf`, `exam2.pdf`, `exam3.pdf` and `exam4.pdf`, 20 pages each.

## Download

Go to the **[Releases](../../releases/latest)** page and download the file for your computer:

| Computer | File | First launch |
| --- | --- | --- |
| Windows | `PDF-Cutter-Windows.exe` | Double-click. If you see "Windows protected your PC", click **More info → Run anyway**. |
| Mac (M1 or newer) | `PDF-Cutter-macOS.zip` | Unzip it and move **PDF Cutter** to Applications. macOS will block it the first time: open **System Settings → Privacy & Security** and click **Open Anyway**. |
| Linux | `PDF-Cutter-Linux` | `chmod +x PDF-Cutter-Linux`, then run it. |

The warnings appear because the app isn't signed with a paid developer certificate. Nothing is wrong with the file.

## How to use it

1. **Add files.** Pick one or more `.pdf` or `.pptx` files.
2. **Choose how to cut:**
   - **Pages per file:** `20` turns 80 pages into 4 files of 20 (the last file gets whatever is left, e.g. 85 pages → 20, 20, 20, 20, 5).
   - **Number of files:** `4` turns 80 pages into 4 equal files.
   - **Custom ranges:** `1-25, 26-50, 51-` gives one file per range (`51-` means "51 to the end").
3. **Choose where to save.** Next to the original, or in a folder you pick.
4. Check the **preview** and click **Cut!**

PowerPoint files are cut into smaller `.pptx` files, keeping slides, images and speaker notes.
PDFs that are only copy-protected work fine; PDFs that need a password to open must be unlocked first.
Old `.ppt` files need to be saved as `.pptx` in PowerPoint first.

## Run from source (for developers)

Requires Python 3.10+ with Tkinter (included in the python.org installers).

```bash
pip install -r requirements.txt
python app.py
```

Run the tests:

```bash
pip install pytest
pytest
```

### Project layout

- `cutter.py`: the splitting logic (pypdf for PDFs, python-pptx for PowerPoint). No GUI code, easy to test.
- `app.py`: the Tkinter window.
- `tests/`: pytest tests for `cutter.py`.
- `.github/workflows/build.yml`: builds the Windows/macOS/Linux apps with PyInstaller, checks each one with
  `--self-test`, and publishes them as a GitHub Release.
