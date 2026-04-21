"""
フェーズ1 動作確認スクリプト
合成テスト画像を使って解析ロジックとflt生成を検証する
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
from PIL import Image
import io

from src.analyzer import ImageAnalyzer, FltParams
from src.flt_io import save_flt, load_flt, to_flt_bytes


def make_test_image(mean_rgb: tuple, std: float = 40, size=(512, 512)) -> Image.Image:
    """指定した平均色・分散のテスト画像を生成"""
    r, g, b = mean_rgb
    noise = np.random.normal(0, std, (*size, 3))
    arr = np.clip(
        np.stack([
            np.full(size, r) + noise[:, :, 0],
            np.full(size, g) + noise[:, :, 1],
            np.full(size, b) + noise[:, :, 2],
        ], axis=2),
        0, 255
    ).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def print_params(label: str, params: FltParams):
    print(f"\n=== {label} ===")
    for k, v in params.to_dict().items():
        print(f"  {k}: {v}")


def test_case(name, base_rgb, target_rgb, base_std=40, target_std=40):
    print(f"\n{'='*50}")
    print(f"テストケース: {name}")
    print(f"  Base RGB平均: {base_rgb}, std={base_std}")
    print(f"  Target RGB平均: {target_rgb}, std={target_std}")

    base_img = make_test_image(base_rgb, std=base_std)
    target_img = make_test_image(target_rgb, std=target_std)

    analyzer = ImageAnalyzer()
    params, debug = analyzer.analyze_with_debug(base_img, target_img)

    print("\n  [中間統計値]")
    for k, v in debug["base_stats"].items():
        print(f"    Base  {k}: {v:.2f}")
    for k, v in debug["target_stats"].items():
        print(f"    Target {k}: {v:.2f}")

    print_params("推定パラメータ", params)

    # .flt バイト生成テスト
    flt_bytes = to_flt_bytes(params)
    print("\n  [.flt 内容]")
    print(flt_bytes.decode())

    # 読み込みラウンドトリップテスト
    loaded = load_flt(flt_bytes)
    assert abs(loaded.brightness - params.brightness) < 0.001, "Brightness ラウンドトリップ失敗"
    assert abs(loaded.gamma_r - params.gamma_r) < 0.001, "GammaR ラウンドトリップ失敗"
    print("  [OK] .flt 読み書きラウンドトリップ成功")


def main():
    print("Camp Snap V105 フィルター解析 - フェーズ1 テスト")

    # ケース1: 同一画像（パラメータはすべて 1.0 付近になるはず）
    test_case(
        name="同一画像（変化なし）",
        base_rgb=(120, 118, 115),
        target_rgb=(120, 118, 115),
    )

    # ケース2: Target が全体的に明るい
    test_case(
        name="Target が明るい",
        base_rgb=(100, 98, 95),
        target_rgb=(160, 158, 155),
    )

    # ケース3: Target がフィルム風（暖色・低彩度・コントラスト低め）
    test_case(
        name="フィルム風（暖色・低コントラスト）",
        base_rgb=(120, 118, 115),
        target_rgb=(155, 130, 100),
        base_std=50,
        target_std=30,
    )

    # ケース4: シングル画像（フォールバック）
    test_case(
        name="シングル画像（フォールバック使用）",
        base_rgb=(120, 118, 115),
        target_rgb=None,  # フォールバック
        base_std=40,
        target_std=40,
    )

    print("\n\nすべてのテスト完了")


if __name__ == "__main__":
    # ケース4のみ特別処理（target_rgb=None）
    import numpy as np
    from PIL import Image

    print("Camp Snap V105 フィルター解析 - フェーズ1 テスト")

    cases = [
        ("同一画像（変化なし）",     (120, 118, 115), (120, 118, 115), 40, 40),
        ("Target が明るい",          (100,  98,  95), (160, 158, 155), 40, 40),
        ("フィルム風（暖色）",        (120, 118, 115), (155, 130, 100), 50, 30),
    ]

    for name, base_rgb, target_rgb, base_std, target_std in cases:
        test_case(name, base_rgb, target_rgb, base_std, target_std)

    # フォールバックケース
    print(f"\n{'='*50}")
    print("テストケース: シングル画像（フォールバック）")
    base_img = make_test_image((90, 88, 85))
    analyzer = ImageAnalyzer()
    params, debug = analyzer.analyze_with_debug(base_img, target_source=None)
    print_params("推定パラメータ（フォールバック）", params)
    flt_bytes = to_flt_bytes(params)
    print("\n  [.flt 内容]")
    print(flt_bytes.decode())
    print("  [OK] フォールバックモード成功")

    print("\n\nすべてのテスト完了")
