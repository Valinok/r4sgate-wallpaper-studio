"""Image <-> RGB565 conversion and wallpaper.h handling.

The module is GUI independent so it can be reused from scripts or tests.
All fallible operations raise :class:`ConverterError` with a stable ``code``
that the UI translates through :mod:`localization`.
"""

from __future__ import annotations

import ast
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Final

from PIL import Image, ImageOps

MAX_DIMENSION: Final = 8192
MAX_PIXELS: Final = 8_000_000
ELEMENTS_PER_LINE: Final = 16
DEFAULT_ARRAY_NAME: Final = "wallpaper"
IMAGE_SUFFIXES: Final = frozenset({".png", ".jpg", ".jpeg", ".bmp"})
HEADER_SUFFIXES: Final = frozenset({".h"})

C_KEYWORDS: Final = frozenset(
    {
        "auto",
        "break",
        "case",
        "char",
        "const",
        "continue",
        "default",
        "do",
        "double",
        "else",
        "enum",
        "extern",
        "float",
        "for",
        "goto",
        "if",
        "inline",
        "int",
        "long",
        "register",
        "restrict",
        "return",
        "short",
        "signed",
        "sizeof",
        "static",
        "struct",
        "switch",
        "typedef",
        "union",
        "unsigned",
        "void",
        "volatile",
        "while",
        "_Alignas",
        "_Alignof",
        "_Atomic",
        "_Bool",
        "_Complex",
        "_Generic",
        "_Imaginary",
        "_Noreturn",
        "_Static_assert",
        "_Thread_local",
    }
)

_IDENTIFIER_RE: Final = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_COMMENT_RE: Final = re.compile(r"/\*.*?\*/|//[^\n]*", re.DOTALL)
_DIRECTIVE_RE: Final = re.compile(r"(?m)^[ \t]*#[^\n]*$")
_DEFINE_RE: Final = re.compile(
    r"^[ \t]*#[ \t]*define[ \t]+([A-Za-z_]\w*)[ \t]+\(?[ \t]*([0-9]+)[ \t]*\)?",
    re.MULTILINE,
)
_ARRAY_RE: Final = re.compile(
    r"([A-Za-z_]\w*)\s*\[\s*([^\]\n]*?)\s*\]\s*=\s*\{"
)
_HEX_RE: Final = re.compile(r"0x[0-9A-Fa-f]+")
_DECIMAL_RE: Final = re.compile(r"(?<![\w.])[0-9]+(?![\w.])")
_INITIALIZER_RE: Final = re.compile(r"\{([^{}]*)\}", re.DOTALL)


class ConverterError(Exception):
    """Error with a localization code and formatting parameters."""

    def __init__(self, code: str, **params: object) -> None:
        super().__init__(code)
        self.code = code
        self.params: dict[str, object] = params


class ResizeMode(str, Enum):
    CROP = "crop"
    STRETCH = "stretch"


@dataclass(frozen=True, order=True)
class Resolution:
    width: int
    height: int

    def __post_init__(self) -> None:
        if not isinstance(self.width, int) or not isinstance(self.height, int):
            raise ConverterError("invalid_resolution_number")
        if not (1 <= self.width <= MAX_DIMENSION and 1 <= self.height <= MAX_DIMENSION):
            raise ConverterError("invalid_resolution", max_dimension=MAX_DIMENSION)
        if self.width * self.height > MAX_PIXELS:
            raise ConverterError("too_large", max_pixels=MAX_PIXELS)

    @property
    def pixel_count(self) -> int:
        return self.width * self.height

    def __str__(self) -> str:
        return f"{self.width} × {self.height}"


@dataclass(frozen=True)
class Preset:
    key: str
    width: int | None
    height: int | None

    @property
    def is_custom(self) -> bool:
        return self.width is None or self.height is None

    def resolution(self) -> Resolution | None:
        if self.width is None or self.height is None:
            return None
        return Resolution(self.width, self.height)


