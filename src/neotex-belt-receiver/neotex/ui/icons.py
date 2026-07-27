"""Painted vital-sign icons for MetricCards (no external image assets)."""

from __future__ import annotations

from PyQt5 import QtCore, QtGui


def _pen(color: str, width: float = 2.2) -> QtGui.QPen:
    pen = QtGui.QPen(QtGui.QColor(color))
    pen.setWidthF(width)
    pen.setCapStyle(QtCore.Qt.RoundCap)
    pen.setJoinStyle(QtCore.Qt.RoundJoin)
    return pen


def _brush(color: str, alpha: int = 70) -> QtGui.QBrush:
    c = QtGui.QColor(color)
    c.setAlpha(alpha)
    return QtGui.QBrush(c)


def icon_heart(color: str, size: int = 28) -> QtGui.QPixmap:
    pm = QtGui.QPixmap(size, size)
    pm.fill(QtCore.Qt.transparent)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    path = QtGui.QPainterPath()
    # Heart from two arcs + V
    s = float(size)
    path.moveTo(0.50 * s, 0.82 * s)
    path.cubicTo(0.12 * s, 0.58 * s, 0.08 * s, 0.28 * s, 0.32 * s, 0.22 * s)
    path.cubicTo(0.44 * s, 0.18 * s, 0.50 * s, 0.30 * s, 0.50 * s, 0.30 * s)
    path.cubicTo(0.50 * s, 0.30 * s, 0.56 * s, 0.18 * s, 0.68 * s, 0.22 * s)
    path.cubicTo(0.92 * s, 0.28 * s, 0.88 * s, 0.58 * s, 0.50 * s, 0.82 * s)
    p.setPen(_pen(color, 1.8))
    p.setBrush(_brush(color, 90))
    p.drawPath(path)
    p.end()
    return pm


def icon_lungs(color: str, size: int = 28) -> QtGui.QPixmap:
    pm = QtGui.QPixmap(size, size)
    pm.fill(QtCore.Qt.transparent)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    s = float(size)
    p.setPen(_pen(color, 1.9))
    p.setBrush(_brush(color, 55))
    # Left / right lobes
    p.drawEllipse(QtCore.QRectF(0.12 * s, 0.22 * s, 0.32 * s, 0.58 * s))
    p.drawEllipse(QtCore.QRectF(0.56 * s, 0.22 * s, 0.32 * s, 0.58 * s))
    # Trachea
    p.drawLine(QtCore.QPointF(0.50 * s, 0.12 * s), QtCore.QPointF(0.50 * s, 0.42 * s))
    p.drawLine(QtCore.QPointF(0.50 * s, 0.42 * s), QtCore.QPointF(0.34 * s, 0.52 * s))
    p.drawLine(QtCore.QPointF(0.50 * s, 0.42 * s), QtCore.QPointF(0.66 * s, 0.52 * s))
    p.end()
    return pm


def icon_o2(color: str, size: int = 28) -> QtGui.QPixmap:
    pm = QtGui.QPixmap(size, size)
    pm.fill(QtCore.Qt.transparent)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    s = float(size)
    p.setPen(_pen(color, 1.8))
    p.setBrush(_brush(color, 50))
    # Droplet / O2 badge
    path = QtGui.QPainterPath()
    path.moveTo(0.50 * s, 0.12 * s)
    path.cubicTo(0.78 * s, 0.38 * s, 0.78 * s, 0.72 * s, 0.50 * s, 0.88 * s)
    path.cubicTo(0.22 * s, 0.72 * s, 0.22 * s, 0.38 * s, 0.50 * s, 0.12 * s)
    p.drawPath(path)
    font = QtGui.QFont("Bahnschrift", max(7, int(size * 0.32)))
    font.setBold(True)
    p.setFont(font)
    p.setPen(QtGui.QColor(color))
    p.drawText(QtCore.QRectF(0, 0.28 * s, s, 0.5 * s), QtCore.Qt.AlignCenter, "O₂")
    p.end()
    return pm


def icon_thermometer(color: str, size: int = 28) -> QtGui.QPixmap:
    pm = QtGui.QPixmap(size, size)
    pm.fill(QtCore.Qt.transparent)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    s = float(size)
    p.setPen(_pen(color, 1.9))
    p.setBrush(_brush(color, 40))
    # Stem
    stem = QtCore.QRectF(0.42 * s, 0.10 * s, 0.16 * s, 0.52 * s)
    p.drawRoundedRect(stem, 3, 3)
    # Bulb
    p.setBrush(_brush(color, 110))
    p.drawEllipse(QtCore.QRectF(0.30 * s, 0.52 * s, 0.40 * s, 0.38 * s))
    # Mercury line
    p.setPen(_pen(color, 2.4))
    p.drawLine(QtCore.QPointF(0.50 * s, 0.22 * s), QtCore.QPointF(0.50 * s, 0.68 * s))
    p.end()
    return pm


def vital_icon(kind: str, color: str, size: int = 28) -> QtGui.QPixmap:
    kind = kind.lower()
    if kind in ("hr", "heart"):
        return icon_heart(color, size)
    if kind in ("rr", "lungs", "resp"):
        return icon_lungs(color, size)
    if kind in ("o2", "spo2", "oxygen"):
        return icon_o2(color, size)
    if kind in ("tmp", "temp", "thermometer"):
        return icon_thermometer(color, size)
    pm = QtGui.QPixmap(size, size)
    pm.fill(QtCore.Qt.transparent)
    return pm
