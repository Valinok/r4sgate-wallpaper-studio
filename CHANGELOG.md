# Changelog

## v0.1.0 — 2026-11-03

### Добавлено

- GUI на Tkinter/ttk: меню, секции настроек, статус-бар, живой предпросмотр.
- Поддержка исходных изображений PNG, JPG/JPEG, BMP.
- Целевые разрешения: 320×240 (ILI9341), 240×320, 240×240, 170×320, 135×240,
  128×160, 320×188 (область обоев R4sGate) и произвольный размер.
- Режимы масштабирования: обрезка + масштаб (`ImageOps.fit`) и растяжение.
- Генерация `wallpaper.h` с `#pragma once`, `WALLPAPER_WIDTH/HEIGHT` и массивом
  `const uint16_t <name>[N]` (16 значений в строке).
- Открытие готовых `*.h`: автоопределение размеров, диалог выбора из
  подходящих разрешений, быстрое переключение разрешения над предпросмотром.
- Экспорт предпросмотра в PNG, JPG/JPEG, BMP.
- Локализация ru/en с автоматическим определением языка системы.
- Модульные тесты.
- Сборка одним исполняемым файлом через PyInstaller.

### Примечание

Этот релиз создан в режиме vibe coding с помощью ИИ; код может содержать
«нейрослоп». Перед использованием в прошивке рекомендуется проверять
сгенерированный `wallpaper.h`.

---

## v0.1.0 — 2026-11-03

### Added

- Tkinter/ttk GUI with menu, settings sections, status bar and live preview.
- Input images: PNG, JPG/JPEG, BMP.
- Target resolutions: 320×240 (ILI9341), 240×320, 240×240, 170×320, 135×240,
  128×160, 320×188 (R4sGate wallpaper area) and custom size.
- Resize modes: crop + resize (`ImageOps.fit`) and stretch.
- `wallpaper.h` generation with `#pragma once`, `WALLPAPER_WIDTH/HEIGHT` and
  `const uint16_t <name>[N]` array (16 values per line).
- Opening existing `*.h` headers: auto size detection, resolution selection
  dialog, quick resolution switching above the preview.
- Export preview to PNG, JPG/JPEG, BMP.
- ru/en localization with OS language auto-detection.
- Unit tests.
- Single-file executable build via PyInstaller.

### Note

This release was vibe-coded with AI assistance and may contain AI slop. Please
verify any generated `wallpaper.h` before flashing it to your device.