PRESETS: Final[tuple[Preset, ...]] = (
    Preset("preset.ili9341", 320, 240),
    Preset("preset.240x320", 240, 320),
    Preset("preset.240x240", 240, 240),
    Preset("preset.170x320", 170, 320),
    Preset("preset.135x240", 135, 240),
    Preset("preset.128x160", 128, 160),
    Preset("preset.r4sgate", 320, 188),
    Preset("preset.custom", None, None),
)


@dataclass(frozen=True)
class HeaderInfo:
    values: tuple[int, ...]
    width: int | None
    height: int | None
    array_name: str | None
    declared_count: int | None
    path: Path | None = None


def rgb888_to_rgb565(red: int, green: int, blue: int) -> int:
    return ((red & 0xF8) << 8) | ((green & 0xFC) << 3) | (blue >> 3)


def rgb565_to_rgb888(value: int) -> tuple[int, int, int]:
    red = (value >> 11) & 0x1F
    green = (value >> 5) & 0x3F
    blue = value & 0x1F
    return (red * 255) // 31, (green * 255) // 63, (blue * 255) // 31


def validate_array_name(name: str) -> str:
    value = name.strip()
    if not _IDENTIFIER_RE.match(value):
        raise ConverterError("array_name")
    if value in C_KEYWORDS:
        raise ConverterError("array_keyword", name=value)
    return value


def load_image(path: Path) -> Image.Image:
    suffix = path.suffix.lower()
    if suffix not in IMAGE_SUFFIXES:
        raise ConverterError("unsupported_image", suffix=suffix or path.name)
    try:
        with Image.open(path) as opened:
            transposed = ImageOps.exif_transpose(opened)
            return transposed.convert("RGB")
    except Exception as exc:
        raise ConverterError("image_open", detail=str(exc)) from exc


def resize_image(
    image: Image.Image, resolution: Resolution, mode: ResizeMode
) -> Image.Image:
    size = (resolution.width, resolution.height)
    if mode is ResizeMode.CROP:
        return ImageOps.fit(
            image,
            size,
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        ).convert("RGB")
    return image.resize(size, Image.Resampling.LANCZOS).convert("RGB")


