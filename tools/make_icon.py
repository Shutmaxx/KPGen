# -*- coding: utf-8 -*-
"""Создаёт иконку приложения в фирменных цветах ЕСТП."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

OUT = Path(__file__).resolve().parents[1] / "assets"
OUT.mkdir(exist_ok=True)

BACKGROUND = QColor("#18181B")
ACCENT = QColor("#5EAEC4")
TEXT = QColor("#FAFAFA")


def draw(size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    radius = size * 0.22
    painter.setBrush(QBrush(BACKGROUND))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(QRect(0, 0, size, size), radius, radius)

    # Бирюзовая «волна» снизу — как в презентации ЕСТП.
    painter.setBrush(QBrush(ACCENT))
    painter.drawEllipse(int(-size * 0.25), int(size * 0.62),
                        int(size * 0.95), int(size * 0.6))

    font = QFont("Arial", int(size * 0.34), QFont.Bold)
    painter.setFont(font)
    painter.setPen(TEXT)
    painter.drawText(QRect(0, int(size * 0.08), size, int(size * 0.5)),
                     Qt.AlignCenter, "КП")

    painter.end()
    return pixmap


def main() -> int:
    application = QApplication(sys.argv)

    sizes = [16, 24, 32, 48, 64, 128, 256]
    icon = QIcon()
    for size in sizes:
        pixmap = draw(size)
        icon.addPixmap(pixmap)
        if size == 256:
            pixmap.save(str(OUT / "icon.png"))

    # .ico собирается из набора размеров
    from PySide6.QtGui import QImageWriter  # noqa: F401
    pixmaps = [draw(s) for s in sizes]
    first = pixmaps[-1]
    first.save(str(OUT / "icon_256.png"))

    # Qt не пишет многоразмерный .ico, поэтому собираем вручную.
    _write_ico([draw(s) for s in (16, 32, 48, 64, 128, 256)], OUT / "icon.ico")
    print("иконка:", OUT / "icon.ico")
    application.quit()
    return 0


def _write_ico(pixmaps: list[QPixmap], path: Path) -> None:
    """Собирает .ico из нескольких PNG-изображений."""
    import struct
    from PySide6.QtCore import QBuffer, QByteArray

    images: list[bytes] = []
    for pixmap in pixmaps:
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QBuffer.WriteOnly)
        pixmap.save(buffer, "PNG")
        buffer.close()
        images.append(bytes(data))

    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries = b""
    for pixmap, blob in zip(pixmaps, images):
        size = pixmap.width()
        entries += struct.pack(
            "<BBBBHHII",
            0 if size >= 256 else size,
            0 if size >= 256 else size,
            0, 0, 1, 32, len(blob), offset,
        )
        offset += len(blob)

    path.write_bytes(header + entries + b"".join(images))


if __name__ == "__main__":
    raise SystemExit(main())
