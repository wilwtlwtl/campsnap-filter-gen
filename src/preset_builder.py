"""
複数の参考画像からプリセットを自動生成するモジュール
"""

import json
import numpy as np
from pathlib import Path
from dataclasses import dataclass, asdict
from PIL import Image

from .analyzer import ImageAnalyzer, FltParams, DEFAULT_SAFETY, SafetyLimits

PRESET_FILE         = Path(__file__).parent.parent / "presets.json"
DEFAULT_PRESET_FILE = Path(__file__).parent.parent / "default_presets.json"


# ── プリセット生成 ──────────────────────────────────────────────────────────

def build_preset_from_images(
    images: list,
    safety: SafetyLimits = DEFAULT_SAFETY,
) -> tuple[FltParams, dict]:
    """
    複数の参考画像を解析し、パラメータを平均してプリセットを生成する。

    images: PIL Image のリスト
    戻り値: (平均FltParams, 診断情報)
      診断情報: 各画像の個別パラメータ・平均・標準偏差
    """
    analyzer = ImageAnalyzer()
    all_params: list[FltParams] = []

    for img in images:
        params, _ = analyzer.analyze_from_target_only(img, safety=SafetyLimits(
            # 個別解析時は安全範囲を緩めに設定し、平均後に最終クランプ
            brightness_min=0.2, brightness_max=2.0,
            contrast_min=0.2,   contrast_max=2.0,
            saturation_min=0.2, saturation_max=2.0,
            gamma_min=0.2,      gamma_max=2.5,
        ))
        all_params.append(params)

    keys = ["brightness", "contrast", "saturation", "gamma_r", "gamma_g", "gamma_b"]

    # 各パラメータの配列を作成
    values = {k: np.array([getattr(p, k) for p in all_params]) for k in keys}

    # 平均・標準偏差
    means = {k: float(v.mean()) for k, v in values.items()}
    stds  = {k: float(v.std())  for k, v in values.items()}

    # 平均値から FltParams を生成し、最終的なセーフティクランプを適用
    avg_raw = FltParams(
        brightness=means["brightness"],
        contrast=means["contrast"],
        saturation=means["saturation"],
        hue=0,
        gamma_r=means["gamma_r"],
        gamma_g=means["gamma_g"],
        gamma_b=means["gamma_b"],
    )
    avg_params = avg_raw.clamped(safety)

    diag = {
        "n_images": len(images),
        "individual": [p.to_dict() for p in all_params],
        "mean": avg_params.to_dict(),
        "std": {k: round(stds[k], 4) for k in keys},
    }
    return avg_params, diag


# ── プリセットの保存・読み込み ────────────────────────────────────────────────
# ローカル環境: presets.json に永続保存
# クラウド環境: ファイル書き込みが再起動で消えるため、
#               PRESET_FILE が書き込み不可の場合はファイル操作をスキップする

def _file_writable() -> bool:
    try:
        PRESET_FILE.parent.mkdir(parents=True, exist_ok=True)
        PRESET_FILE.touch(exist_ok=True)
        return True
    except Exception:
        return False


def load_presets() -> dict[str, dict]:
    """
    保存済みプリセットを {名前: params_dict} で返す。
    default_presets.json（組み込み）とpresets.json（ユーザー作成）をマージし、
    同名の場合はユーザー作成側を優先する。
    """
    result = {}
    if DEFAULT_PRESET_FILE.exists():
        try:
            result.update(json.loads(DEFAULT_PRESET_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    if PRESET_FILE.exists():
        try:
            result.update(json.loads(PRESET_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    return result


def save_preset(name: str, params: FltParams, meta: dict | None = None) -> None:
    """プリセットを保存する。ファイル書き込み不可の場合はスキップ。"""
    presets = load_presets()
    presets[name] = {
        "params": params.to_dict(),
        "meta": meta or {},
    }
    if _file_writable():
        PRESET_FILE.write_text(
            json.dumps(presets, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def delete_preset(name: str) -> None:
    presets = load_presets()
    presets.pop(name, None)
    if _file_writable():
        PRESET_FILE.write_text(
            json.dumps(presets, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def preset_to_flt_params(name: str) -> FltParams | None:
    presets = load_presets()
    if name not in presets:
        return None
    d = presets[name]["params"]
    return FltParams(
        brightness=d.get("Brightness", 1.0),
        contrast=d.get("Contrast", 1.0),
        saturation=d.get("Saturation", 1.0),
        hue=d.get("Hue", 0),
        gamma_r=d.get("GammaR", 1.0),
        gamma_g=d.get("GammaG", 1.0),
        gamma_b=d.get("GammaB", 1.0),
    )
