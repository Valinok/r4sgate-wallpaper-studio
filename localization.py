"""Localization support for ESP32 R4sGate Wallpaper Studio.

All user-visible strings live in ``TRANSLATIONS``.  Language detection follows
the operating system UI language: Russian for ru/uk/be, English otherwise.
"""

from __future__ import annotations

import ctypes
import locale
import os
import sys
from collections.abc import Callable, Mapping
from typing import Final

LANGUAGE_RU: Final = "ru"
LANGUAGE_EN: Final = "en"
RUSSIAN_LANGUAGES: Final = frozenset({"ru", "uk", "be"})
LANGUAGES: Final = (LANGUAGE_RU, LANGUAGE_EN)
LANGUAGE_NAMES: Final = {"ru": "Русский", "en": "English"}

TRANSLATIONS: Final[dict[str, dict[str, str]]] = {
    LANGUAGE_EN: {
        "app.title": "ESP32 R4sGate Wallpaper Studio",
        "app.subtitle": (
            "Convert images to wallpaper.h for the ESP32-R4sGate-for-Redmond firmware"
        ),
        "menu.file": "File",
        "menu.file.open_image": "Open Image…",
        "menu.file.open_header": "Open wallpaper.h…",
        "menu.file.save_image": "Save Image As…",
        "menu.file.generate": "Generate wallpaper.h…",
        "menu.file.exit": "Exit",
        "menu.language": "Language",
        "menu.help": "Help",
        "menu.help.about": "About",
        "section.source": "Source Image",
        "section.target": "Target Resolution",
        "section.mode": "Resize Mode",
        "section.array": "Array Name",
        "section.preview": "Preview",
        "source.none": "No image selected",
        "source.choose": "Choose Image…",
        "source.info": "Source: {width} × {height} px",
        "source.hint": "PNG, JPG, JPEG, BMP",
        "target.preset": "Preset",
        "target.width": "Width",
        "target.height": "Height",
        "target.output": "{width} × {height} px · {count} values",
        "mode.crop": "Crop + Resize (ImageOps.fit)",
        "mode.stretch": "Stretch",
        "array.label": "C array name",
        "array.hint": "Valid C identifier, e.g. wallpaper",
        "array.invalid": "Only letters, digits and underscore; cannot start with a digit.",
        "array.keyword": "“{name}” is a reserved C keyword.",
        "button.generate": "Generate wallpaper.h",
        "button.open_header": "Open wallpaper.h",
        "button.save_image": "Save Image As…",
        "preview.empty": "Open an image or a wallpaper.h file to see the preview.",
        "preview.invalid": "Enter a valid target resolution to see the preview.",
        "preview.source": "Source · {width} × {height} px",
        "preview.result": "Result · {width} × {height} px · {mode}",
        "preview.suggestions.label": (
            "Header has no size defines. If the preview looks wrong, "
            "choose another resolution:"
        ),
        "preview.restored": "Restored · {width} × {height} px · {name}",
        "status.ready": "Ready",
        "status.image_loaded": "Loaded {name} ({width} × {height} px)",
        "status.generated": "Saved {path} · {count} values",
        "status.restored": "Restored {name} · {width} × {height} px · preview: {path}",
        "status.restored_no_file": (
            "Restored {name} · {width} × {height} px · preview was not saved"
        ),
        "status.image_saved": "Image saved: {path}",
        "status.cancelled": "Cancelled",
        "dialog.dimensions.title": "Header resolution",
        "dialog.dimensions.message": (
            "The file has no WALLPAPER_WIDTH / WALLPAPER_HEIGHT defines. "
            "The pixel count matches one or more resolutions; please select "
            "the correct one."
        ),
        "dialog.dimensions.info": "Found {count} RGB565 values.",
        "dialog.dimensions.suggestions_hint": (
            "Select a resolution from the list or enter Width and Height manually."
        ),
        "dialog.dimensions.manual": (
            "No matching resolution was found. Enter Width and Height manually."
        ),
        "dialog.ok": "OK",
        "dialog.cancel": "Cancel",
        "about.title": "About",
        "about.text": (
            "ESP32 R4sGate Wallpaper Studio {version}\n\n"
            "Converts PNG, JPG, JPEG and BMP images into a C header with an "
            "RGB565 array, and restores PNG previews from wallpaper.h.\n\n"
            "Target firmware: ESP32-R4sGate-for-Redmond.\n\n"
            "For the built-in wallpaper area of the gateway use 320 × 188 "
            "(the image is drawn at y = 52)."
        ),
        "error.title": "Error",
        "error.no_image": "Choose a source image first.",
        "error.unsupported_image": (
            "Unsupported image type “{suffix}”. Use PNG, JPG, JPEG or BMP."
        ),
        "error.image_open": "Could not open the image:\n{detail}",
        "error.read_failed": "Could not read {path}:\n{detail}",
        "error.write_failed": "Could not write {path}:\n{detail}",
        "error.unsupported_header": (
            "Unsupported header type “{suffix}”. Use a .h file."
        ),
        "error.empty_values": "No RGB565 values were found in {name}.",
        "error.value_range": "Value 0x{value:04X} does not fit into 16 bits.",
        "error.short_data": "Not enough values: expected {expected}, found {found}.",
        "error.count_mismatch": (
            "Pixel count mismatch: expected {expected}, got {found}."
        ),
        "error.invalid_resolution": (
            "Width and height must be between 1 and {max_dimension}."
        ),
        "error.invalid_resolution_number": "Width and height must be whole numbers.",
        "error.too_large": "Resolution is too large: maximum {max_pixels} pixels.",
        "error.array_name": "Enter a valid C identifier for the array name.",
        "error.array_keyword": "“{name}” is a reserved C keyword.",
        "error.save_failed": "Could not save the image:\n{detail}",
        "error.unsupported_save_format": (
            "Unsupported save format “{suffix}”. Use PNG, JPG, JPEG or BMP."
        ),
        "error.no_restored": (
            "Nothing to save yet. Load an image or open a wallpaper.h file."
        ),
        "error.unexpected": "Unexpected error:\n{detail}",
        "warning.title": "Warning",
        "warning.excess_values": (
            "{name} contains {found} values but {width} × {height} needs "
            "{expected}. Extra values were ignored."
        ),
        "preset.ili9341": "320 × 240 (ILI9341)",
        "preset.240x320": "240 × 320",
        "preset.240x240": "240 × 240",
        "preset.170x320": "170 × 320",
        "preset.135x240": "135 × 240",
        "preset.128x160": "128 × 160",
        "preset.r4sgate": "320 × 188 (R4sGate area)",
        "preset.custom": "Custom…",
    },
    LANGUAGE_RU: {
        "app.title": "ESP32 R4sGate Wallpaper Studio",
        "app.subtitle": (
            "Конвертация изображений в wallpaper.h для прошивки "
            "ESP32-R4sGate-for-Redmond"
        ),
        "menu.file": "Файл",
        "menu.file.open_image": "Открыть изображение…",
        "menu.file.open_header": "Открыть wallpaper.h…",
        "menu.file.save_image": "Сохранить изображение как…",
        "menu.file.generate": "Создать wallpaper.h…",
        "menu.file.exit": "Выход",
        "menu.language": "Язык",
        "menu.help": "Справка",
        "menu.help.about": "О программе",
        "section.source": "Исходное изображение",
        "section.target": "Целевое разрешение",
        "section.mode": "Режим масштабирования",
        "section.array": "Имя массива",
        "section.preview": "Предпросмотр",
        "source.none": "Изображение не выбрано",
        "source.choose": "Выбрать изображение…",
        "source.info": "Источник: {width} × {height} px",
        "source.hint": "PNG, JPG, JPEG, BMP",
        "target.preset": "Пресет",
        "target.width": "Ширина",
        "target.height": "Высота",
        "target.output": "{width} × {height} px · {count} значений",
        "mode.crop": "Обрезка + масштаб (ImageOps.fit)",
        "mode.stretch": "Растянуть",
        "array.label": "Имя массива C",
        "array.hint": "Допустимый идентификатор C, например wallpaper",
        "array.invalid": (
            "Только буквы, цифры и подчёркивание; нельзя начинать с цифры."
        ),
        "array.keyword": "«{name}» — зарезервированное слово C.",
        "button.generate": "Создать wallpaper.h",
        "button.open_header": "Открыть wallpaper.h",
        "button.save_image": "Сохранить изображение как…",
        "preview.empty": (
            "Откройте изображение или файл wallpaper.h, чтобы увидеть предпросмотр."
        ),
        "preview.invalid": "Укажите корректное целевое разрешение для предпросмотра.",
        "preview.source": "Источник · {width} × {height} px",
        "preview.result": "Результат · {width} × {height} px · {mode}",
        "preview.suggestions.label": (
            "В заголовке нет размеров. Если предпросмотр неверный, "
            "выберите другое разрешение:"
        ),
        "preview.restored": "Восстановлено · {width} × {height} px · {name}",
        "status.ready": "Готово",
        "status.image_loaded": "Загружено {name} ({width} × {height} px)",
        "status.generated": "Сохранено {path} · {count} значений",
        "status.restored": (
            "Восстановлено {name} · {width} × {height} px · предпросмотр: {path}"
        ),
        "status.restored_no_file": (
            "Восстановлено {name} · {width} × {height} px · предпросмотр не сохранён"
        ),
        "status.image_saved": "Изображение сохранено: {path}",
        "status.cancelled": "Отменено",
        "dialog.dimensions.title": "Разрешение заголовка",
        "dialog.dimensions.message": (
            "В файле нет определений WALLPAPER_WIDTH / WALLPAPER_HEIGHT. "
            "Количество пикселей подходит под одно или несколько разрешений; "
            "выберите правильный вариант."
        ),
        "dialog.dimensions.info": "Найдено {count} значений RGB565.",
        "dialog.dimensions.suggestions_hint": (
            "Выберите разрешение из списка либо введите Ширину и Высоту вручную."
        ),
        "dialog.dimensions.manual": (
            "Подходящее разрешение не найдено. Введите Ширину и Высоту вручную."
        ),
        "dialog.ok": "ОК",
        "dialog.cancel": "Отмена",
        "about.title": "О программе",
        "about.text": (
            "ESP32 R4sGate Wallpaper Studio {version}\n\n"
            "Преобразует изображения PNG, JPG, JPEG и BMP в заголовочный файл C "
            "с массивом RGB565 и восстанавливает PNG из wallpaper.h.\n\n"
            "Целевая прошивка: ESP32-R4sGate-for-Redmond.\n\n"
            "Для встроенной области обоев шлюза используйте 320 × 188 "
            "(изображение выводится с y = 52)."
        ),
        "error.title": "Ошибка",
        "error.no_image": "Сначала выберите исходное изображение.",
        "error.unsupported_image": (
            "Неподдерживаемый тип изображения «{suffix}». "
            "Используйте PNG, JPG, JPEG или BMP."
        ),
        "error.image_open": "Не удалось открыть изображение:\n{detail}",
        "error.read_failed": "Не удалось прочитать {path}:\n{detail}",
        "error.write_failed": "Не удалось записать {path}:\n{detail}",
        "error.unsupported_header": (
            "Неподдерживаемый тип заголовка «{suffix}». Используйте файл .h."
        ),
        "error.empty_values": "В {name} не найдено значений RGB565.",
        "error.value_range": "Значение 0x{value:04X} не помещается в 16 бит.",
        "error.short_data": (
            "Недостаточно значений: ожидалось {expected}, найдено {found}."
        ),
        "error.count_mismatch": (
            "Несовпадение количества пикселей: ожидалось {expected}, "
            "получено {found}."
        ),
        "error.invalid_resolution": (
            "Ширина и высота должны быть от 1 до {max_dimension}."
        ),
        "error.invalid_resolution_number": (
            "Ширина и высота должны быть целыми числами."
        ),
        "error.too_large": "Слишком большое разрешение: максимум {max_pixels} пикселей.",
        "error.array_name": "Введите корректный идентификатор C для имени массива.",
        "error.array_keyword": "«{name}» — зарезервированное слово C.",
        "error.save_failed": "Не удалось сохранить изображение:\n{detail}",
        "error.unsupported_save_format": (
            "Неподдерживаемый формат сохранения «{suffix}». "
            "Используйте PNG, JPG, JPEG или BMP."
        ),
        "error.no_restored": (
            "Пока нечего сохранять. Загрузите изображение или откройте wallpaper.h."
        ),
        "error.unexpected": "Непредвиденная ошибка:\n{detail}",
        "warning.title": "Предупреждение",
        "warning.excess_values": (
            "В {name} найдено {found} значений, но для {width} × {height} нужно "
            "{expected}. Лишние значения проигнорированы."
        ),
        "preset.ili9341": "320 × 240 (ILI9341)",
        "preset.240x320": "240 × 320",
        "preset.240x240": "240 × 240",
        "preset.170x320": "170 × 320",
        "preset.135x240": "135 × 240",
        "preset.128x160": "128 × 160",
        "preset.r4sgate": "320 × 188 (область R4sGate)",
        "preset.custom": "Другой…",
    },
}


