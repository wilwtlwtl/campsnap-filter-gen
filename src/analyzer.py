"""
Camp Snap V105 フィルターパラメータ解析モジュール
2枚の画像を比較し、.flt パラメータを推定する
"""

import numpy as np
from PIL import Image, ImageStat
from dataclasses import dataclass, field
from pathlib import Path
import configparser
import io


@dataclass
class SafetyLimits:
    """V105センサー性能を考慮したパラメータ安全範囲"""
    brightness_min: float = 0.5
    brightness_max: float = 1.6
    contrast_min: float = 0.6
    contrast_max: float = 1.4
    saturation_min: float = 0.0
    saturation_max: float = 1.5
    gamma_min: float = 0.5
    gamma_max: float = 1.8


# デフォルトのセーフティリミット（モジュールグローバル）
DEFAULT_SAFETY = SafetyLimits()


@dataclass
class FltParams:
    brightness: float = 1.0
    contrast: float = 1.0
    saturation: float = 1.0
    hue: int = 0
    gamma_r: float = 1.0
    gamma_g: float = 1.0
    gamma_b: float = 1.0

    def clamp(self, value: float, min_val: float, max_val: float) -> float:
        return round(max(min_val, min(max_val, value)), 3)

    def clamped(self, safety: SafetyLimits = DEFAULT_SAFETY) -> "FltParams":
        """セーフティリミット付きクランプ。warningsも返す。"""
        return FltParams(
            brightness=self.clamp(self.brightness, safety.brightness_min, safety.brightness_max),
            contrast=self.clamp(self.contrast, safety.contrast_min, safety.contrast_max),
            saturation=self.clamp(self.saturation, safety.saturation_min, safety.saturation_max),
            hue=max(-180, min(180, self.hue)),
            gamma_r=self.clamp(self.gamma_r, safety.gamma_min, safety.gamma_max),
            gamma_g=self.clamp(self.gamma_g, safety.gamma_min, safety.gamma_max),
            gamma_b=self.clamp(self.gamma_b, safety.gamma_min, safety.gamma_max),
        )

    def safety_warnings(self, safety: SafetyLimits = DEFAULT_SAFETY) -> list[str]:
        """クリッピングが発生したパラメータの警告メッセージ一覧を返す"""
        warnings = []
        checks = [
            ("Brightness",  self.brightness,  safety.brightness_min,  safety.brightness_max),
            ("Contrast",    self.contrast,    safety.contrast_min,    safety.contrast_max),
            ("Saturation",  self.saturation,  safety.saturation_min,  safety.saturation_max),
            ("GammaR",      self.gamma_r,     safety.gamma_min,       safety.gamma_max),
            ("GammaG",      self.gamma_g,     safety.gamma_min,       safety.gamma_max),
            ("GammaB",      self.gamma_b,     safety.gamma_min,       safety.gamma_max),
        ]
        for name, val, lo, hi in checks:
            if val < lo:
                warnings.append(f"{name} の推定値 {val:.3f} は下限 {lo} にクリッピングされました")
            elif val > hi:
                warnings.append(f"{name} の推定値 {val:.3f} は上限 {hi} にクリッピングされました")
        return warnings

    def blend(self, strength: float) -> "FltParams":
        """
        フィルター強度を 0.0〜1.0 で適用。
        0.0 = すべて 1.0（変化なし）、1.0 = フル適用。
        各パラメータを 1.0 との間で線形補間する。
        """
        s = max(0.0, min(1.0, strength))
        def _lerp(v): return 1.0 + (v - 1.0) * s
        return FltParams(
            brightness=round(_lerp(self.brightness), 3),
            contrast=round(_lerp(self.contrast), 3),
            saturation=round(_lerp(self.saturation), 3),
            hue=round(self.hue * s),
            gamma_r=round(_lerp(self.gamma_r), 3),
            gamma_g=round(_lerp(self.gamma_g), 3),
            gamma_b=round(_lerp(self.gamma_b), 3),
        )

    def to_dict(self) -> dict:
        return {
            "Brightness": self.brightness,
            "Contrast": self.contrast,
            "Saturation": self.saturation,
            "Hue": self.hue,
            "GammaR": self.gamma_r,
            "GammaG": self.gamma_g,
            "GammaB": self.gamma_b,
        }


