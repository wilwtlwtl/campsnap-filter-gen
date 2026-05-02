"""
フィルター比較ビュー
保存済みプリセットを同じ写真に並べて表示する
"""

import streamlit as st
from PIL import Image
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.preset_builder import load_presets, preset_to_flt_params
from src.preview import apply_filter
from src.flt_io import to_flt_bytes

st.title("🔍 フィルター比較ビュー")
st.markdown(
    "写真をアップロードして、保存済みのプリセットを**横に並べて比較**できます。"
    "どのフィルターが一番好みか、一目で確認してください。"
)
st.divider()


# ── 写真アップロード ─────────────────────────────────────────────────────────

st.subheader("📸 比較したい写真をアップロード")
uploaded = st.file_uploader(
    "JPG / PNG を選択",
    type=["jpg", "jpeg", "png"],
    label_visibility="collapsed",
)

if "compare_img" not in st.session_state:
    st.session_state.compare_img = None

if uploaded:
    st.session_state.compare_img = Image.open(uploaded).convert("RGB")

if st.session_state.compare_img is None:
    st.info("写真をアップロードすると、各プリセットの仕上がりを並べて表示します。")
    st.stop()

st.image(st.session_state.compare_img, caption="比較用の写真", use_container_width=True)
st.divider()


# ── プリセット選択 ────────────────────────────────────────────────────────────

presets = load_presets()

if not presets:
    st.warning(
        "保存済みプリセットがありません。"
        "左メニューの「プリセットをつくる」ページでプリセットを作成してください。"
    )
    st.stop()

st.subheader("🎞️ 比較するプリセットを選択")
st.caption("複数選択できます。選んだプリセットをすべて並べて表示します。")

all_names = list(presets.keys())
selected_names = st.multiselect(
    "プリセットを選択",
    all_names,
    default=all_names[:min(3, len(all_names))],
    label_visibility="collapsed",
)

if not selected_names:
    st.info("比較するプリセットを1つ以上選択してください。")
    st.stop()

st.divider()


# ── 比較グリッド表示 ──────────────────────────────────────────────────────────

st.subheader("👁️ 比較結果")

img = st.session_state.compare_img

# 元画像を含めて表示
all_display = [("📷 元の写真（フィルターなし）", img, None)] + [
    (name, apply_filter(img, preset_to_flt_params(name)), name)
    for name in selected_names
    if preset_to_flt_params(name) is not None
]

# 1行あたりの列数（最大3列）
cols_per_row = min(3, len(all_display))
rows = [all_display[i:i+cols_per_row] for i in range(0, len(all_display), cols_per_row)]

for row in rows:
    cols = st.columns(len(row))
    for col, (label, filtered_img, preset_name) in zip(cols, row):
        with col:
            st.image(filtered_img, use_container_width=True)
            st.caption(label)
            if preset_name:
                meta = presets[preset_name].get("meta", {})
                if meta.get("n_images"):
                    st.caption(f"参考画像 {meta['n_images']}枚")
                p = preset_to_flt_params(preset_name)
                flt_bytes = to_flt_bytes(p)
                st.download_button(
                    label="📥 ダウンロード",
                    data=flt_bytes,
                    file_name=f"{preset_name.replace(' ','_')}.flt",
                    mime="application/octet-stream",
                    use_container_width=True,
                    key=f"dl_{preset_name}",
                )
