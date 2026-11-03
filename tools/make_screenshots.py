"""Generate README screenshots by driving the GUI programmatically."""

from __future__ import annotations

import shutil
import sys
import time
from pathlib import Path

from PIL import ImageGrab

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main
import localization
from converter import Resolution, suggest_resolutions


def _bbox(window) -> tuple[int, int, int, int]:
    window.update_idletasks()
    window.update()
    x = window.winfo_rootx()
    y = window.winfo_rooty()
    w = window.winfo_width()
    h = window.winfo_height()
    return (x, y, x + w, y + h)


def _grab(window, path: Path) -> None:
    window.attributes("-topmost", True)
    window.update()
    time.sleep(0.3)
    bbox = _bbox(window)
    # Ensure a small margin is included so window borders are captured.
    bbox = (bbox[0] - 2, bbox[1] - 2, bbox[2] + 2, bbox[3] + 2)
    ImageGrab.grab(bbox=bbox).save(path, format="PNG")
    window.attributes("-topmost", False)


def main_screenshots() -> None:
    out = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
    out.mkdir(parents=True, exist_ok=True)

    root, dnd = main.create_root()
    root.geometry("1120x780")
    i18n = localization.Localization("en")
    app = main.WallpaperStudioApp(root, i18n, dnd_enabled=dnd)
    root.update()

    # 1. Main window with an image loaded and a preview result.
    app._open_image(Path(r"..\ESP32-R4sGate-for-Redmond-master\jpg\tst.jpeg"))
    root.update()
    app.width_var.set("320")
    app.height_var.set("188")
    app._on_resolution_edited()
    root.update()
    time.sleep(0.5)
    root.update()
    _grab(root, out / "main-window.png")

    real_dialog = main.DimensionDialog

    # 2. Header opened: suggestion bar above the preview.
    class FakeDialog:
        def __init__(self, parent, i18n, pixel_count, suggestions, initial):
            self.suggestions = suggestions

        def show(self):
            return self.suggestions[0]

    main.DimensionDialog = FakeDialog

    work = Path("screenshot_work")
    work.mkdir(exist_ok=True)
    header_src = Path(r"..\wallpaper vol.h")
    header_copy = work / "wallpaper vol.h"
    shutil.copyfile(header_src, header_copy)
    app._open_header(header_copy)
    root.update()
    time.sleep(0.5)
    root.update()
    _grab(root, out / "header-suggestions.png")

    # 3. Dimension dialog for the same ambiguous header.
    main.DimensionDialog = real_dialog
    suggestions = suggest_resolutions(57600)
    dialog = main.DimensionDialog(
        root, i18n, pixel_count=57600, suggestions=suggestions, initial=Resolution(320, 180)
    )
    dialog.window.geometry("+300+200")
    dialog.window.deiconify()
    dialog.window.update()
    time.sleep(0.3)
    _grab(dialog.window, out / "resolution-dialog.png")
    dialog.window.destroy()

    root.destroy()
    shutil.rmtree(work, ignore_errors=True)
    print(f"Screenshots saved to {out}")


if __name__ == "__main__":
    main_screenshots()
