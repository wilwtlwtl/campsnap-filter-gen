"""
sRGB ↔ CIE Lab 色空間変換（外部ライブラリ不要）

Lab 色空間の利点:
  - L* : 人間の知覚に線形な明るさ (0=黒, 100=白)
  - a* : 赤↔緑軸 (正=赤み, 負=緑み)
  - b* : 黄↔青軸 (正=黄み・暖色, 負=青み・寒色)
  - CIEDE2000 に基づく色差計算が可能
"""

import numpy as np
from PIL import Image


def rgb_to_lab(img: Image.Image) -> np.ndarray:
    """
    PIL RGB 画像 → CIE Lab ndarray (H, W, 3) float64
    L: 0〜100, a: -128〜127, b: -128〜127
    """
    arr = np.array(img.convert("RGB"), dtype=np.float64) / 255.0

    # sRGB → 線形RGB（ガンマ除去）
    linear = np.where(
        arr > 0.04045,
        ((arr + 0.055) / 1.055) ** 2.4,
        arr / 12.92,
    )

    # 線形RGB → XYZ (D65照明)
    M = np.array([
        [0.4124564, 0.3575761, 0.1804375],
        [0.2126729, 0.7151522, 0.0721750],
        [0.0193339, 0.1191920, 0.9503041],
    ])
    xyz = linear @ M.T  # (H, W, 3)

    # D65 白色点で正規化
    xyz[:, :, 0] /= 0.95047
    xyz[:, :, 1] /= 1.00000
    xyz[:, :, 2] /= 1.08883

    # XYZ → Lab
    eps, kappa = 0.008856, 903.3
    f = np.where(
        xyz > eps,
        np.cbrt(np.clip(xyz, 0, None)),
        (kappa * xyz + 16.0) / 116.0,
    )
    L = 116.0 * f[:, :, 1] - 16.0
    a = 500.0 * (f[:, :, 0] - f[:, :, 1])
    b = 200.0 * (f[:, :, 1] - f[:, :, 2])

    return np.stack([L, a, b], axis=2)


def lab_stats(lab: np.ndarray) -> dict:
    """Lab 配列から基本統計量を返す"""
    return {
        "L_mean":    float(lab[:, :, 0].mean()),
        "L_std":     float(lab[:, :, 0].std()),
        "L_median":  float(np.median(lab[:, :, 0])),
        "a_mean":    float(lab[:, :, 1].mean()),
        "b_mean":    float(lab[:, :, 2].mean()),
        "chroma":    float(np.sqrt(lab[:, :, 1]**2 + lab[:, :, 2]**2).mean()),
    }


def region_masks(lab: np.ndarray) -> dict[str, np.ndarray]:
    """
    L* 値でシャドウ / ミッドトーン / ハイライトを分割。
    戻り値: bool マスク (H, W)
    """
    L = lab[:, :, 0]
    return {
        "shadow":    L < 35,
        "midtone":   (L >= 35) & (L < 70),
        "highlight": L >= 70,
    }