def image_to_rgb565(image: Image.Image) -> list[int]:
    data = image.convert("RGB").tobytes()
    values = [0] * (len(data) // 3)
    index = 0
    for offset in range(0, len(data), 3):
        red = data[offset]
        green = data[offset + 1]
        blue = data[offset + 2]
        values[index] = ((red & 0xF8) << 8) | ((green & 0xFC) << 3) | (blue >> 3)
        index += 1
    return values


def rgb565_to_image(values: Sequence[int], resolution: Resolution) -> Image.Image:
    expected = resolution.pixel_count
    if len(values) < expected:
        raise ConverterError("short_data", expected=expected, found=len(values))
    buffer = bytearray(expected * 3)
    for index in range(expected):
        red, green, blue = rgb565_to_rgb888(values[index])
        offset = index * 3
        buffer[offset] = red
        buffer[offset + 1] = green
        buffer[offset + 2] = blue
    return Image.frombytes("RGB", (resolution.width, resolution.height), bytes(buffer))


def restore_image(values: Sequence[int], resolution: Resolution) -> Image.Image:
    expected = resolution.pixel_count
    if len(values) < expected:
        raise ConverterError("short_data", expected=expected, found=len(values))
    return rgb565_to_image(values[:expected], resolution)


def build_rgb565(
    image: Image.Image, resolution: Resolution, mode: ResizeMode
) -> list[int]:
    return image_to_rgb565(resize_image(image, resolution, mode))


def quantized_image(
    image: Image.Image, resolution: Resolution, mode: ResizeMode
) -> Image.Image:
    return rgb565_to_image(build_rgb565(image, resolution, mode), resolution)


def build_header(
    values: Sequence[int], resolution: Resolution, array_name: str
) -> str:
    name = validate_array_name(array_name)
    expected = resolution.pixel_count
    if len(values) != expected:
        raise ConverterError("count_mismatch", expected=expected, found=len(values))

    rows: list[str] = []
    for start in range(0, expected, ELEMENTS_PER_LINE):
        chunk = values[start : start + ELEMENTS_PER_LINE]
        packed = ", ".join(f"0x{value:04X}" for value in chunk)
        rows.append(f"    {packed},")
    body = "\n".join(rows)
    return (
        "#pragma once\n"
        "\n"
        "#include <stdint.h>\n"
        "\n"
        f"#define WALLPAPER_WIDTH {resolution.width}\n"
        f"#define WALLPAPER_HEIGHT {resolution.height}\n"
        "\n"
        f"const uint16_t {name}[{expected}] = {{\n"
        f"{body}\n"
        "};\n"
    )


def write_text(path: Path, text: str) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(text, encoding="utf-8", newline="\n")
        os.replace(temporary, path)
    except OSError as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise ConverterError(
            "write_failed", path=str(path), detail=str(exc)
        ) from exc


def write_header(
    path: Path,
    values: Sequence[int],
    resolution: Resolution,
    array_name: str,
) -> None:
    write_text(path, build_header(values, resolution, array_name))


def save_png(image: Image.Image, path: Path) -> None:
    temporary = path.with_name(f".{path.stem}.tmp.png")
    try:
        image.save(temporary, format="PNG")
        os.replace(temporary, path)
    except OSError as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise ConverterError("save_failed", detail=str(exc)) from exc


def save_jpeg(image: Image.Image, path: Path, quality: int = 95) -> None:
    temporary = path.with_name(f".{path.stem}.tmp{path.suffix}")
    try:
        image.convert("RGB").save(
            temporary, format="JPEG", quality=quality, optimize=False
        )
        os.replace(temporary, path)
    except OSError as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise ConverterError("save_failed", detail=str(exc)) from exc


def save_bmp(image: Image.Image, path: Path) -> None:
    temporary = path.with_name(f".{path.stem}.tmp{path.suffix}")
    try:
        image.convert("RGB").save(temporary, format="BMP")
        os.replace(temporary, path)
    except OSError as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise ConverterError("save_failed", detail=str(exc)) from exc


SAVE_SUFFIXES: Final = frozenset({".png", ".jpg", ".jpeg", ".bmp"})


def save_image(image: Image.Image, path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix == ".png":
        save_png(image, path)
    elif suffix in {".jpg", ".jpeg"}:
        save_jpeg(image, path)
    elif suffix == ".bmp":
        save_bmp(image, path)
    else:
        raise ConverterError("unsupported_save_format", suffix=suffix or path.name)


def save_restored_png(header_path: Path, image: Image.Image) -> Path:
    target = header_path.with_name(f"{header_path.stem}_restored.png")
    save_png(image, target)
    return target


def _decode_text(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1251"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


def _strip_comments(text: str) -> str:
    return _COMMENT_RE.sub(" ", text)


def _strip_directives(text: str) -> str:
    return _DIRECTIVE_RE.sub(" ", text)


def _parse_defines(text: str) -> dict[str, int]:
    defines: dict[str, int] = {}
    for match in _DEFINE_RE.finditer(text):
        defines[match.group(1).upper()] = int(match.group(2))
    return defines


def _first_define(defines: Mapping[str, int], *names: str) -> int | None:
    for name in names:
        value = defines.get(name.upper())
        if value is not None:
            return value
    return None


def _evaluate_size(expression: str, defines: Mapping[str, int]) -> int | None:
    expression = expression.strip()
    if not expression:
        return None
    if expression.isdigit():
        return int(expression)

    def replace(match: re.Match[str]) -> str:
        return str(defines.get(match.group(0).upper(), "")) or match.group(0)

    expanded = re.sub(r"[A-Za-z_]\w*", replace, expression)
    try:
        tree = ast.parse(expanded, mode="eval")
    except SyntaxError:
        return None
    allowed = (ast.Expression, ast.BinOp, ast.Constant, ast.Add, ast.Mult, ast.UnaryOp)
    for node in ast.walk(tree):
        if not isinstance(node, allowed):
            return None
        if isinstance(node, ast.Constant) and not isinstance(node.value, int):
            return None
    try:
        result = eval(compile(tree, "<size>", "eval"), {"__builtins__": {}}, {})
    except Exception:
        return None
    return result if isinstance(result, int) and result > 0 else None


def parse_header_text(text: str, path: Path | None = None) -> HeaderInfo:
    defines = _parse_defines(text)
    clean = _strip_directives(_strip_comments(text))

    array_name: str | None = None
    declared_count: int | None = None
    array_match = _ARRAY_RE.search(clean)
    if array_match is not None:
        array_name = array_match.group(1)
        declared_count = _evaluate_size(array_match.group(2), defines)
        if declared_count is not None and declared_count > MAX_PIXELS * 8:
            declared_count = None

    width = _first_define(
        defines,
        "WALLPAPER_WIDTH",
        f"{array_name.upper()}_WIDTH" if array_name else "",
        "WIDTH",
    )
    height = _first_define(
        defines,
        "WALLPAPER_HEIGHT",
        f"{array_name.upper()}_HEIGHT" if array_name else "",
        "HEIGHT",
    )

    tokens = _HEX_RE.findall(clean)
    values: list[int] = []
    if tokens:
        values = [int(token, 16) for token in tokens]
    else:
        block = _INITIALIZER_RE.search(clean)
        source = block.group(1) if block else clean
        values = [int(token, 10) for token in _DECIMAL_RE.findall(source)]

    if not values:
        name = path.name if path is not None else "header"
        raise ConverterError("empty_values", name=name)

    for value in values:
        if value > 0xFFFF:
            raise ConverterError("value_range", value=value)

    return HeaderInfo(
        values=tuple(values),
        width=width,
        height=height,
        array_name=array_name,
        declared_count=declared_count,
        path=path,
    )


def read_header(path: Path) -> HeaderInfo:
    suffix = path.suffix.lower()
    if suffix not in HEADER_SUFFIXES:
        raise ConverterError("unsupported_header", suffix=suffix or path.name)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ConverterError(
            "read_failed", path=str(path), detail=str(exc)
        ) from exc
    return parse_header_text(_decode_text(raw), path)


def suggest_resolutions(pixel_count: int) -> list[Resolution]:
    """Return plausible resolutions that contain exactly pixel_count pixels.

    Preset matches are listed first.  Additional factorizations are kept only
    when the non-preset side does not exceed 320 px, which matches the TFT
    displays targeted by this tool and keeps the choice list short.
    """

    if pixel_count <= 0:
        return []

    seen: set[tuple[int, int]] = set()
    results: list[Resolution] = []

    for preset in PRESETS:
        if preset.width is not None and preset.height is not None:
            if preset.width * preset.height == pixel_count:
                key = (preset.width, preset.height)
                if key not in seen:
                    seen.add(key)
                    results.append(Resolution(preset.width, preset.height))

    widths = sorted(
        {preset.width for preset in PRESETS if preset.width is not None},
        reverse=True,
    )
    for width in widths:
        if pixel_count % width:
            continue
        height = pixel_count // width
        if height > 320 or not (1 <= height <= MAX_DIMENSION):
            continue
        if height * width > MAX_PIXELS:
            continue
        try:
            resolution = Resolution(width, height)
        except ConverterError:
            continue
        key = (resolution.width, resolution.height)
        if key not in seen:
            seen.add(key)
            results.append(resolution)

    heights = sorted(
        {preset.height for preset in PRESETS if preset.height is not None},
        reverse=True,
    )
    for height in heights:
        if pixel_count % height:
            continue
        width = pixel_count // height
        if width > 320 or not (1 <= width <= MAX_DIMENSION):
            continue
        if height * width > MAX_PIXELS:
            continue
        try:
            resolution = Resolution(width, height)
        except ConverterError:
            continue
        key = (resolution.width, resolution.height)
        if key not in seen:
            seen.add(key)
            results.append(resolution)

    return results
