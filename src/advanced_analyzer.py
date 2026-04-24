"""
高精度フィルター推定エンジン

① Lab色空間解析:
   - CIE Lab 色空間で Brightness / Contrast / Saturation を推定
   - a*/b* 軸から暖色・寒色のカラーキャストを検出

② 分割領域解析:
   - シャドウ(L<35) / ミッドトーン(35-70) / ハイライト(L≧70) に分けて
     各領域のRGB平均比率からGammaを推定し、領域サイズで加重平均

③ スプライン階調曲線フィッティング:
   - ヒストグラムマッチングLUTを CubicSpline で平滑化
   - log-log 回帰より正確なガンマ + 輝度推定
   - ミッドトーン重みを加えた最小二乗フィット
"""

import numpy as np
from PIL import Image
from scipy.interpolate import CubicSpline
from dataclasses import dataclass
from pathlib import Path
import io

from .analyzer import FltParams, SafetyLimits, DEFAULT_SAFETY
from .lab_utils import rgb_to_lab, lab_stats, region_masks
from .hist_analyzer import _cdf, _build_lut


# ── スプライン平滑化 + Gamma フィッティング ──────────────────────────────────

def _spline_fit_gamma_brightness(lut: np.ndarray) -> tuple[float, float]:
    """
    LUT(256エントリ) を CubicSpline で平滑化し、
    ミッドトーン重み付き log-log 回帰で gamma + brightness を推定。

    現在の単純log-log回帰との違い:
      - スプライン平滑化でノイズを除去してから回帰
      - ミッドトーン域(64-192)に3倍の重みをかける（目視で重要な領域）
    """
    # 制御点を間引いてスプライン構築（16px間隔）
    xs_ctrl = np.arange(0, 256, 16, dtype=float)
    ys_ctrl = lut[xs_ctrl.astype(int)].astype(float)
    ys_ctrl = np.clip(ys_ctrl, 0.5, 255)

    cs = CubicSpline(xs_ctrl, ys_ctrl, extrapolate=True)

    # 1〜254 で評価
    xs = np.arange(1, 255, dtype=float)
    ys = np.clip(cs(xs), 0.5, 255)

    log_x = np.log(xs / 255.0)
    log_y = np.log(ys / 255.0)

    # ミッドトーン重み（64〜192 を 3倍に重視）
    weights = np.where((xs >= 64) & (xs <= 192), 3.0, 1.0)

    # 重み付き最小二乗: log_y = slope * log_x + intercept
    W = np.diag(weights)
    A = np.column_stack([log_x, np.ones_like(log_x)])
    AW = A.T @ W
    result = np.linalg.solve(AW @ A, AW @ log_y)
    slope, intercept = result

    gamma      = float(1.0 / slope) if abs(slope) > 1e-6 else 1.0
    brightness = float(np.exp(intercept))
    return gamma, brightness


# ── 分割領域 Gamma 推定 ────────────────────────────────────────────────────

def _region_gamma(
    base_ch: np.ndarray,
    target_ch: np.ndarray,
    mask: np.ndarray,
) -> float | None:
    """
    特定領域のマスク内ピクセルで、チャンネル平均比からガンマを推定。
    ピクセル数が少ない場合は None を返す。
    """
    if mask.sum() < 200:
        return None

    b = float(base_ch[mask].mean()) / 255.0
    t = float(target_ch[mask].mean()) / 255.0
    b = max(b, 0.02)
    t = max(t, 0.02)

    if abs(b - 0.5) < 0.08:
        return t / b
    try:
        return float(np.log(t) / np.log(b))
    except Exception:
        return None


def _weighted_gamma(gammas: list[float | None], weights: list[float]) -> float:
    """有効なガンマ値を重み付き平均する"""
    total_w, total_v = 0.0, 0.0
    for g, w in zip(gammas, weights):
        if g is not None and 0.1 <= g <= 5.0:
            total_v += g * w
            total_w += w
    return total_v / total_w if total_w > 0 else 1.0


# ── 診断情報 ────────────────────────────────────────────────────────────────

@dataclass
class AdvancedDiag:
    lab_base:    dict
    lab_target:  dict
    region_weights: dict        # {"shadow": n, "midtone": n, "highlight": n}
    gamma_by_region: dict       # {"R": {"shadow": v, ...}, ...}
    spline_gamma:    dict       # {"R": v, "G": v, "B": v}
    final_params:    FltParams
    warnings:        list[str]


# ── メインクラス ─────────────────────────────────────────────────────────────