def _format(template: str, params: Mapping[str, object]) -> str:
    try:
        return template.format(**params)
    except (KeyError, IndexError, ValueError):
        return template


def _windows_ui_language() -> str | None:
    try:
        language_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()  # type: ignore[attr-defined]
    except Exception:
        return None
    primary = language_id & 0x3FF
    return {0x19: "ru", 0x22: "uk", 0x23: "be"}.get(primary)


def _environment_language() -> str | None:
    for name in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        value = os.environ.get(name)
        if not value:
            continue
        code = value.split(".")[0].split("_")[0].split("-")[0].strip().lower()
        if code:
            return code
    try:
        locale_name = locale.getlocale()[0]
    except (ValueError, TypeError):
        locale_name = None
    if locale_name:
        code = locale_name.split(".")[0].split("_")[0].split("-")[0].strip().lower()
        if code:
            return code
    return None


def detect_system_language() -> str:
    """Return ``"ru"`` for ru/uk/be systems and ``"en"`` otherwise."""

    if sys.platform == "win32":
        code = _windows_ui_language()
        if code:
            return LANGUAGE_RU if code in RUSSIAN_LANGUAGES else LANGUAGE_EN
    code = _environment_language()
    if code and code in RUSSIAN_LANGUAGES:
        return LANGUAGE_RU
    return LANGUAGE_EN


class Localization:
    """Holds the active language and notifies subscribers on change."""

    def __init__(self, language: str | None = None) -> None:
        self._language = language if language in TRANSLATIONS else LANGUAGE_EN
        self._listeners: list[Callable[[], None]] = []

    @property
    def language(self) -> str:
        return self._language

    def set_language(self, language: str) -> None:
        if language not in TRANSLATIONS or language == self._language:
            return
        self._language = language
        for listener in tuple(self._listeners):
            listener()

    def subscribe(self, listener: Callable[[], None]) -> None:
        if listener not in self._listeners:
            self._listeners.append(listener)

    def t(self, key: str, **params: object) -> str:
        template = TRANSLATIONS[self._language].get(key)
        if template is None:
            template = TRANSLATIONS[LANGUAGE_EN].get(key, key)
        return _format(template, params)

    def error(self, code: str, params: Mapping[str, object] | None = None) -> str:
        return self.t(f"error.{code}", **(params or {}))

    def warning(self, code: str, params: Mapping[str, object] | None = None) -> str:
        return self.t(f"warning.{code}", **(params or {}))
