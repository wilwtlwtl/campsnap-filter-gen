"""
Camp Snap V105 Filter Generator - 編集画面
ホーム/写真から作る から遷移してくる前提。
session_state.params に編集対象のFltParamsが入っている。
"""

import streamlit as st
from PIL import Image
import sys, os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.analyzer import FltParams, DEFAULT_SAFETY
from src.preview import apply_filter, simulate_v105
from src.flt_io import to_flt_bytes
from src.histogram import histogram_dataframe


_SNAP_IMG_PATH = Path(__file__).parent.parent / "sample_snap.jpg"


# ── プリセット未指定なら戻す ──────────────────────────────────────────────
if "params" not in st.session_state or st.session_state.params is None:
    st.warning("プリセットが選択されていません。ホームに戻って選択してください。")
    st.page_link("pages/home.py", label="← ホームに戻る")
    st.stop()


# ── セッション初期化 ────────────────────────────────────────────────────
for key, default in [
    ("strength",            1.0),
    ("preview_img",         None),
    ("flt_name",            "my_filter"),
    ("warmth_offset",       0),   # 暖色/寒色スライダーの相対値(-50〜+50)
    ("base_params",         None),
    ("current_preset_name", "編集中フィルター"),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# 編集画面に入った時点の params を base として固定（暖色/寒色の基準）
# preset が変わったらリセット（current_preset_name の変化を検知）
if st.session_state.base_params is None or \
   st.session_state.get("_base_for_preset") != st.session_state.current_preset_name:
    st.session_state.base_params = st.session_state.params
    st.session_state._base_for_preset = st.session_state.current_preset_name
    st.session_state.warmth_offset = 0


# ── スタイル ───────────────────────────────────────────────────────────
st.markdown("""
<style>
.block-container {
    padding-top: 0.8rem !important;
    padding-bottom: 1.5rem !important;
    max-width: 720px;
}
.editor-title {
    text-align: center;
    font-weight: 700;
    font-size: 1.05rem;
    padding-top: 0.4rem;
    line-height: 1.2;
}
.editor-sublabel {
    font-size: 0.7rem;
    color: #888;
    text-align: center;
    margin-top: -0.4rem;
    margin-bottom: 0.6rem;
}
/* スライダー: 値を右寄せで大きめに */
div[data-testid="stSlider"] label {
    font-size: 0.92rem;
    font-weight: 600;
}
/* ヘッダーボタン（戻る・リセット）を小さく */
.header-btn button {
    padding: 0.25rem 0.5rem !important;
    font-size: 0.85rem !important;
}
/* 主要なダウンロードボタン */
div[data-testid="stDownloadButton"] button[kind="primary"] {
    background: #111 !important;
    color: #fff !important;
    font-weight: 700;
    border-radius: 10px;
    padding: 0.7rem 1rem !important;
}
</style>
""", unsafe_allow_html=True)


# ── ヘッダー（戻る・名前・リセット） ──────────────────────────────────
col_back, col_title, col_reset = st.columns([1, 3, 1])
with col_back:
    st.markdown('<div class="header-btn">', unsafe_allow_html=True)
    if st.button("← 戻る", key="back_btn", use_container_width=True):
        st.session_state.base_params = None
        st.session_state.warmth_offset = 0
        st.switch_page("pages/home.py")
    st.markdown('</div>', unsafe_allow_html=True)
with col_title:
    st.markdown(
        f'<div class="editor-title">{st.session_state.current_preset_name}</div>',
        unsafe_allow_html=True,
    )
with col_reset:
    st.markdown('<div class="header-btn">', unsafe_allow_html=True)
    if st.button("↻ リセット", key="reset_btn", use_container_width=True,
                 help="プリセットの初期値に戻す"):
        st.session_state.params = st.session_state.base_params
        st.session_state.strength = 1.0
        st.session_state.warmth_offset = 0
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)


# ── プレビュー対象（自分の写真があればそちらを優先） ──────────────────
preview_src: Image.Image | None = None
if st.session_state.get("preview_img") is not None:
    preview_src = st.session_state.preview_img
elif _SNAP_IMG_PATH.exists():
    preview_src = Image.open(_SNAP_IMG_PATH).convert("RGB")


# ── 現在のパラメータでフィルター画像を作成 ────────────────────────────
base = st.session_state.base_params
p_current = st.session_state.params

# 強度ブレンド適用
p_blended = p_current.blend(st.session_state.strength)


# ── Before/After 横並び ──────────────────────────────────────────────
if preview_src is not None:
    # 表示用にリサイズ
    PREVIEW_SIZE = (400, 280)
    src_small = preview_src.resize(PREVIEW_SIZE, Image.LANCZOS)
    after_img = apply_filter(src_small, p_blended)

    c1, c2 = st.columns(2)
    with c1:
        st.caption("Before")
        st.image(src_small, use_container_width=True)
    with c2:
        st.caption("After")
        st.image(after_img, use_container_width=True)
else:
    st.info("サンプル画像が見つかりません。")


# ── 自分の写真でプレビュー（リンク風） ────────────────────────────────
with st.expander("📷 サンプル画像を自分の写真に変更"):
    upl = st.file_uploader(
        "JPG / PNG をアップロード",
        type=["jpg", "jpeg", "png"],
        key="editor_preview_upload",
        label_visibility="collapsed",
    )
    if upl:
        st.session_state.preview_img = Image.open(upl).convert("RGB")
        st.rerun()
    if st.session_state.preview_img is not None:
        if st.button("✕ 自分の写真を外す", key="clear_preview_editor"):
            st.session_state.preview_img = None
            st.rerun()


