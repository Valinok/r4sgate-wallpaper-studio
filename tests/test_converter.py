"""Tests for :mod:`converter`."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

import converter
from converter import (
    ConverterError,
    Resolution,
    ResizeMode,
    build_header,
    build_rgb565,
    parse_header_text,
    read_header,
    restore_image,
    rgb565_to_image,
    rgb565_to_rgb888,
    rgb888_to_rgb565,
    suggest_resolutions,
    validate_array_name,
)

FIRMWARE_HEADER = (
    Path(__file__).resolve().parents[2]
    / "ESP32-R4sGate-for-Redmond-master"
    / "main"
    / "tft"
    / "wallpaper.h"
)


class Rgb565Test(unittest.TestCase):
    def test_known_vectors(self) -> None:
        self.assertEqual(rgb888_to_rgb565(0, 0, 0), 0x0000)
        self.assertEqual(rgb888_to_rgb565(255, 255, 255), 0xFFFF)
        self.assertEqual(rgb888_to_rgb565(255, 0, 0), 0xF800)
        self.assertEqual(rgb888_to_rgb565(0, 255, 0), 0x07E0)
        self.assertEqual(rgb888_to_rgb565(0, 0, 255), 0x001F)

    def test_inverse_expands_full_range(self) -> None:
        self.assertEqual(rgb565_to_rgb888(0xFFFF), (255, 255, 255))
        self.assertEqual(rgb565_to_rgb888(0xF800), (255, 0, 0))
        self.assertEqual(rgb565_to_rgb888(0x07E0), (0, 255, 0))
        self.assertEqual(rgb565_to_rgb888(0x001F), (0, 0, 255))

    def test_round_trip_image(self) -> None:
        image = Image.new("RGB", (3, 2))
        image.putdata(
            [
                (255, 0, 0),
                (0, 255, 0),
                (0, 0, 255),
                (10, 20, 30),
                (200, 100, 50),
                (1, 2, 3),
            ]
        )
        resolution = Resolution(3, 2)
        values = build_rgb565(image, resolution, ResizeMode.STRETCH)
        self.assertEqual(len(values), 6)
        restored = restore_image(values, resolution)
        self.assertEqual(restored.size, (3, 2))
        expected = b"".join(
            bytes(rgb565_to_rgb888(value)) for value in values
        )
        self.assertEqual(restored.tobytes(), expected)


class ResizeTest(unittest.TestCase):
    def test_crop_keeps_target_size(self) -> None:
        image = Image.new("RGB", (400, 200), (128, 128, 128))
        result = converter.resize_image(image, Resolution(100, 100), ResizeMode.CROP)
        self.assertEqual(result.size, (100, 100))

    def test_stretch_keeps_target_size(self) -> None:
        image = Image.new("RGB", (400, 200), (128, 128, 128))
        result = converter.resize_image(image, Resolution(100, 100), ResizeMode.STRETCH)
        self.assertEqual(result.size, (100, 100))

    def test_invalid_resolution(self) -> None:
        with self.assertRaises(ConverterError) as context:
            Resolution(0, 10)
        self.assertEqual(context.exception.code, "invalid_resolution")


class RestoreTest(unittest.TestCase):
    def test_short_data_raises(self) -> None:
        with self.assertRaises(ConverterError) as context:
            restore_image([0x0000] * 3, Resolution(2, 2))
        self.assertEqual(context.exception.code, "short_data")
        self.assertEqual(context.exception.params["expected"], 4)
        self.assertEqual(context.exception.params["found"], 3)

    def test_excess_data_is_truncated(self) -> None:
        image = restore_image([0xFFFF] * 10, Resolution(2, 2))
        self.assertEqual(image.size, (2, 2))


class HeaderBuildTest(unittest.TestCase):
    def test_format(self) -> None:
        values = [0x0000 + index for index in range(16)]
        text = build_header(values, Resolution(4, 4), "wallpaper")
        self.assertTrue(text.startswith("#pragma once\n"))
        self.assertIn("#include <stdint.h>", text)
        self.assertIn("#define WALLPAPER_WIDTH 4", text)
        self.assertIn("#define WALLPAPER_HEIGHT 4", text)
        self.assertIn("const uint16_t wallpaper[16] = {", text)
        self.assertIn("0x0000, 0x0001", text)
        self.assertEqual(text.count("0x"), 16)

    def test_sixteen_values_per_line(self) -> None:
        values = list(range(32))
        text = build_header(values, Resolution(8, 4), "wallpaper")
        data_lines = [
            line
            for line in text.splitlines()
            if line.strip().startswith("0x")
        ]
        self.assertEqual(len(data_lines), 2)
        for line in data_lines:
            self.assertEqual(line.count("0x"), 16)

    def test_count_mismatch(self) -> None:
        with self.assertRaises(ConverterError) as context:
            build_header([0] * 3, Resolution(2, 2), "wallpaper")
        self.assertEqual(context.exception.code, "count_mismatch")

    def test_array_name_validation(self) -> None:
        self.assertEqual(validate_array_name("wallpaper"), "wallpaper")
        self.assertEqual(validate_array_name("  my_array2  "), "my_array2")
        for bad in ("", "1abc", "my-array", "my array", "array.name"):
            with self.assertRaises(ConverterError):
                validate_array_name(bad)
        with self.assertRaises(ConverterError) as context:
            validate_array_name("int")
        self.assertEqual(context.exception.code, "array_keyword")


class HeaderParseTest(unittest.TestCase):
    def test_round_trip(self) -> None:
        resolution = Resolution(4, 4)
        values = [0x1000 + index for index in range(16)]
        text = build_header(values, resolution, "wallpaper")
        info = parse_header_text(text)
        self.assertEqual(info.values, tuple(values))
        self.assertEqual((info.width, info.height), (4, 4))
        self.assertEqual(info.array_name, "wallpaper")
        self.assertEqual(info.declared_count, 16)

    def test_comment_tokens_are_ignored(self) -> None:
        text = (
            "#pragma once\n"
            "// generated from 0xDEAD 0xBEEF\n"
            "/* 0x1234 */\n"
            "#define WALLPAPER_WIDTH 2\n"
            "#define WALLPAPER_HEIGHT 1\n"
            "const uint16_t wallpaper[2] = {\n"
            "    0x0001, 0x0002, /* trailing 0x9999 */\n"
            "};\n"
        )
        info = parse_header_text(text)
        self.assertEqual(info.values, (0x0001, 0x0002))

    def test_decimal_initializer(self) -> None:
        text = (
            "#define WALLPAPER_WIDTH 2\n"
            "#define WALLPAPER_HEIGHT 2\n"
            "const uint16_t wallpaper[4] = { 1, 2, 3, 4 };\n"
        )
        info = parse_header_text(text)
        self.assertEqual(info.values, (1, 2, 3, 4))

    def test_expression_size(self) -> None:
        text = (
            "#define WALLPAPER_WIDTH 2\n"
            "#define WALLPAPER_HEIGHT 2\n"
            "const uint16_t wallpaper[WALLPAPER_WIDTH * WALLPAPER_HEIGHT] = {\n"
            "    0x0001, 0x0002, 0x0003, 0x0004\n"
            "};\n"
        )
        info = parse_header_text(text)
        self.assertEqual(info.declared_count, 4)

    def test_empty_raises(self) -> None:
        with self.assertRaises(ConverterError) as context:
            parse_header_text("// nothing here\n")
        self.assertEqual(context.exception.code, "empty_values")

    def test_value_out_of_range(self) -> None:
        with self.assertRaises(ConverterError) as context:
            parse_header_text("const uint16_t wallpaper[1] = { 0x1FFFF };")
        self.assertEqual(context.exception.code, "value_range")

    @unittest.skipUnless(FIRMWARE_HEADER.exists(), "firmware header not available")
    def test_legacy_firmware_header(self) -> None:
        info = read_header(FIRMWARE_HEADER)
        self.assertEqual(len(info.values), 60160)
        self.assertEqual(info.declared_count, 60160)
        self.assertIsNone(info.width)
        self.assertIsNone(info.height)
        self.assertEqual(info.array_name, "wallpaper")
        suggestions = suggest_resolutions(len(info.values))
        self.assertIn(Resolution(320, 188), suggestions)


class SuggestResolutionsTest(unittest.TestCase):
    def test_preset_matches_first(self) -> None:
        results = suggest_resolutions(320 * 240)
        self.assertEqual(results[0], Resolution(320, 240))

    def test_multiple_matches(self) -> None:
        # 57600 == 240*240 (preset) and 320*180 (factor via preset width)
        results = suggest_resolutions(57600)
        self.assertIn(Resolution(240, 240), results)
        self.assertIn(Resolution(320, 180), results)

    def test_r4sgate_match(self) -> None:
        results = suggest_resolutions(320 * 188)
        self.assertIn(Resolution(320, 188), results)

    def test_invalid_count(self) -> None:
        self.assertEqual(suggest_resolutions(0), [])
        self.assertEqual(suggest_resolutions(-5), [])


class SaveImageTest(unittest.TestCase):
    def test_save_png_round_trip(self) -> None:
        image = Image.new("RGB", (7, 5), (40, 80, 120))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "out.png"
            converter.save_image(image, path)
            with Image.open(path) as restored:
                self.assertEqual(restored.format, "PNG")
                self.assertEqual(restored.size, (7, 5))
                self.assertEqual(restored.tobytes(), image.tobytes())

    def test_save_bmp_round_trip(self) -> None:
        image = Image.new("RGB", (7, 5), (40, 80, 120))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "out.bmp"
            converter.save_image(image, path)
            with Image.open(path) as restored:
                self.assertEqual(restored.format, "BMP")
                self.assertEqual(restored.size, (7, 5))

    def test_save_jpeg_round_trip(self) -> None:
        image = Image.new("RGB", (16, 16), (40, 80, 120))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "out.jpg"
            converter.save_image(image, path)
            with Image.open(path) as restored:
                self.assertEqual(restored.format, "JPEG")
                self.assertEqual(restored.size, (16, 16))

    def test_unsupported_save_suffix(self) -> None:
        image = Image.new("RGB", (2, 2))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "out.tiff"
            with self.assertRaises(ConverterError) as context:
                converter.save_image(image, path)
            self.assertEqual(context.exception.code, "unsupported_save_format")


class FileRoundTripTest(unittest.TestCase):
    def test_rejects_non_header_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wallpaper.txt"
            path.write_text("const uint16_t wallpaper[1] = { 0x0001 };", encoding="utf-8")
            with self.assertRaises(ConverterError) as context:
                read_header(path)
            self.assertEqual(context.exception.code, "unsupported_header")

    def test_write_and_read(self) -> None:
        resolution = Resolution(2, 2)
        values = [0x0001, 0x0002, 0x0003, 0x0004]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wallpaper.h"
            converter.write_header(path, values, resolution, "wallpaper")
            raw = path.read_bytes()
            self.assertNotIn(b"\r\n", raw)
            info = read_header(path)
            self.assertEqual(info.values, tuple(values))
            self.assertEqual((info.width, info.height), (2, 2))
            image = restore_image(info.values, resolution)
            png = converter.save_restored_png(path, image)
            self.assertTrue(png.exists())
            self.assertEqual(png.name, "wallpaper_restored.png")


if __name__ == "__main__":
    unittest.main()
