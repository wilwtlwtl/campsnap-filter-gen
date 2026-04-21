"""
ヒストグラムマッチングベースのフィルター推定モジュール

処理の流れ:
  1. Base/Target 各チャンネルの累積分布関数(CDF)を計算
  2. CDF逆関数マッピングで LUT(256エントリの補正曲線)を生成
  3. LUT を V105 パラメータモデル(ガンマ・輝度・コントラスト・彩度)に最小二乗フィッティング
  4. FltParams として返す
"""

import numpy as np
from PIL import Image
import io
from pathlib import Path
from dataclasses import dataclass
from .analyzer import FltParams, SafetyLimits, DEFAULT_SAFETY


# ───────────────────────────────────────────
# 1. CDF / LUT ユーティリティ
# ───────────────────────────────────────────

def _cdf(channel: np.ndarray) -> np.ndarray:
    """uint8チャンネル(H,W)の正規化済みCDF(256エントリ)を返す"""
    hist, _ = np.histogram(channel.flatten(), bins=256, range=(0, 256))
    cdf = hist.cumsum().astype(np.float64)
    cdf /= cdf[-1]  # 0〜1 に正規化
    return cdf


def _build_lut(cdf_base: np.ndarray, cdf_target: np.ndarray) -> np.ndarray:
    """
    ヒストグラムマッチング LUT を生成する。
    各入力値 v に対して、cdf_base[v] ≈ cdf_target[lut[v]] となる lut[v] を求める。
    戻り値: shape (256,) uint8
    """
    lut = np.zeros(256, dtype=np.uint8)
    j = 0
    for v in range(256):
        while j < 255 and cdf_target[j] < cdf_base[v]:
            j += 1
        lut[v] = j
    return lut


# ───────────────────────────────────────────
# 2. LUT → パラメータ フィッティング
# ───────────────────────────────────────────

def _fit_gamma_brightness(lut: np.ndarray) -> tuple[float, float]:
    """
    LUT を  output = brightness * input^(1/gamma)  にフィット。

    log(output) = log(brightness) + (1/gamma) * log(input)

    入力0は除外し、log-log 線形回帰で (intercept=log_brightness, slope=1/gamma) を推定。
    戻り値: (gamma, brightness)
    """
    xs = np.arange(1, 256, dtype=np.float64)   # input  (1〜255)
    ys = lut[1:].astype(np.float64)
    ys = np.where(ys < 1, 1.0, ys)             # log(0) 回避

    log_x = np.log(xs / 255.0)
    log_y = np.log(ys / 255.0)

    # 最小二乗: log_y = slope * log_x + intercept
    A = np.column_stack([log_x, np.ones_like(log_x)])
    result, _, _, _ = np.linalg.lstsq(A, log_y, rcond=None)
    slope, intercept = result

    inv_gamma = float(slope)          # 1/gamma
    log_brightness = float(intercept)

    gamma = 1.0 / inv_gamma if abs(inv_gamma) > 1e-6 else 1.0
    brightness = float(np.exp(log_brightness))

    return gamma, brightness


def _fit_contrast(lut: np.ndarray) -> float:
    """
    LUT の中間域(10〜245)の傾き ≈ コントラスト係数を推定。
    midpoint=0.5 基準の線形変換: output = contrast * (input - 0.5) + 0.5
    → contrast ≈ d(output)/d(input) around midpoint
    """
    mid_slice = lut[10:246].astype(np.float64) / 255.0
    x = np.arange(10, 246, dtype=np.float64) / 255.0
    # 線形回帰で傾きを取得
    slope = float(np.polyfit(x, mid_slice, 1)[0])
    return max(0.1, slope)


def _fit_saturation(lut_s: np.ndarray) -> float:
    """
    彩度チャンネル(S)のLUTから彩度比率を推定。
    単純な中点比率（外れ値に強い）。
    """
    mid = 128
    out = float(lut_s[mid])
    return out / mid if mid > 0 else 1.0


# ───────────────────────────────────────────
# 3. 診断情報
# ───────────────────────────────────────────

