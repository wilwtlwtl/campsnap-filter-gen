"""
Generic single-preset generator.
Usage: python build_single_preset.py <sample_dir> <preset_name> <description>
"""

import sys
import numpy as np
from pathlib import Path
from PIL import Image as PILImage

sys.path.insert(0, str(Path(__file__).parent))

from src.preset_builder import save_preset
from src.advanced_analyzer import AdvancedAnalyzer
from src.analyzer import FltParams, DEFAULT_SAFETY, SafetyLimits

LOOSE_SAFETY = SafetyLimits(
    brightness_min=0.2, brightness_max=2.0,
    contrast_min=0.2,   contrast_max=2.0,
    saturation_min=0.0, saturation_max=2.0,
    gamma_min=0.2,      gamma_max=2.5,
)


def analyze_images(image_paths):
    analyzer = AdvancedAnalyzer()
    all_params = []
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
    means = {k: float(np.mean([getattr(p, k) for p in all_params])) for k in keys}
    stds  = {k: float(np.std( [getattr(p, k) for p in all_params])) for k in keys}

    avg_raw = FltParams(
        brightness=means["brightness"], contrast=means["contrast"],
        saturation=means["saturation"], hue=0,
        gamma_r=means["gamma_r"], gamma_g=means["gamma_g"], gamma_b=means["gamma_b"],
    )
    avg_params = avg_raw.clamped(DEFAULT_SAFETY)
    avg_std   = float(np.mean(list(stds.values())))
    stability = max(0, int(100 - avg_std * 200))

    meta = {"n_images": len(image_paths),
            "std": {k: round(stds[k], 4) for k in keys},
            "stability": stability}
    return avg_params, meta


def main():
    sample_dir = Path(sys.argv[1])
    preset_name = sys.argv[2]
    description = sys.argv[3]

    paths = sorted(list(sample_dir.glob("*.jpg")) + list(sample_dir.glob("*.jpeg"))
                   + list(sample_dir.glob("*.webp")))

    print(f"\n=== {preset_name} ({len(paths)} images) ===")
    params, meta = analyze_images(paths)
    print(f"  -> brightness={params.brightness:.3f}  contrast={params.contrast:.3f}  "
          f"saturation={params.saturation:.3f}")
    print(f"     GammaR={params.gamma_r:.3f}  GammaG={params.gamma_g:.3f}  "
          f"GammaB={params.gamma_b:.3f}")
    print(f"  -> stability={meta['stability']}")
    save_preset(preset_name, params, {**meta, "description": description})
    print(f"  [OK] {preset_name} saved")


if __name__ == "__main__":
    main()
