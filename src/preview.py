"""
フィルター適用 + V105センサーシミュレーション
"""

import numpy as np
from PIL import Image, ImageFilter
from .analyzer import FltParams


def apply_filter(img: Image.Image, params: FltParams) -> Image.Image:
    """
    FltParams をそのまま適用するクリーンなプレビュー。
    処理順: Gamma → Brightness → Contrast → Saturation
    """
    arr = np.array(img, dtype=np.float32) / 255.0

    arr[:, :, 0] = np.power(np.clip(arr[:, :, 0], 1e-6, 1.0), 1.0 / params.gamma_r)
    arr[:, :, 1] = np.power(np.clip(arr[:, :, 1], 1e-6, 1.0), 1.0 / params.gamma_g)
    arr[:, :, 2] = np.power(np.clip(arr[:, :, 2], 1e-6, 1.0), 1.0 / params.gamma_b)

    arr = arr * params.brightness
    arr = (arr - 0.5) * params.contrast + 0.5
    arr = np.clip(arr, 0.0, 1.0)

    result = Image.fromarray((arr * 255).astype(np.uint8), "RGB")
    if abs(params.saturation - 1.0) > 0.001:
        hsv = np.array(result.convert("HSV"), dtype=np.float32)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * params.saturation, 0, 255)
        result = Image.fromarray(hsv.astype(np.uint8), "HSV").convert("RGB")

    return result


def simulate_v105(img: Image.Image, params: FltParams, seed: int = 42) -> Image.Image:
    """
    フィルター適用後にV105センサーの物理的特性をシミュレートする。

    適用する効果（実機の特性に基づく推測）:
      1. フィルター適用
      2. 解像度ダウン→アップ（低解像センサーのボケ感）
      3. センサーノイズ（ISO感度固定＝高め）
      4. ダイナミックレンジ圧縮（8bitセンサーのクリッピング特性）
      5. わずかなビネット（周辺光量落ち）
      6. 固定の色温度オフセット（センサー固有の白バランス傾向）
    """
    rng = np.random.default_rng(seed)

    # 1. フィルター適用
    filtered = apply_filter(img, params)
    w, h = filtered.size

    # 2. 解像度ダウン→アップ（V105は低解像度固定: 실제 약 2MP相当）
    sensor_w, sensor_h = max(w // 4, 64), max(h // 4, 64)
    low_res = filtered.resize((sensor_w, sensor_h), Image.BILINEAR)
    upscaled = low_res.resize((w, h), Image.BILINEAR)
    # ソフトネスを足す
    upscaled = upscaled.filter(ImageFilter.GaussianBlur(radius=1.2))

    arr = np.array(upscaled, dtype=np.float32) / 255.0

    # 3. センサーノイズ（固定高ISO＝ルミナンスノイズ + カラーノイズ）
    luma_noise = rng.normal(0, 0.025, arr.shape[:2])          # 輝度ノイズ
    color_noise = rng.normal(0, 0.012, arr.shape)             # カラーノイズ
    arr[:, :, 0] += luma_noise + color_noise[:, :, 0]
    arr[:, :, 1] += luma_noise + color_noise[:, :, 1]
    arr[:, :, 2] += luma_noise + color_noise[:, :, 2]

    # 4. ダイナミックレンジ圧縮（ハイライト・シャドウのロールオフ）
    # シャドウ持ち上げ（黒つぶれ軽減の逆: V105はシャドウが潰れやすい）
    arr = np.where(arr < 0.12, arr * 0.6, arr)
    # ハイライトロールオフ（白飛び: 0.85以上で圧縮）
    arr = np.where(arr > 0.85, 0.85 + (arr - 0.85) * 0.4, arr)

    arr = np.clip(arr, 0.0, 1.0)

    # 5. ビネット（周辺光量落ち）
    ys = np.linspace(-1, 1, h)[:, np.newaxis]
    xs = np.linspace(-1, 1, w)[np.newaxis, :]
    vignette = 1.0 - 0.25 * (xs**2 + ys**2)   # 周辺で最大 25% 減
    arr *= vignette[:, :, np.newaxis]

    # 6. センサー固有の色温度オフセット（V105は若干マゼンタ寄り傾向）
    arr[:, :, 0] = np.clip(arr[:, :, 0] * 1.04, 0, 1)   # R わずかに強調
    arr[:, :, 2] = np.clip(arr[:, :, 2] * 0.96, 0, 1)   # B わずかに抑制

    arr = np.clip(arr, 0.0, 1.0)
    return Image.fromarray((arr * 255).astype(np.uint8), "RGB")
