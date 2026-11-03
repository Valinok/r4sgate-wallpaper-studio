"""Tests for :mod:`localization`."""

from __future__ import annotations

import unittest

import localization
from localization import (
    LANGUAGES,
    LANGUAGE_EN,
    LANGUAGE_RU,
    TRANSLATIONS,
    Localization,
    detect_system_language,
)


class TranslationTableTest(unittest.TestCase):
    def test_key_parity(self) -> None:
        english = set(TRANSLATIONS[LANGUAGE_EN])
        russian = set(TRANSLATIONS[LANGUAGE_RU])
        self.assertEqual(english, russian)

    def test_all_languages_present(self) -> None:
        self.assertEqual(set(LANGUAGES), {LANGUAGE_EN, LANGUAGE_RU})

    def test_placeholders_match(self) -> None:
        def placeholders(template: str) -> set[str]:
            result: set[str] = set()
            index = 0
            while True:
                start = template.find("{", index)
                if start < 0:
                    return result
                end = template.find("}", start)
                if end < 0:
                    return result
                result.add(template[start + 1 : end])
                index = end + 1

        for key, template in TRANSLATIONS[LANGUAGE_EN].items():
            self.assertEqual(
                placeholders(template),
                placeholders(TRANSLATIONS[LANGUAGE_RU][key]),
                msg=f"placeholder mismatch for {key}",
            )


class LocalizationTest(unittest.TestCase):
    def test_defaults_to_english_for_unknown(self) -> None:
        i18n = Localization("de")
        self.assertEqual(i18n.language, LANGUAGE_EN)

    def test_formatting(self) -> None:
        i18n = Localization(LANGUAGE_EN)
        self.assertEqual(
            i18n.t("source.info", width=320, height=188),
            "Source: 320 × 188 px",
        )

    def test_missing_parameter_returns_template(self) -> None:
        i18n = Localization(LANGUAGE_EN)
        self.assertIn("{width}", i18n.t("source.info"))

    def test_unknown_key_returns_key(self) -> None:
        i18n = Localization(LANGUAGE_EN)
        self.assertEqual(i18n.t("missing.key"), "missing.key")

    def test_error_lookup(self) -> None:
        i18n = Localization(LANGUAGE_RU)
        text = i18n.error("short_data", {"expected": 4, "found": 3})
        self.assertIn("4", text)
        self.assertIn("3", text)

    def test_listener_is_called_once_per_change(self) -> None:
        i18n = Localization(LANGUAGE_EN)
        calls: list[str] = []
        i18n.subscribe(lambda: calls.append(i18n.language))
        i18n.set_language(LANGUAGE_RU)
        i18n.set_language(LANGUAGE_RU)
        i18n.set_language("de")
        i18n.set_language(LANGUAGE_EN)
        self.assertEqual(calls, [LANGUAGE_RU, LANGUAGE_EN])

    def test_detect_returns_supported_language(self) -> None:
        self.assertIn(detect_system_language(), LANGUAGES)


if __name__ == "__main__":
    unittest.main()
