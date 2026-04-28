"""
12プリセットフィルター比較グリッド画像生成スクリプト
sample_base.jpg に全プリセットを適用して 4x3 グリッドで並べた PNG を出力する。
"""

import sys
import json
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))

from src.preview import apply_filter
from src.analyzer import FltParams

SNAP_IMAGE  = Path(__file__).parent / "sample_snap.jpg"
LAND_IMAGE  = Path(__file__).parent / "sample_landscape.jpg"
PRESET_FILE = Path(__file__).parent / "default_presets.json"
OUTPUT_FILE = Path(__file__).parent / "filter_preview_grid.png"

COLS    = 4
CELL_W  = 360
CELL_H  = 240
LABEL_H = 40
PAD     = 6
HEADER_H = 54

BG        = (18, 18, 18)
HEADER_BG = (32, 32, 32)
LABEL_BG  = (26, 26, 26)
LABEL_FG  = (220, 220, 220)
HEADER_FG = (255, 255, 255)
ACCENT    = (170, 145, 80)

SHORT_NAMES = {
    "KodakEktar100":   "Ektar 100",
    "FujiSuperia400":  "Superia 400",
    "FujiPro400H":     "Fuji Pro 400H",
    "Cinestill800T":   "Cinestill 800T",
    "KodakPortra800":  "Portra 800",
    "AgfaVista200":    "Agfa Vista 200",
    "LomoLadyGrey400": "Lady Grey 400 (B&W)",
    "KodakTriX400":    "Tri-X 400 (B&W)",
    "IlfordHP5Plus":   "HP5 Plus (B&W)",
}

SUFFIX_JP = {
    "_スナップ": " / Snap",
    "_風景":     " / Landscape",
}


def short_name(key: str) -> str:
    for film, label in SHORT_NAMES.items():
        if key.startswith(film):
            rest = key[len(film):]
            suffix = SUFFIX_JP.get(rest, rest.replace("_", " "))
            return label + suffix
    return key.replace("_", " ")


def load_params(d: dict) -> FltParams:
    p = d["params"]
    return FltParams(
        brightness=p["Brightness"], contrast=p["Contrast"],
        saturation=p["Saturation"], hue=p.get("Hue", 0),
        gamma_r=p["GammaR"], gamma_g=p["GammaG"], gamma_b=p["GammaB"],
    )


def crop_center(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    bw, bh = img.size
    ratio = target_w / target_h
    if bw / bh > ratio:
        new_w = int(bh * ratio)
        left = (bw - new_w) // 2
        img = img.crop((left, 0, left + new_w, bh))
    else:
        new_h = int(bw / ratio)
        top = (bh - new_h) // 2
        img = img.crop((0, top, bw, top + new_h))
    return img.resize((target_w, target_h), Image.LANCZOS)


def get_font(size: int):
    candidates = [
        "C:/Windows/Fonts/YuGothM.ttc",
        "C:/Windows/Fonts/YuGothR.ttc",
        "C:/Windows/Fonts/msgothic.ttc",
        "C:/Windows/Fonts/meiryo.ttc",
    ]
    for fp in candidates:
        try:
            return ImageFont.truetype(fp, size)
        except Exception:
            continue
    return ImageFont.load_default()


def draw_text_centered(draw, text, font, x, y, w, h, color):
    bb = draw.textbbox((0, 0), text, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    draw.text((x + (w - tw) // 2, y + (h - th) // 2), text, fill=color, font=font)


def main():
    presets = json.loads(PRESET_FILE.read_text(encoding="utf-8"))
    snap_keys = [k for k in presets if k.endswith("_スナップ")]
    land_keys = [k for k in presets if k.endswith("_風景")]
    keys = snap_keys + land_keys
    n = len(keys)
    rows = (n + COLS - 1) // COLS

    base_snap = crop_center(Image.open(SNAP_IMAGE).convert("RGB"), CELL_W, CELL_H)
    base_land = crop_center(Image.open(LAND_IMAGE).convert("RGB"), CELL_W, CELL_H)

    total_w = PAD + COLS * (CELL_W + PAD)
    total_h = HEADER_H + PAD + rows * (CELL_H + LABEL_H + PAD)

    grid = Image.new("RGB", (total_w, total_h), BG)
    draw = ImageDraw.Draw(grid)

    # ヘッダー
    draw.rectangle([0, 0, total_w, HEADER_H], fill=HEADER_BG)
    draw.rectangle([0, HEADER_H - 3, total_w, HEADER_H], fill=ACCENT)

    font_title  = get_font(18)
    font_label  = get_font(14)

    title = f"CampSnap V105  |  Filter Presets  ({n} kinds)"
    draw_text_centered(draw, title, font_title, 0, 0, total_w, HEADER_H - 3, HEADER_FG)

    # フィルターセル
    for idx, key in enumerate(keys):
        col = idx % COLS
        row = idx // COLS
        x = PAD + col * (CELL_W + PAD)
        y = HEADER_H + PAD + row * (CELL_H + LABEL_H + PAD)

        base = base_snap if key.endswith("_スナップ") else base_land
        params = load_params(presets[key])
        filtered = apply_filter(base, params)
        grid.paste(filtered, (x, y))

        # ラベル帯
        draw.rectangle([x, y + CELL_H, x + CELL_W, y + CELL_H + LABEL_H], fill=LABEL_BG)
        label = short_name(key)
        draw_text_centered(draw, label, font_label, x, y + CELL_H, CELL_W, LABEL_H, LABEL_FG)

    grid.save(OUTPUT_FILE, "PNG", optimize=True)
    w, h = grid.size
    print(f"Saved: {OUTPUT_FILE.name}  ({w} x {h} px)")


if __name__ == "__main__":
    main()
