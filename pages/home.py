"""
Camp Snap V105 Filter Generator - TOPページ
モバイル優先のレイアウト：カテゴリピル + 2列ギャラリー
"""

import streamlit as st
from PIL import Image
import sys, os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.analyzer import FltParams
from src.preview import apply_filter
from src.preset_builder import load_presets, preset_to_flt_params


# ── 定数 ────────────────────────────────────────────────────────────────
_SNAP_IMG_PATH = Path(__file__).parent.parent / "sample_snap.jpg"
_THUMB_SIZE = (300, 200)

# カテゴリ定義（順序がそのまま表示順、メーカー別＋実機）
_CATEGORIES = [
    ("all",        "すべて"),
    ("kodak",      "Kodak"),
    ("fujifilm",   "Fujifilm"),
    ("cinestill",  "Cinestill"),
    ("agfa",       "Agfa"),
    ("ilford",     "Ilford"),
    ("lomography", "Lomography"),
    ("camera",     "実機"),
]


# ── キャッシュ ─────────────────────────────────────────────────────────
def _img_mtime_key() -> str:
    return str(_SNAP_IMG_PATH.stat().st_mtime) if _SNAP_IMG_PATH.exists() else "0"


@st.cache_data
def _build_preset_previews(presets_json: str, _img_key: str) -> dict:
    import json
    presets = json.loads(presets_json)
    if not _SNAP_IMG_PATH.exists():
        return {}
    base_img = Image.open(_SNAP_IMG_PATH).convert("RGB").resize(_THUMB_SIZE, Image.LANCZOS)
    result = {}
    for name, data in presets.items():
        p_data = data["params"]
        p = FltParams(
            brightness=p_data["Brightness"], contrast=p_data["Contrast"],
            saturation=p_data["Saturation"], hue=p_data.get("Hue", 0),
            gamma_r=p_data["GammaR"], gamma_g=p_data["GammaG"], gamma_b=p_data["GammaB"],
        )
        result[name] = apply_filter(base_img, p)
    return result


# ── スタイル ───────────────────────────────────────────────────────────
st.markdown("""
<style>
/* モバイル幅で本文を圧迫しないよう余白圧縮 */
.block-container {
    padding-top: 1.2rem !important;
    padding-bottom: 1.5rem !important;
    max-width: 720px;
}

/* ヘッダー */
.hero-title {
    font-size: 1.35rem;
    font-weight: 700;
    line-height: 1.2;
    margin: 0.4rem 0 0.2rem;
}
.hero-sub {
    font-size: 0.85rem;
    color: #666;
    margin: 0 0 1rem;
}

/* カテゴリピル: st.radio を横スクロール対応 */
div[role="radiogroup"] {
    flex-wrap: nowrap !important;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: thin;
    padding-bottom: 0.4rem;
    gap: 0.4rem !important;
}
div[role="radiogroup"]::-webkit-scrollbar { height: 4px; }
div[role="radiogroup"]::-webkit-scrollbar-thumb { background: #ccc; border-radius: 2px; }
div[role="radiogroup"] > label {
    flex-shrink: 0 !important;
    padding: 0.4rem 0.9rem !important;
    border-radius: 999px !important;
    border: 1px solid #ddd !important;
    background: #fff !important;
    font-size: 0.85rem !important;
    cursor: pointer;
    white-space: nowrap;
}
div[role="radiogroup"] > label:has(input:checked) {
    background: #1f6feb !important;
    color: #fff !important;
    border-color: #1f6feb !important;
}
div[role="radiogroup"] > label > div:first-child { display: none !important; }

/* プリセットカード */
.preset-card-name {
    font-size: 0.85rem;
    font-weight: 600;
    margin: 0.3rem 0 0.1rem;
    line-height: 1.2;
}
.preset-card-desc {
    font-size: 0.72rem;
    color: #666;
    line-height: 1.3;
    margin: 0 0 0.4rem;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

/* サブ動線 */
.sub-section {
    background: #f7f7f7;
    border-radius: 10px;
    padding: 0.9rem;
    margin-top: 1.5rem;
}
.sub-section-title {
    font-size: 0.85rem;
    font-weight: 600;
    color: #555;
    margin: 0 0 0.6rem;
}

/* フッター */
.app-footer {
    text-align: center;
    font-size: 0.7rem;
    color: #999;
    margin-top: 1.8rem;
    padding-top: 0.8rem;
    border-top: 1px solid #eee;
}
.app-footer a { color: #999; text-decoration: none; margin: 0 0.4rem; }
</style>
""", unsafe_allow_html=True)