@dataclass
class HistMatchDiag:
    """ヒストグラムマッチングの診断情報"""
    lut_r: np.ndarray
    lut_g: np.ndarray
    lut_b: np.ndarray
    lut_s: np.ndarray    # HSV 彩度チャンネル
    lut_v: np.ndarray    # HSV 明度チャンネル
    fit_gamma_r: float
    fit_gamma_g: float
    fit_gamma_b: float
    fit_brightness_r: float
    fit_brightness_g: float
    fit_brightness_b: float
    fit_brightness_v: float
    fit_contrast: float
    fit_saturation: float
    warnings: list[str]


# ───────────────────────────────────────────
# 4. メインクラス
# ───────────────────────────────────────────

class HistogramAnalyzer:
    """
    ヒストグラムマッチングで Base→Target の補正 LUT を求め、
    V105 .flt パラメータに変換する。
    """

    def __init__(self, resize_to: tuple[int, int] = (512, 512)):
        self.resize_to = resize_to

    def _load(self, source) -> Image.Image:
        if isinstance(source, (str, Path)):
            img = Image.open(source)
        elif isinstance(source, bytes):
            img = Image.open(io.BytesIO(source))
        else:
            img = source
        return img.convert("RGB").resize(self.resize_to, Image.LANCZOS)

    def analyze(
        self,
        base_source,
        target_source,
        safety: SafetyLimits = DEFAULT_SAFETY,
    ) -> tuple[FltParams, HistMatchDiag]:
        """
        base_source, target_source: ファイルパス / bytes / PIL Image
        戻り値: (クランプ済みFltParams, 診断情報)
        """
        base_img = self._load(base_source)
        target_img = self._load(target_source)

        base_rgb = np.array(base_img, dtype=np.uint8)
        target_rgb = np.array(target_img, dtype=np.uint8)

        base_hsv = np.array(base_img.convert("HSV"), dtype=np.uint8)
        target_hsv = np.array(target_img.convert("HSV"), dtype=np.uint8)

        # --- チャンネル分離 ---
        br, bg, bb = base_rgb[:,:,0], base_rgb[:,:,1], base_rgb[:,:,2]
        tr, tg, tb = target_rgb[:,:,0], target_rgb[:,:,1], target_rgb[:,:,2]
        bs, bv = base_hsv[:,:,1], base_hsv[:,:,2]
        ts, tv = target_hsv[:,:,1], target_hsv[:,:,2]

        # --- LUT 生成 ---
        lut_r = _build_lut(_cdf(br), _cdf(tr))
        lut_g = _build_lut(_cdf(bg), _cdf(tg))
        lut_b = _build_lut(_cdf(bb), _cdf(tb))
        lut_s = _build_lut(_cdf(bs), _cdf(ts))
        lut_v = _build_lut(_cdf(bv), _cdf(tv))

        # --- フィッティング ---
        gamma_r, br_factor = _fit_gamma_brightness(lut_r)
        gamma_g, bg_factor = _fit_gamma_brightness(lut_g)
        gamma_b, bb_factor = _fit_gamma_brightness(lut_b)
        _,       bv_factor = _fit_gamma_brightness(lut_v)

        # Brightness: RGB各チャンネルの輝度因子を輝度加重平均
        brightness = 0.299 * br_factor + 0.587 * bg_factor + 0.114 * bb_factor

        # Contrast: 明度(V)チャンネルのLUT傾き
        contrast = _fit_contrast(lut_v)

        # Saturation: 彩度(S)チャンネルのLUT中点比率
        saturation = _fit_saturation(lut_s)

        raw = FltParams(
            brightness=brightness,
            contrast=contrast,
            saturation=saturation,
            hue=0,
            gamma_r=gamma_r,
            gamma_g=gamma_g,
            gamma_b=gamma_b,
        )
        warnings = raw.safety_warnings(safety)
        clamped = raw.clamped(safety)

        diag = HistMatchDiag(
            lut_r=lut_r, lut_g=lut_g, lut_b=lut_b,
            lut_s=lut_s, lut_v=lut_v,
            fit_gamma_r=gamma_r, fit_gamma_g=gamma_g, fit_gamma_b=gamma_b,
            fit_brightness_r=br_factor, fit_brightness_g=bg_factor,
            fit_brightness_b=bb_factor, fit_brightness_v=bv_factor,
            fit_contrast=contrast,
            fit_saturation=saturation,
            warnings=warnings,
        )
        return clamped, diag
