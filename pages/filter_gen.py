"""
Camp Snap V105 Filter Generator - 写真から作る（サブ動線）
理想の写真をアップロード → 解析 → 編集画面（editor.py）に遷移する。

旧サイドバーの「解析エンジン選択」「.flt 読み込み」「Lab解析詳細」もここに集約。
"""

import streamlit as st
from PIL import Image
import sys, os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.analyzer import ImageAnalyzer, FltParams, SafetyLimits, DEFAULT_SAFETY
from src.hist_analyzer import HistogramAnalyzer
from src.advanced_analyzer import AdvancedAnalyzer
from src.flt_io import load_flt


# ── スタイル ───────────────────────────────────────────────────────────
st.markdown("""
<style>
.block-container {
    padding-top: 0.8rem !important;
    padding-bottom: 1.5rem !important;
    max-width: 720px;
}
.fg-title {
    font-size: 1.15rem;
    font-weight: 700;
    margin: 0.3rem 0 0.2rem;
}
.fg-sub {
    font-size: 0.82rem;
    color: #666;
    margin-bottom: 1rem;
}
.step-label {
    font-size: 0.95rem;
    font-weight: 600;
    margin: 0.8rem 0 0.4rem;
}
</style>
""", unsafe_allow_html=True)


# ── ヘッダー ───────────────────────────────────────────────────────────
st.page_link("pages/home.py", label="← ホームに戻る")
st.markdown('<div class="fg-title">📸 写真からフィルターを作る</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="fg-sub">「こんな色で撮りたい！」という写真を1枚アップロードするだけで、V105用のフィルターを自動生成します。</div>',
    unsafe_allow_html=True,
)


# ── セッション初期化 ────────────────────────────────────────────────────
for key, default in [
    ("target_img",          None),
    ("base_img",            None),
    ("engine",              "高精度モード"),
    ("_upload_target_id",   None),
    ("_upload_base_id",     None),
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ── 解析エンジン選択（旧サイドバー機能） ──────────────────────────────
ENGINE_DESC = {
    "高精度モード": "Lab色空間で領域別解析。**V105で撮った写真**と**理想の写真**の2枚が必要。最も精度が高い。",
    "標準モード":   "ヒストグラム解析。**V105で撮った写真**と**理想の写真**の2枚が必要。",
    "かんたんモード": "**理想の写真1枚だけ**で動作。手軽だが精度は下がる。",
}
with st.expander("🔬 解析エンジン（クリックして変更）"):
    engine = st.radio(
        "エンジン",
        list(ENGINE_DESC.keys()),
        index=list(ENGINE_DESC.keys()).index(st.session_state.engine),
        label_visibility="collapsed",
    )
    st.session_state.engine = engine
    st.caption(ENGINE_DESC[engine])


# ── STEP 1: 理想の写真 ────────────────────────────────────────────────
st.markdown('<div class="step-label">📷 STEP 1: 理想の写真をアップロード</div>', unsafe_allow_html=True)
uploaded = st.file_uploader(
    "JPG / PNG をドロップまたはクリックして選択",
    type=["jpg", "jpeg", "png"],
    key="upload_target",
    label_visibility="collapsed",
)
if uploaded:
    file_id = (uploaded.name, uploaded.size)
    if st.session_state._upload_target_id != file_id:
        st.session_state._upload_target_id = file_id
        st.session_state.target_img = Image.open(uploaded).convert("RGB")
    st.image(st.session_state.target_img, use_container_width=True)


# ── STEP 1.5: V105で撮った写真（任意） ────────────────────────────────
with st.expander("📁 V105で撮った写真もあれば、より正確に解析できます（任意）"):
    st.caption("「V105で撮った素の写真」と「理想の写真」を比べることで、より正確なフィルターを生成します。")
    base_uploaded = st.file_uploader(
        "V105で撮った写真",
        type=["jpg", "jpeg", "png"],
        key="upload_base",
    )
    if base_uploaded:
        file_id = (base_uploaded.name, base_uploaded.size)
        if st.session_state._upload_base_id != file_id:
            st.session_state._upload_base_id = file_id
            st.session_state.base_img = Image.open(base_uploaded).convert("RGB")
        st.image(st.session_state.base_img, use_container_width=True)


# ── STEP 2: フィルター生成 ────────────────────────────────────────────
st.markdown('<div class="step-label">✨ STEP 2: フィルターを生成</div>', unsafe_allow_html=True)

generate_btn = st.button(
    "🎨 この写真の色をフィルターにする",
    type="primary",
    use_container_width=True,
    disabled=(st.session_state.target_img is None),
)

if st.session_state.target_img is None:
    st.info("まず STEP 1 で写真をアップロードしてください。")


def _run_analysis(target_img, base_img, engine: str):
    if base_img is not None:
        if engine == "高精度モード":
            analyzer = AdvancedAnalyzer()
            params, diag = analyzer.analyze(base_img, target_img, safety=DEFAULT_SAFETY)
            return params, diag.warnings
        else:
            analyzer = HistogramAnalyzer()
            params, diag = analyzer.analyze(base_img, target_img, safety=DEFAULT_SAFETY)
            return params, diag.warnings
    else:
        analyzer = ImageAnalyzer()
        params, warnings = analyzer.analyze_from_target_only(target_img, safety=DEFAULT_SAFETY)
        return params, warnings


if generate_btn:
    with st.spinner("色の特徴を読み取っています…"):
        params, warnings = _run_analysis(
            st.session_state.target_img,
            st.session_state.base_img,
            st.session_state.engine,
        )
    st.session_state.params = params
    st.session_state.warnings = warnings
    st.session_state.analyzed = True
    st.session_state.current_preset_name = "写真から生成したフィルター"
    # editor 側で base を再構築するためにフラグをリセット
    st.session_state.base_params = None
    st.session_state.warmth_offset = 0
    st.session_state.strength = 1.0
    st.success("✅ フィルター生成完了！編集画面に移動します…")
    st.switch_page("pages/editor.py")


# ── 既存 .flt ファイルの読み込み（旧サイドバー機能） ──────────────────
st.divider()
with st.expander("📂 以前作った .flt ファイルを読み込む"):
    st.caption("このツールで作成したフィルター(.flt)を読み込んで、編集画面で再調整できます。")
    flt_upload = st.file_uploader(
        "フィルターファイル(.flt)",
        type=["flt"],
        key="flt_loader",
    )
    if flt_upload is not None:
        try:
            loaded_params = load_flt(flt_upload.read())
            st.session_state.params = loaded_params
            st.session_state.analyzed = True
            st.session_state.current_preset_name = flt_upload.name.replace(".flt", "")
            st.session_state.base_params = None
            st.session_state.warmth_offset = 0
            st.session_state.strength = 1.0
            st.success("読み込みました。編集画面に移動します…")
            st.switch_page("pages/editor.py")
        except Exception as e:
            st.error(f"読み込みエラー: {e}")