class AdvancedAnalyzer:
    """
    Lab解析 + 分割領域解析 + スプライン階調フィッティングの統合エンジン。

    パラメータ推定の優先度:
      Brightness / Contrast → Lab L* チャンネルから（知覚精度が高い）
      Saturation            → Lab Chroma（色度）から
      GammaR/G/B            → スプラインLUTフィッティング + 分割領域の加重平均
    """

    REGION_WEIGHTS = {"shadow": 0.25, "midtone": 0.55, "highlight": 0.20}

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
    ) -> tuple[FltParams, AdvancedDiag]:

        base_img   = self._load(base_source)
        target_img = self._load(target_source)

        base_arr   = np.array(base_img,   dtype=np.uint8)
        target_arr = np.array(target_img, dtype=np.uint8)

        # ────────────────────────────────────────────────────────────────
        # ① Lab 色空間解析
        # ────────────────────────────────────────────────────────────────
        base_lab   = rgb_to_lab(base_img)
        target_lab = rgb_to_lab(target_img)

        bs = lab_stats(base_lab)
        ts = lab_stats(target_lab)

        eps = 1e-6

        # Brightness: L*平均の比（L*は0-100なのでスケール換算）
        brightness = (ts["L_mean"] + eps) / (bs["L_mean"] + eps)

        # Contrast: L*標準偏差の比
        contrast = (ts["L_std"] + eps) / (bs["L_std"] + eps)

        # Saturation: 色度（chroma）の比
        saturation = (ts["chroma"] + eps) / (bs["chroma"] + eps)

        # ────────────────────────────────────────────────────────────────
        # ② 分割領域解析（GammaR/G/B の精度向上）
        # ────────────────────────────────────────────────────────────────
        masks = region_masks(base_lab)   # シャドウ/ミッドトーン/ハイライト

        region_pixel_counts = {
            k: int(v.sum()) for k, v in masks.items()
        }

        gamma_by_region: dict[str, dict] = {"R": {}, "G": {}, "B": {}}
        for region_name, mask in masks.items():
            for ch_idx, ch_name in enumerate(["R", "G", "B"]):
                g = _region_gamma(
                    base_arr[:, :, ch_idx],
                    target_arr[:, :, ch_idx],
                    mask,
                )
                gamma_by_region[ch_name][region_name] = g

        # 領域ごとの重みを画素数比でさらに調整
        total_px = max(sum(region_pixel_counts.values()), 1)
        adaptive_weights = {
            k: self.REGION_WEIGHTS[k] * (region_pixel_counts[k] / total_px * 3 + 0.1)
            for k in masks
        }
        # 正規化
        w_sum = sum(adaptive_weights.values())
        adaptive_weights = {k: v / w_sum for k, v in adaptive_weights.items()}

        region_gamma_r = _weighted_gamma(
            [gamma_by_region["R"][r] for r in masks],
            [adaptive_weights[r] for r in masks],
        )
        region_gamma_g = _weighted_gamma(
            [gamma_by_region["G"][r] for r in masks],
            [adaptive_weights[r] for r in masks],
        )
        region_gamma_b = _weighted_gamma(
            [gamma_by_region["B"][r] for r in masks],
            [adaptive_weights[r] for r in masks],
        )

        # ────────────────────────────────────────────────────────────────
        # ③ スプライン階調曲線フィッティング（GammaR/G/B の補正）
        # ────────────────────────────────────────────────────────────────
        spline_gammas = {}
        spline_brightness = {}
        for ch_idx, ch_name in enumerate(["R", "G", "B"]):
            lut = _build_lut(
                _cdf(base_arr[:, :, ch_idx]),
                _cdf(target_arr[:, :, ch_idx]),
            )
            g, b = _spline_fit_gamma_brightness(lut)
            spline_gammas[ch_name]     = g
            spline_brightness[ch_name] = b

        # 最終Gamma: スプライン(60%) + 分割領域(40%) のブレンド
        SPLINE_W, REGION_W = 0.6, 0.4
        gamma_r = spline_gammas["R"] * SPLINE_W + region_gamma_r * REGION_W
        gamma_g = spline_gammas["G"] * SPLINE_W + region_gamma_g * REGION_W
        gamma_b = spline_gammas["B"] * SPLINE_W + region_gamma_b * REGION_W

        # ────────────────────────────────────────────────────────────────
        # Lab の a*/b* カラーキャスト → Gamma への微補正
        # ────────────────────────────────────────────────────────────────
        # Δb > 0 → target が暖色寄り → Rを持ち上げ(gamma_r↓)、Bを抑え(gamma_b↑)
        delta_b = ts["b_mean"] - bs["b_mean"]
        delta_a = ts["a_mean"] - bs["a_mean"]
        cast_scale = 0.015   # 補正感度（大きすぎると過補正）

        gamma_r = gamma_r - delta_b * cast_scale + delta_a * cast_scale
        gamma_g = gamma_g - delta_a * cast_scale * 0.5
        gamma_b = gamma_b + delta_b * cast_scale

        # ────────────────────────────────────────────────────────────────
        # セーフティクランプ
        # ────────────────────────────────────────────────────────────────
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
        clamped  = raw.clamped(safety)

        diag = AdvancedDiag(
            lab_base=bs,
            lab_target=ts,
            region_weights=adaptive_weights,
            gamma_by_region=gamma_by_region,
            spline_gamma=spline_gammas,
            final_params=clamped,
            warnings=warnings,
        )
        return clamped, diag