class ImageAnalyzer:
    """
    Base画像とTarget画像を比較してFltParamsを推定する。

    推定ロジック概要:
      - Brightness: 輝度（L チャンネル平均）の比率
      - Contrast: 輝度の標準偏差の比率
      - Saturation: HSV 彩度平均の比率
      - GammaR/G/B: 各チャンネル平均の比率を対数変換でガンマに変換
    """

    # 標準的な写真の統計値（フォールバック用）
    DEFAULT_STATS = {
        "mean_l": 127.5,
        "std_l": 55.0,
        "mean_s": 0.35,
        "mean_r": 120.0,
        "mean_g": 118.0,
        "mean_b": 115.0,
    }

    def __init__(self, resize_to: tuple[int, int] = (512, 512)):
        self.resize_to = resize_to

    def _load(self, source) -> Image.Image:
        if isinstance(source, (str, Path)):
            img = Image.open(source)
        elif isinstance(source, bytes):
            img = Image.open(io.BytesIO(source))
        else:
            img = source  # PIL Image または file-like object

        img = img.convert("RGB")
        img = img.resize(self.resize_to, Image.LANCZOS)
        return img

    def _stats(self, img: Image.Image) -> dict:
        arr = np.array(img, dtype=np.float32)

        # RGB チャンネル平均
        mean_r = float(arr[:, :, 0].mean())
        mean_g = float(arr[:, :, 1].mean())
        mean_b = float(arr[:, :, 2].mean())

        # 輝度（L*a*b* の近似として 0.299R + 0.587G + 0.114B）
        luma = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
        mean_l = float(luma.mean())
        std_l = float(luma.std())

        # HSV 彩度
        hsv = np.array(img.convert("HSV"), dtype=np.float32)
        mean_s = float(hsv[:, :, 1].mean() / 255.0)

        return {
            "mean_l": mean_l,
            "std_l": std_l,
            "mean_s": mean_s,
            "mean_r": mean_r,
            "mean_g": mean_g,
            "mean_b": mean_b,
        }

    def _ratio_to_gamma(self, ratio: float) -> float:
        """
        チャンネル平均比率をガンマ値に変換。
        ガンマ補正: output = input ^ (1/gamma)
        平均輝度の比率 ≈ ratio^(1/gamma) を解いて gamma = log(ratio) / log(base_mean/255)
        簡易近似: gamma = 1 / ratio（比率が小さければガンマを大きく）
        より正確: gamma = log(target/255) / log(base/255)
        """
        eps = 1e-6
        base_norm = 0.5  # 中間輝度を基準（127.5/255）
        ratio = max(0.1, min(10.0, ratio))
        # ガンマ = log(target_norm) / log(base_norm) の近似
        # 比率 ≈ (base_norm)^(1/base_gamma) / (base_norm)^(1/target_gamma)
        # 簡易: gamma ∝ 1/ratio
        gamma = 1.0 / (ratio + eps)
        # 1.0 付近に正規化（ratio=1のとき gamma=1）
        gamma = gamma * ratio  # = 1.0 のとき ratio=1
        # 実用的な近似: target_mean/base_mean の逆数でガンマをスケール
        gamma = 1.0 / max(ratio, eps)
        # ratio > 1 → Targetの方が明るい → ガンマ < 1（持ち上げ効果を強める）
        # ratio < 1 → Targetの方が暗い → ガンマ > 1
        return gamma

    def analyze(self, base_source, target_source=None) -> FltParams:
        """
        base_source: Base画像（V105で撮った標準写真）
        target_source: Target画像（理想の色味の写真）。None の場合はデフォルト統計と比較。
        """
        base_img = self._load(base_source)
        base_stats = self._stats(base_img)

        if target_source is not None:
            target_img = self._load(target_source)
            target_stats = self._stats(target_img)
        else:
            target_stats = self.DEFAULT_STATS

        eps = 1e-6

        # --- Brightness ---
        # 輝度平均の比率（0-255スケール）
        brightness = target_stats["mean_l"] / max(base_stats["mean_l"], eps)

        # --- Contrast ---
        # 輝度標準偏差の比率
        contrast = target_stats["std_l"] / max(base_stats["std_l"], eps)

        # --- Saturation ---
        # HSV彩度の比率
        saturation = target_stats["mean_s"] / max(base_stats["mean_s"], eps)

        # --- Gamma per channel ---
        # 各チャンネルの平均比率をガンマ変換
        # gamma = log(target/255) / log(base/255) の形式を使う
        def channel_gamma(base_mean: float, target_mean: float) -> float:
            b = base_mean / 255.0
            t = target_mean / 255.0
            b = max(b, 0.01)
            t = max(t, 0.01)
            if abs(b - 0.5) < 0.05:
                # 中間付近は比率をそのまま使う
                return t / b
            try:
                g = np.log(t) / np.log(b)
            except Exception:
                g = 1.0
            # ガンマが 1.0 の逆数的な意味になるよう調整
            # V105では gamma>1 = 暗くなる方向
            return float(g)

        gamma_r = channel_gamma(base_stats["mean_r"], target_stats["mean_r"])
        gamma_g = channel_gamma(base_stats["mean_g"], target_stats["mean_g"])
        gamma_b = channel_gamma(base_stats["mean_b"], target_stats["mean_b"])

        raw = FltParams(
            brightness=brightness,
            contrast=contrast,
            saturation=saturation,
            hue=0,
            gamma_r=gamma_r,
            gamma_g=gamma_g,
            gamma_b=gamma_b,
        )
        warnings = raw.safety_warnings()
        return raw.clamped(), warnings

    def analyze_from_target_only(
        self, target_source, safety: "SafetyLimits" = None
    ) -> tuple["FltParams", list[str]]:
        """
        理想画像1枚だけからフィルターを推定する。
        DEFAULT_STATS を「標準的なV105の写り」と見なし、
        そこから target_source の色調に変換するパラメータを返す。
        """
        if safety is None:
            safety = DEFAULT_SAFETY
        target_img = self._load(target_source)
        target_stats = self._stats(target_img)
        base_stats = self.DEFAULT_STATS

        eps = 1e-6

        brightness = target_stats["mean_l"] / max(base_stats["mean_l"], eps)
        contrast   = target_stats["std_l"]  / max(base_stats["std_l"],  eps)
        saturation = target_stats["mean_s"] / max(base_stats["mean_s"], eps)

        def channel_gamma(base_mean, target_mean):
            b = max(base_mean / 255.0, 0.01)
            t = max(target_mean / 255.0, 0.01)
            if abs(b - 0.5) < 0.05:
                return t / b
            try:
                return float(np.log(t) / np.log(b))
            except Exception:
                return 1.0

        raw = FltParams(
            brightness=brightness,
            contrast=contrast,
            saturation=saturation,
            hue=0,
            gamma_r=channel_gamma(base_stats["mean_r"], target_stats["mean_r"]),
            gamma_g=channel_gamma(base_stats["mean_g"], target_stats["mean_g"]),
            gamma_b=channel_gamma(base_stats["mean_b"], target_stats["mean_b"]),
        )
        return raw.clamped(safety), raw.safety_warnings(safety)

    def analyze_with_debug(self, base_source, target_source=None) -> tuple[FltParams, dict]:
        """解析結果と中間統計値を両方返す（デバッグ・UI表示用）"""
        base_img = self._load(base_source)
        base_stats = self._stats(base_img)

        if target_source is not None:
            target_img = self._load(target_source)
            target_stats = self._stats(target_img)
        else:
            target_stats = self.DEFAULT_STATS

        params, warnings = self.analyze(base_source, target_source)

        debug = {
            "base_stats": base_stats,
            "target_stats": target_stats,
            "params": params.to_dict(),
            "warnings": warnings,
        }
        return params, debug
