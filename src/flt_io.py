"""
.flt ファイルの読み書きモジュール
Camp Snap V105 独自フォーマット（CSV形式）に対応。

ファイル構造:
  行1: 7つのパラメータ
        Brightness(整数 = (倍率-1)*100), Contrast, Saturation, Hue, GammaR, GammaG, GammaB
  行2-4: 3x3 RGBカラーマトリックス（×1000の整数）
  行5-7: 各チャンネル256要素のトーンカーブ（0〜255）
"""

import numpy as np
from pathlib import Path
from .analyzer import FltParams


def save_flt(params: FltParams, path: str | Path) -> None:
    Path(path).write_text(_build_flt_text(params), encoding="utf-8")


def to_flt_bytes(params: FltParams) -> bytes:
    return _build_flt_text(params).encode("utf-8")


def load_flt(source) -> FltParams:
    if isinstance(source, (str, Path)):
        text = Path(source).read_text(encoding="utf-8")
    elif isinstance(source, bytes):
        text = source.decode("utf-8")
    else:
        text = source.read().decode("utf-8")
    return _parse_flt_text(text)


def _fmt(v: float) -> str:
    r = round(v, 2)
    if r == int(r):
        return str(int(r))
    return f"{r:g}"


def _build_flt_text(params: FltParams) -> str:
    lines: list[str] = []

    brightness_int = int(round((params.brightness - 1.0) * 100))
    line1 = (
        f"{brightness_int}, {_fmt(params.contrast)}, {_fmt(params.saturation)}, "
        f"{int(params.hue)}, {_fmt(params.gamma_r)}, {_fmt(params.gamma_g)}, {_fmt(params.gamma_b)}"
    )
    lines.append(line1)

    matrix = _saturation_matrix(params.saturation)
    for row in matrix:
        lines.append(", ".join(str(int(round(v * 1000))) for v in row))

    for ch_gamma in (params.gamma_r, params.gamma_g, params.gamma_b):
        curve = _tone_curve(params.brightness, params.contrast, ch_gamma)
        lines.append(", ".join(str(int(v)) for v in curve))

    return "\r\n".join(lines) + "\r\n"


def _saturation_matrix(s: float) -> list[list[float]]:
    lr, lg, lb = 0.3086, 0.6094, 0.0820
    sr = (1 - s) * lr
    sg = (1 - s) * lg
    sb = (1 - s) * lb
    return [
        [sr + s, sg, sb],
        [sr, sg + s, sb],
        [sr, sg, sb + s],
    ]


def _tone_curve(brightness: float, contrast: float, gamma: float) -> list[int]:
    x = np.arange(256) / 255.0
    y = np.power(x, 1.0 / max(gamma, 0.01))
    y = y * brightness
    y = (y - 0.5) * contrast + 0.5
    y = np.clip(y, 0, 1) * 255
    return np.round(y).astype(int).tolist()


def _parse_flt_text(text: str) -> FltParams:
    normalized = text.replace("\r\n", "\n")
    lines = [l.strip() for l in normalized.split("\n") if l.strip()]
    if not lines:
        raise ValueError("Empty .flt file")

    if lines[0].startswith("[Filter]"):
        return _parse_ini_format(text)

    parts = [v.strip() for v in lines[0].split(",")]
    if len(parts) != 7:
        raise ValueError(f"Expected 7 parameters in line 1, got {len(parts)}")

    brightness_int = float(parts[0])
    return FltParams(
        brightness=1.0 + brightness_int / 100.0,
        contrast=float(parts[1]),
        saturation=float(parts[2]),
        hue=int(float(parts[3])),
        gamma_r=float(parts[4]),
        gamma_g=float(parts[5]),
        gamma_b=float(parts[6]),
    )


def _parse_ini_format(text: str) -> FltParams:
    import configparser
    cp = configparser.ConfigParser()
    cp.read_string(text)
    sec = cp["Filter"]

    def f(key, default=1.0):
        return float(sec.get(key, default))

    return FltParams(
        brightness=f("Brightness"),
        contrast=f("Contrast"),
        saturation=f("Saturation"),
        hue=int(sec.get("Hue", 0)),
        gamma_r=f("GammaR"),
        gamma_g=f("GammaG"),
        gamma_b=f("GammaB"),
    )