st.markdown("")  # 余白


# ── メインスライダー4本 ──────────────────────────────────────────────
# 1. 強度
strength_pct = st.slider(
    "🎚️ 強度",
    min_value=0, max_value=100,
    value=int(st.session_state.strength * 100),
    step=1, format="%d%%",
    help="0% = 効果なし、100% = フル適用",
)
st.session_state.strength = strength_pct / 100

# 2. 彩度
saturation = st.slider(
    "🌈 彩度",
    min_value=float(DEFAULT_SAFETY.saturation_min),
    max_value=float(DEFAULT_SAFETY.saturation_max),
    value=float(p_current.saturation),
    step=0.01, format="%.2f",
    help="大きくすると色が鮮やかに",
)

# 3. コントラスト
contrast = st.slider(
    "⚡ コントラスト",
    min_value=float(DEFAULT_SAFETY.contrast_min),
    max_value=float(DEFAULT_SAFETY.contrast_max),
    value=float(p_current.contrast),
    step=0.01, format="%.2f",
    help="明暗のメリハリを調整",
)

# 4. 暖色/寒色（GammaR と GammaB を逆相連動）
warmth = st.slider(
    "🔴🔵 暖色 / 寒色",
    min_value=-50, max_value=50,
    value=int(st.session_state.warmth_offset),
    step=1, format="%d",
    help="左：寒色寄り（青）、右：暖色寄り（赤）",
)
st.session_state.warmth_offset = warmth

# warmth から GammaR / GammaB を計算（base からの相対オフセット）
# warmth +（暖色）→ gamma_r 下げる（赤を強調）、gamma_b 上げる（青を抑制）
factor = warmth / 200.0  # 最大 ±0.25 倍
new_gamma_r = base.gamma_r * (1 - factor)
new_gamma_b = base.gamma_b * (1 + factor)


# ── 詳細パラメータ（折りたたみ） ──────────────────────────────────────
with st.expander("詳細パラメータ"):
    st.caption("「強度」「彩度」「コントラスト」「暖色/寒色」で足りないときに使います。")
    brightness = st.slider(
        "☀️ 明るさ",
        min_value=float(DEFAULT_SAFETY.brightness_min),
        max_value=float(DEFAULT_SAFETY.brightness_max),
        value=float(p_current.brightness),
        step=0.01, format="%.2f",
    )
    gamma_g = st.slider(
        "🟢 緑のガンマ (GammaG)",
        min_value=float(DEFAULT_SAFETY.gamma_min),
        max_value=float(DEFAULT_SAFETY.gamma_max),
        value=float(p_current.gamma_g),
        step=0.01, format="%.2f",
    )
    st.caption("※ 赤・青のガンマは「暖色/寒色」スライダーで調整しています。")
    st.caption(f"  現在値 → GammaR: {new_gamma_r:.3f}　GammaB: {new_gamma_b:.3f}")


# ── パラメータを最新化 ───────────────────────────────────────────────
new_params = FltParams(
    brightness=brightness, contrast=contrast,
    saturation=saturation, hue=0,
    gamma_r=new_gamma_r, gamma_g=gamma_g, gamma_b=new_gamma_b,
)
st.session_state.params = new_params
p_blended = new_params.blend(st.session_state.strength)


# ── ヒストグラム＆実機シミュレーション（任意） ────────────────────────
with st.expander("📊 詳しく見る（ヒストグラム / V105実機シミュレーション）"):
    if preview_src is None:
        st.caption("プレビュー画像がありません。")
    else:
        tab1, tab2 = st.tabs(["ヒストグラム", "V105実機シミュレーション"])
        with tab1:
            tab_l, tab_r, tab_g, tab_b = st.tabs(["明るさ全体", "赤(R)", "緑(G)", "青(B)"])
            filtered_img = apply_filter(preview_src, p_blended)
            for tab, channel in zip([tab_l, tab_r, tab_g, tab_b], ["輝度", "R", "G", "B"]):
                with tab:
                    df = histogram_dataframe(preview_src, filtered_img, channel=channel)
                    colors = {
                        "輝度": ["#aaaaaa", "#444444"],
                        "R":    ["#ffaaaa", "#cc0000"],
                        "G":    ["#aaffaa", "#009900"],
                        "B":    ["#aaaaff", "#0000cc"],
                    }[channel]
                    st.line_chart(df, color=colors)
        with tab2:
            with st.spinner(""):
                sim_img = simulate_v105(preview_src, p_blended)
            st.image(sim_img, use_container_width=True)
            st.caption("V105 の粒子感・低解像感・周辺光量落ちを再現したシミュレーション")


# ── 下部固定エリア：ダウンロード ──────────────────────────────────────
st.divider()

flt_name = st.text_input(
    "ファイル名",
    value=st.session_state.get("flt_name", "my_filter"),
    key="flt_name_input_editor",
    help="半角英数字推奨。SDカードに保存される名前です。",
)
final_name = flt_name.strip() or "my_filter"

flt_bytes = to_flt_bytes(p_blended)

st.download_button(
    label=f"📥 .flt をダウンロード（強度 {strength_pct}%）",
    data=flt_bytes,
    file_name=f"{final_name}.flt",
    mime="application/octet-stream",
    use_container_width=True,
    type="primary",
)

with st.expander("📖 SDカードへの入れ方"):
    st.markdown("""
1. SDカードをパソコンに挿す
2. ダウンロードした `.flt` ファイルをSDカードの**ルート直下**にコピー
3. SDカードをV105に戻して電源を入れる

起動時に画面に **CUS** と表示されれば成功です。
""")
