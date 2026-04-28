"""
Ilford HP5 Plus preset generation script
Analyzes snap/landscape sample images and saves to default_presets.json
NOTE: Saturation is forced to 0.0 (B&W film) after analysis.
"""

import sys
import numpy as np
from pathlib import Path
from PIL import Image as PILImage

sys.path.insert(0, str(Path(__file__).parent))

from src.preset_builder import save_preset, load_presets
from src.advanced_analyzer import AdvancedAnalyzer
from src.analyzer import FltParams, DEFAULT_SAFETY, SafetyLimits

SAMPLE_DIR  = Path(r"C:\Users\sakamoto\ilford_hp5_plus_samples")
PRESET_SNAP = "IlfordHP5Plus_スナップ"
PRESET_LAND = "IlfordHP5Plus_風景"

LOOSE_SAFETY = SafetyLimits(
    brightness_min=0.2, brightness_max=2.0,
    contrast_min=0.2,   contrast_max=2.0,
    saturation_min=0.0, saturation_max=2.0,
    gamma_min=0.2,      gamma_max=2.5,
)


def analyze_images(image_paths: list[Path]) -> tuple[FltParams, dict]:
    analyzer = AdvancedAnalyzer()
    all_params: list[FltParams] = []
    imgs = [PILImage.open(p).convert("RGB") for p in image_paths]
    print(f"  {len(imgs)} images loaded")

    for i, target in enumerate(imgs):
        others = [im for j, im in enumerate(imgs) if j != i]
        if not others:
            continue
        arr_others = np.mean(
            [np.array(im.resize((512, 512))) for im in others], axis=0
        ).astype("uint8")
        base_avg = PILImage.fromarray(arr_others)
        params, _ = analyzer.analyze(base_avg, target, safety=LOOSE_SAFETY)
        all_params.append(params)
        keys = ["brightness", "contrast", "saturation", "gamma_r", "gamma_g", "gamma_b"]
        print(f"  [{i+1}] " + "  ".join(f"{k}={getattr(params, k):.3f}" for k in keys))

    keys = ["brightness", "contrast", "saturation", "gamma_r", "gamma_g", "gamma_b"]
    means = {k: float(np.mean([getattr(p, k) for p in all_params])) for k in keys}
    stds  = {k: float(np.std( [getattr(p, k) for p in all_params])) for k in keys}

    avg_raw = FltParams(
        brightness=means["brightness"], contrast=means["contrast"],
        saturation=0.0,  # B&W film: force saturation to 0
        hue=0,
        gamma_r=means["gamma_r"], gamma_g=means["gamma_g"], gamma_b=means["gamma_b"],
    )
    avg_params = avg_raw.clamped(DEFAULT_SAFETY)
    avg_std   = float(np.mean(list(stds.values())))
    stability = max(0, int(100 - avg_std * 200))

    meta = {"n_images": len(image_paths), "std": {k: round(stds[k], 4) for k in keys},
            "stability": stability}
    return avg_params, meta


def main():
    snap_paths = sorted((SAMPLE_DIR / "snap").glob("*.jpg"))
    land_paths = sorted((SAMPLE_DIR / "landscape").glob("*.jpg"))

    print(f"\n=== {PRESET_SNAP} ({len(snap_paths)} images) ===")
    snap_params, snap_meta = analyze_images(snap_paths)
    print(f"  -> brightness={snap_params.brightness:.3f}  contrast={snap_params.contrast:.3f}  "
          f"saturation={snap_params.saturation:.3f}")
    print(f"     GammaR={snap_params.gamma_r:.3f}  GammaG={snap_params.gamma_g:.3f}  "
          f"GammaB={snap_params.gamma_b:.3f}")
    print(f"  -> stability={snap_meta['stability']}")
    save_preset(PRESET_SNAP, snap_params,
                {**snap_meta, "description": "Ilford HP5 Plus / snap"})
    print(f"  [OK] {PRESET_SNAP} saved")

    print(f"\n=== {PRESET_LAND} ({len(land_paths)} images) ===")
    land_params, land_meta = analyze_images(land_paths)
    print(f"  -> brightness={land_params.brightness:.3f}  contrast={land_params.contrast:.3f}  "
          f"saturation={land_params.saturation:.3f}")
    print(f"     GammaR={land_params.gamma_r:.3f}  GammaG={land_params.gamma_g:.3f}  "
          f"GammaB={land_params.gamma_b:.3f}")
    print(f"  -> stability={land_meta['stability']}")
    save_preset(PRESET_LAND, land_params,
                {**land_meta, "description": "Ilford HP5 Plus / landscape"})
    print(f"  [OK] {PRESET_LAND} saved")

    print("\n=== done ===")
    return snap_params, snap_meta, land_params, land_meta


if __name__ == "__main__":
    main()
