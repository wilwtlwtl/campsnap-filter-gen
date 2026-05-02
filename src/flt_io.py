"""
.flt ファイルの読み書きモジュール
Camp Snap V105 独自フォーマット（CSV形式）に対応。

ファイル構造:
  行1: 7つのパラメータ
        Brightness(整数 = (倍率-1)*100), Contrast, Saturation, Hue, GammaR, GammaG, GammaB
  行2-4: 3x3 RGBカラーマトリックス（×1024 の符号付き整数 = 10bit固定小数）
  行5-7: 各チャンネル256要素のトーンカーブ（0〜255）
  改行 LF, 末尾改行なし, BOMなし

公式の初期値ファイル例（Brightness=0, Contrast=1, Saturation=1, Hue=0, Gamma=1）:
  0, 1, 1, 0, 1, 1, 1
  1024, 0, 0
  0, 1024, 0
  0, 0, 1024
  0, 1, 2, ..., 255  (R)
  0, 1, 2, ..., 255  (G)
  0, 1, 2, ..., 255  (B)
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

    matrix = build_color_matrix(params.saturation, params.hue)
    for row in matrix:
        lines.append(", ".join(str(_clamp_int(v * 1024, -2048, 2047)) for v in row))

    for ch_gamma in (params.gamma_r, params.gamma_g, params.gamma_b):
        curve = build_tone_curve(params.brightness, params.contrast, ch_gamma)
        lines.append(", ".join(str(int(v)) for v in curve))

    return "\n".join(lines)


def _clamp_int(v: float, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(round(v))))


def build_color_matrix(saturation: float, hue_deg: float = 0.0) -> np.ndarray:
    """
    彩度マトリックス × 色相回転マトリックスの合成 3x3 RGB変換行列を返す。
    hue_deg = 0 のときは純粋な彩度マトリックス。
    """
    lr, lg, lb = 0.3086, 0.6094, 0.0820
    s = saturation
    sr = (1 - s) * lr
    sg = (1 - s) * lg
    sb = (1 - s) * lb
    sat_mat = np.array([
        [sr + s, sg, sb],
        [sr, sg + s, sb],
        [sr, sg, sb + s],
    ])

    if hue_deg == 0:
        return sat_mat

    a = np.deg2rad(hue_deg)
    cos_a = np.cos(a)
    sin_a = np.sin(a)
    hue_mat = np.array([
        [0.299 + 0.701 * cos_a + 0.168 * sin_a,
         0.587 - 0.587 * cos_a + 0.330 * sin_a,
         0.114 - 0.114 * cos_a - 0.497 * sin_a],
        [0.299 - 0.299 * cos_a - 0.328 * sin_a,
         0.587 + 0.413 * cos_a + 0.035 * sin_a,
         0.114 - 0.114 * cos_a + 0.292 * sin_a],
        [0.299 - 0.300 * cos_a + 1.250 * sin_a,
         0.587 - 0.588 * cos_a - 1.050 * sin_a,
         0.114 + 0.886 * cos_a - 0.203 * sin_a],
    ])

    return sat_mat @ hue_mat


def build_tone_curve(brightness: float, contrast: float, gamma: float) -> list[int]:
    """
    Brightness, Contrast, Gamma から256要素のトーンカーブを生成。
      base_a = 255*(1-contrast)/2 + brightness_int
      base_b = 255 - 255*(1-contrast)/2
      a = base_a + (gamma - 1) * 50            （黒レベル：Gammaシフト）
      b = base_b + (gamma - 1) * 7             （白レベル：Gammaシフト）
      core(x) = a + (b - a) * x^gamma          （ガンマカーブ）
      midtone_dip(x) = sin(π * x) * (1 - contrast) * 320   （contrast<1 で中央が凹む）
      y = core(x) - midtone_dip(x)
    """
    brightness_int = int(round((brightness - 1.0) * 100))
    margin = 255.0 * (1.0 - contrast) / 2.0
    base_a = margin + brightness_int
    base_b = 255.0 - margin
    g = max(gamma, 0.01)
    a = base_a + (g - 1.0) * 50.0
    b = base_b + (g - 1.0) * 7.0

    x = np.arange(256) / 255.0
    core = a + (b - a) * np.power(x, g)
    midtone_dip = np.sin(np.pi * x) * (1.0 - contrast) * 320.0
    y = core - midtone_dip
    y = np.clip(y, 0, 255)
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
