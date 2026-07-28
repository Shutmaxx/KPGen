# -*- coding: utf-8 -*-
"""Тёмная тема в стиле shadcn/ui (21st.dev) для Qt."""
from __future__ import annotations

# Палитра: нейтральные тона zinc + фирменный бирюзовый акцент ЕСТП.
BACKGROUND = "#09090B"
SURFACE = "#111113"
CARD = "#18181B"
CARD_HOVER = "#1F1F23"
BORDER = "#27272A"
BORDER_STRONG = "#3F3F46"
TEXT = "#FAFAFA"
TEXT_MUTED = "#A1A1AA"
TEXT_DIM = "#71717A"
ACCENT = "#5EAEC4"
ACCENT_HOVER = "#74B9C7"
ACCENT_PRESSED = "#4A94A8"
SUCCESS = "#4ADE80"
WARNING = "#FBBF24"
DANGER = "#F87171"

FONT_FAMILY = '"Segoe UI Variable Display", "Segoe UI", "Inter", sans-serif'
RADIUS = 10

STYLESHEET = f"""
* {{
    font-family: {FONT_FAMILY};
    color: {TEXT};
}}

QWidget#root, QDialog {{
    background-color: {BACKGROUND};
}}

QLabel {{
    background: transparent;
}}

QLabel#h1 {{
    font-size: 26px;
    font-weight: 700;
    letter-spacing: -0.4px;
}}

QLabel#h2 {{
    font-size: 18px;
    font-weight: 600;
    letter-spacing: -0.2px;
}}

QLabel#muted {{
    color: {TEXT_MUTED};
    font-size: 13px;
}}

QLabel#dim {{
    color: {TEXT_DIM};
    font-size: 12px;
}}

QLabel#stepBadge {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 4px 12px;
    color: {TEXT_MUTED};
    font-size: 12px;
    font-weight: 600;
}}

QLabel#stepBadgeActive {{
    background-color: {ACCENT};
    border: 1px solid {ACCENT};
    border-radius: 12px;
    padding: 4px 12px;
    color: #06232B;
    font-size: 12px;
    font-weight: 700;
}}

QFrame#card {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: {RADIUS}px;
}}

QFrame#dropZone {{
    background-color: {SURFACE};
    border: 2px dashed {BORDER_STRONG};
    border-radius: {RADIUS + 4}px;
}}

QFrame#dropZoneActive {{
    background-color: #10262C;
    border: 2px dashed {ACCENT};
    border-radius: {RADIUS + 4}px;
}}

QFrame#separator {{
    background-color: {BORDER};
    max-height: 1px;
    border: none;
}}

QPushButton {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: {RADIUS - 2}px;
    padding: 9px 18px;
    font-size: 13px;
    font-weight: 600;
}}

QPushButton:hover {{
    background-color: {CARD_HOVER};
    border-color: {BORDER_STRONG};
}}

QPushButton:pressed {{
    background-color: {BORDER};
}}

QPushButton:disabled {{
    color: {TEXT_DIM};
    background-color: {SURFACE};
    border-color: {BORDER};
}}

QPushButton#primary {{
    background-color: {ACCENT};
    border: 1px solid {ACCENT};
    color: #06232B;
}}

QPushButton#primary:hover {{
    background-color: {ACCENT_HOVER};
    border-color: {ACCENT_HOVER};
}}

QPushButton#primary:pressed {{
    background-color: {ACCENT_PRESSED};
}}

QPushButton#primary:disabled {{
    background-color: {BORDER};
    border-color: {BORDER};
    color: {TEXT_DIM};
}}

QPushButton#ghost {{
    background-color: transparent;
    border: 1px solid transparent;
    color: {TEXT_MUTED};
}}

QPushButton#ghost:hover {{
    background-color: {CARD};
    color: {TEXT};
}}

QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: {RADIUS - 2}px;
    padding: 9px 12px;
    font-size: 13px;
    selection-background-color: {ACCENT};
    selection-color: #06232B;
}}

QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus {{
    border-color: {ACCENT};
}}

QLineEdit:disabled, QPlainTextEdit:disabled {{
    color: {TEXT_DIM};
}}

QLineEdit#inn {{
    font-size: 20px;
    font-weight: 600;
    letter-spacing: 2px;
    padding: 12px 14px;
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox QAbstractItemView {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    selection-background-color: {ACCENT};
    selection-color: #06232B;
    padding: 4px;
}}

QProgressBar {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 6px;
    height: 8px;
    text-align: center;
    color: transparent;
}}

QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 5px;
}}

QCheckBox {{
    spacing: 8px;
    font-size: 13px;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 1px solid {BORDER_STRONG};
    border-radius: 5px;
    background-color: {SURFACE};
}}

QCheckBox::indicator:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
}}

QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: {RADIUS}px;
    background-color: {CARD};
    top: -1px;
}}

QTabBar::tab {{
    background: transparent;
    color: {TEXT_MUTED};
    padding: 9px 18px;
    margin-right: 4px;
    border: 1px solid transparent;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 600;
}}

QTabBar::tab:selected {{
    background-color: {CARD};
    color: {TEXT};
    border-color: {BORDER};
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}

QScrollBar::handle:vertical {{
    background: {BORDER_STRONG};
    border-radius: 5px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background: {TEXT_DIM};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
    height: 0;
}}

QToolTip {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    color: {TEXT};
}}
"""