# ── ヒーロー ───────────────────────────────────────────────────────────
st.markdown(
    '<div class="hero-title">📷 プリセットを選んで</div>'
    '<div class="hero-sub">タップして自分好みに調整 → V105用 .flt ファイルをダウンロード</div>',
    unsafe_allow_html=True,
)


# ── プリセット読み込み ───────────────────────────────────────────────────
presets = load_presets()

if not presets:
    st.warning("プリセットがありません。")
    st.stop()


# ── カテゴリピル ───────────────────────────────────────────────────────
def _count_in_cat(cat_key: str) -> int:
    if cat_key == "all":
        return len(presets)
    return sum(1 for d in presets.values() if (d.get("meta") or {}).get("category") == cat_key)


# 件数付きラベル（ピル）
pill_labels = [f"{label} ({_count_in_cat(key)})" for key, label in _CATEGORIES]
pill_key_by_label = {f"{label} ({_count_in_cat(key)})": key for key, label in _CATEGORIES}

selected_label = st.radio(
    "カテゴリ",
    pill_labels,
    horizontal=True,
    label_visibility="collapsed",
)
selected_cat = pill_key_by_label[selected_label]


# ── ギャラリー（2列グリッド） ──────────────────────────────────────────
import json as _json
previews = _build_preset_previews(_json.dumps(presets, ensure_ascii=False), _img_mtime_key())

if selected_cat == "all":
    filtered_names = list(presets.keys())
else:
    filtered_names = [
        n for n, d in presets.items()
        if (d.get("meta") or {}).get("category") == selected_cat
    ]

if not filtered_names:
    st.info("該当するプリセットがありません。")
else:
    GALLERY_COLS = 2
    for row_start in range(0, len(filtered_names), GALLERY_COLS):
        row = filtered_names[row_start:row_start + GALLERY_COLS]
        cols = st.columns(GALLERY_COLS)
        for col, name in zip(cols, row):
            with col:
                if name in previews:
                    st.image(previews[name], use_container_width=True)
                meta = presets[name].get("meta", {})
                desc = meta.get("description", "")
                # 説明から「/」以降を1行説明として使う
                short_desc = desc.split("/", 1)[-1].strip() if "/" in desc else desc
                st.markdown(
                    f'<div class="preset-card-name">{name}</div>'
                    f'<div class="preset-card-desc">{short_desc}</div>',
                    unsafe_allow_html=True,
                )
                if st.button("選択 →", key=f"sel_{name}", use_container_width=True, type="primary"):
                    p = preset_to_flt_params(name)
                    if p:
                        st.session_state.params = p
                        st.session_state.analyzed = True
                        st.session_state.warnings = []
                        st.session_state.current_preset_name = name
                        # editor 側で base を再構築させるためフラグを更新
                        st.session_state.base_params = None
                        st.session_state.warmth_offset = 0
                        st.session_state.strength = 1.0
                        st.switch_page("pages/editor.py")


# ── サブ動線 ───────────────────────────────────────────────────────────
st.markdown('<div class="sub-section">', unsafe_allow_html=True)
st.markdown('<div class="sub-section-title">別の作り方</div>', unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1:
    st.page_link("pages/preset_builder.py", label="🛠️ ゼロから作る", use_container_width=True)
with c2:
    st.page_link("pages/filter_gen.py", label="📸 写真から作る", use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)


# ── フッター ───────────────────────────────────────────────────────────
st.markdown(
    '<div class="app-footer">'
    '<a href="https://campsnapphoto.com/" target="_blank">Camp Snap V105</a> · '
    '<a href="https://github.com/wilwtlwtl/campsnap-filter-gen" target="_blank">GitHub</a>'
    '</div>',
    unsafe_allow_html=True,
)
