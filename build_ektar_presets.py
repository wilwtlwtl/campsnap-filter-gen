"""
Ektar 100 プリセット生成スクリプト
スナップ3枚・風景3枚をそれぞれ解析し、presets.json に保存する。
"""

import sys
from pathlib import Path
from PIL import Image

# プロジェクトのsrcをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from src.preset_builder import build_preset_from_images, save_preset, load_presets
from src.advanced_analyzer import AdvancedAnalyzer
from src.analyzer import FltParams, DEFAULT_SAFETY, SafetyLimits

SAMPLE_DIR = Path(r"C:\Users\sakamoto\ektar100_samples")

LOOSE_SAFETY = SafetyLimits(
    brightness_min=0.2, brightness_max=2.0,
    contrast_min=0.2,   contrast_max=2.0,
    saturation_min=0.2, saturation_max=2.0,
    gamma_min=0.2,      gamma_max=2.5,
)


def analyze_images(image_paths: list[Path]) -> tuple[FltParams, dict]:
    """
    複数枚の画像を個別解析し、パラメータを平均してFltParamsを返す。
    AdvancedAnalyzer（高精度）を使用。base画像なしのため、
    画像間でクロス比較（1枚目を仮baseにして残りと対比）して平均を取る。
    """
    import numpy as np

    analyzer = AdvancedAnalyzer()
    all_params: list[FltParams] = []

    imgs = [Image.open(p).convert("RGB") for p in image_paths]
    print(f"  {len(imgs)}枚を読み込みました")

    # 各画像を他の画像の平均を「base」として解析
    for i, target in enumerate(imgs):
        others = [im for j, im in enumerate(imgs) if j != i]
        # others が 0枚の場合はスキップ（1枚のみは別処理）
        if not others:
            continue
        # others の平均画像を簡易的に作成
        arr_others = np.mean(
            [np.array(im.resize((512, 512))) for im in others], axis=0
        ).astype("uint8")
        from PIL import Image as PILImage
        base_avg = PILImage.fromarray(arr_others)

        params, diag = analyzer.analyze(base_avg, target, safety=LOOSE_SAFETY)
        all_params.append(params)
        tags = ["brightness", "contrast", "saturation", "gamma_r", "gamma_g", "gamma_b"]
        print(f"  [{i+1}] " + "  ".join(f"{k}={getattr(params, k):.3f}" for k in tags))

    # 平均化
    keys = ["brightness", "contrast", "saturation", "gamma_r", "gamma_g", "gamma_b"]
    means = {k: float(np.mean([getattr(p, k) for p in all_params])) for k in keys}
    stds  = {k: float(np.std( [getattr(p, k) for p in all_params])) for k in keys}

    avg_raw = FltParams(
        brightness=means["brightness"],
        contrast=means["contrast"],
        saturation=means["saturation"],
        hue=0,
        gamma_r=means["gamma_r"],
        gamma_g=means["gamma_g"],
        gamma_b=means["gamma_b"],
    )
    avg_params = avg_raw.clamped(DEFAULT_SAFETY)

    # 安定性スコア: 標準偏差の小ささを 0〜100 でスコア化
    avg_std = float(np.mean(list(stds.values())))
    stability = max(0, int(100 - avg_std * 200))

    meta = {
        "n_images": len(image_paths),
        "std": {k: round(stds[k], 4) for k in keys},
        "stability": stability,
    }
    return avg_params, meta


def main():
    snap_paths = sorted((SAMPLE_DIR / "snap").glob("*.jpg"))
    land_paths = sorted((SAMPLE_DIR / "landscape").glob("*.jpg"))

    print(f"\n=== スナップ写真 ({len(snap_paths)}枚) ===")
    snap_params, snap_meta = analyze_images(snap_paths)
    print(f"  → 平均パラメータ: {snap_params}")
    save_preset("Ektar100_スナップ", snap_params, snap_meta)
    print("  [OK] 'Ektar100_スナップ' を保存しました")

    print(f"\n=== 風景写真 ({len(land_paths)}枚) ===")
    land_params, land_meta = analyze_images(land_paths)
    print(f"  -> 平均パラメータ: {land_params}")
    save_preset("Ektar100_風景", land_params, land_meta)
    print("  [OK] 'Ektar100_風景' を保存しました")

    print("\n=== 保存済みプリセット一覧 ===")
    presets = load_presets()
    for name, data in presets.items():
        p = data["params"]
        m = data.get("meta", {})
        stability = m.get("stability", "-")
        n_images  = m.get("n_images", "-")
        print(f"  [{name}]  安定性:{stability}点  参考:{n_images}枚")
        print(f"    brightness={p.get('Brightness', 0):.3f}  contrast={p.get('Contrast', 0):.3f}  "
              f"saturation={p.get('Saturation', 0):.3f}")
        print(f"    GammaR={p.get('GammaR', 0):.3f}  GammaG={p.get('GammaG', 0):.3f}  "
              f"GammaB={p.get('GammaB', 0):.3f}")


if __name__ == "__main__":
    main()
