"""
RGB ヒストグラム計算・描画ユーティリティ
"""

import numpy as np
from PIL import Image
import pandas as pd


def compute_histogram(img: Image.Image, bins: int = 64) -> dict[str, np.ndarray]:
    """
    RGBおよび輝度チャンネルのヒストグラムを返す。
    戻り値: {"R": array, "G": array, "B": array, "輝度": array}
    各配列は bins 個の頻度値（0〜1に正規化済み）
    """
    arr = np.array(img.convert("RGB"), dtype=np.float32)
    result = {}
    for i, name in enumerate(["R", "G", "B"]):
        hist, _ = np.histogram(arr[:, :, i], bins=bins, range=(0, 256))
        result[name] = hist / hist.max()

    luma = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    hist, _ = np.histogram(luma, bins=bins, range=(0, 256))
    result["輝度"] = hist / hist.max()

    return result


def histogram_dataframe(
    before: Image.Image,
    after: Image.Image,
    bins: int = 64,
    channel: str = "輝度",
) -> pd.DataFrame:
    """
    before/after のヒストグラムを1つのDataFrameに結合して返す。
    Streamlit の line_chart に直接渡せる形式。
    """
    h_before = compute_histogram(before, bins)
    h_after  = compute_histogram(after,  bins)

    xs = np.linspace(0, 255, bins)
    return pd.DataFrame({
        f"適用前（{channel}）": h_before[channel],
        f"適用後（{channel}）": h_after[channel],
    }, index=xs.astype(int))


def all_channels_dataframe(img: Image.Image, bins: int = 64) -> pd.DataFrame:
    """単一画像のRGB+輝度ヒストグラムをDataFrameで返す"""
    h = compute_histogram(img, bins)
    xs = np.linspace(0, 255, bins).astype(int)
    return pd.DataFrame(h, index=xs)
