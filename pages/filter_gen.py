"""
Camp Snap V105 フィルタージェネレーター – メインUI
"""

import streamlit as st
from PIL import Image
import numpy as np
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.analyzer import ImageAnalyzer, FltParams, SafetyLimits, DEFAULT_SAFETY
from src.hist_analyzer import HistogramAnalyzer
from src.flt_io import to_flt_bytes, load_flt
from src.preview import apply_filter, simulate_v105
from src.preset_builder import load_presets, preset_to_flt_params


# ── スタイル ────────────────────────────────────────────────────────────────

st.markdown("""
<style>
.big-upload-label {
    font-size: 1.15rem;
    font-weight: 600;
    margin-bottom: 0.25rem;
}
.style-card {
    background: #f7f7f7;
    border-radius: 12px;
    padding: 1.2rem 1.5rem;
    margin-bottom: 1rem;
}
.meter-row {
    display: flex;
    align-items: center;
    gap: 0.7rem;
    margin-bottom: 0.45rem;
    font-size: 0.95rem;
}
.meter-label { width: 130px; flex-shrink: 0; }
.meter-bar-wrap {
    flex: 1;
    background: #e0e0e0;
    border-radius: 6px;
    height: 10px;
    overflow: hidden;
}
.meter-bar {
    height: 100%;
    border-radius: 6px;
    background: #4a90d9;
}
.meter-note { width: 90px; flex-shrink: 0; color: #666; font-size: 0.85rem; }
.tag {
    display: inline-block;
    background: #ececec;
    border-radius: 20px;
    padding: 3px 12px;
    font-size: 0.88rem;
    margin-right: 6px;
}
</style>
""", unsafe_allow_html=True)


# ── ユーティリティ ──────────────────────────────────────────────────────────

def _to_pct(value: float, lo: float, hi: float) -> int:
    """value を lo〜hi の範囲で 0〜100% に変換"""
    return int(max(0, min(100, (value - lo) / (hi - lo) * 100)))


def _meter(label: str, value: float, lo: float, hi: float,
           lo_word: str, hi_word: str, color: str = "#4a90d9"):
    pct = _to_pct(value, lo, hi)
    mid = (lo + hi) / 2
    note = hi_word if value > mid else lo_word
    st.markdown(f"""
<div class="meter-row">
  <span class="meter-label">{label}</span>
  <div class="meter-bar-wrap">
    <div class="meter-bar" style="width:{pct}%;background:{color};"></div>
  </div>
  <span class="meter-note">{note}</span>
</div>""", unsafe_allow_html=True)


def _detect_style_tags(p: FltParams) -> list[tuple[str, str]]:
    """パラメータから直感的なスタイルタグを推定する"""
    tags = []
    warmth = (1.0 / p.gamma_r) - (1.0 / p.gamma_b)   # 正 = 暖色, 負 = 寒色

    if p.brightness > 1.15:
        tags.append(("☀️", "明るめ"))
    elif p.brightness < 0.88:
        tags.append(("🌙", "暗め・シネマティック"))

    if p.contrast < 0.85:
        tags.append(("☁️", "ふんわり・霞がかった"))
    elif p.contrast > 1.15:
        tags.append(("⚡", "くっきりシャープ"))

    if p.saturation < 0.80:
        tags.append(("🩶", "色を抑えたレトロ調"))
    elif p.saturation > 1.20:
        tags.append(("🌈", "鮮やか・ポップ"))

    if warmth > 0.15:
        tags.append(("🔴", "暖色・フィルム風"))
    elif warmth < -0.15:
        tags.append(("🔵", "寒色・クール"))

    if not tags:
        tags.append(("✨", "自然な仕上がり"))
    return tags


def _run_analysis(target_img: Image.Image, base_img=None) -> tuple[FltParams, list[str]]:
    if base_img is not None:
        analyzer = HistogramAnalyzer()
        params, diag = analyzer.analyze(base_img, target_img, safety=DEFAULT_SAFETY)
        return params, diag.warnings
    else:
        analyzer = ImageAnalyzer()
        return analyzer.analyze_from_target_only(target_img, safety=DEFAULT_SAFETY)


# ── セッション初期化 ────────────────────────────────────────────────────────

for key, default in [
    ("params", FltParams()),
    ("target_img", None),
    ("base_img", None),
    ("analyzed", False),
    ("warnings", []),
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ════════════════════════════════════════════════════════════════════════════
# ヘッダー
# ════════════════════════════════════════════════════════════════════════════

st.title("📷 Camp Snap V105\nフィルタージェネレーター")
st.markdown(
    "「**こんな色で撮りたい！**」という写真を1枚アップロードするだけで、"
    "V105用のフィルターファイルを自動でつくります。"
)
st.divider()


# ════════════════════════════════════════════════════════════════════════════
# プリセット選択（保存済みがある場合のみ表示）
# ════════════════════════════════════════════════════════════════════════════

presets = load_presets()
if presets:
    st.subheader("🎞️ 保存済みプリセットから選ぶ")
    st.caption("「プリセットをつくる」ページで作成・保存したプリセットをすぐに適用できます。")

    preset_names = list(presets.keys())
    selected = st.selectbox(
        "プリセットを選択",
        ["（選択しない）"] + preset_names,
        label_visibility="collapsed",
    )

    if selected != "（選択しない）":
        meta = presets[selected].get("meta", {})
        col_a, col_b = st.columns([2, 1])
        with col_a:
            if meta.get("n_images"):
                st.caption(f"参考画像 {meta['n_images']}枚から生成　安定性スコア: {meta.get('stability', '–')}点")
        with col_b:
            if st.button("✅ このプリセットを使う", use_container_width=True, type="primary"):
                p = preset_to_flt_params(selected)
                if p:
                    st.session_state.params   = p
                    st.session_state.analyzed = True
                    st.session_state.warnings = []
                    st.rerun()

    st.caption("新しいプリセットを作るには左メニューの「プリセットをつくる」ページへ。")
    st.divider()


# ════════════════════════════════════════════════════════════════════════════
# STEP 1 – 写真をアップロード
# ════════════════════════════════════════════════════════════════════════════

st.subheader("📸 STEP 1 ｜ 理想の写真をアップロード")
st.caption(
    "フィルム写真・他のカメラで撮った写真・ネットで見つけた好きな写真…なんでも大丈夫です。"
    "その色の雰囲気をそのままV105のフィルターに変換します。"
)

uploaded = st.file_uploader(
    "JPG / PNG をドロップ、またはクリックして選択",
    type=["jpg", "jpeg", "png"],
    key="upload_target",
    label_visibility="collapsed",
)

if uploaded:
    target_img = Image.open(uploaded).convert("RGB")
    st.session_state.target_img = target_img
    st.session_state.analyzed = False   # 再アップ時はリセット
    st.image(target_img, use_container_width=True)

with st.expander("📁 V105で撮った写真もあれば、より正確に解析できます（任意）", expanded=False):
    st.caption(
        "「精密モード」：V105で撮った素の写真と理想の写真を比べることで、"
        "カメラのクセを差し引いたより正確なフィルターを生成します。なくても動作します。"
    )
    base_uploaded = st.file_uploader(
        "V105で撮った写真（任意）",
        type=["jpg", "jpeg", "png"],
        key="upload_base",
    )
    if base_uploaded:
        st.session_state.base_img = Image.open(base_uploaded).convert("RGB")
        st.image(st.session_state.base_img, caption="V105の写真（元画像）", use_container_width=True)
        st.session_state.analyzed = False

st.divider()


# ════════════════════════════════════════════════════════════════════════════
# STEP 2 – フィルターを生成
# ════════════════════════════════════════════════════════════════════════════

st.subheader("✨ STEP 2 ｜ フィルターを自動生成")

generate_btn = st.button(
    "🎨 この写真の色をフィルターにする",
    type="primary",
    use_container_width=True,
    disabled=(st.session_state.target_img is None),
)

if generate_btn:
    with st.spinner("色の特徴を読み取っています…"):
        params, warnings = _run_analysis(
            st.session_state.target_img,
            st.session_state.base_img,
        )
    st.session_state.params   = params
    st.session_state.warnings = warnings
    st.session_state.analyzed = True

if st.session_state.target_img is None:
    st.info("まず上に写真をアップロードしてください。")

# ── 結果カード ──────────────────────────────────────────────────────────────

if st.session_state.analyzed:
    p = st.session_state.params

    st.success("✅ フィルターの生成が完了しました！")

    if st.session_state.warnings:
        with st.expander("ℹ️ 一部の設定を自動的に安全な範囲に調整しました", expanded=False):
            st.caption(
                "解析結果がV105のカメラ性能の限界を超えていたため、"
                "実際に使える範囲に自動で丸めました。"
                "「もっと大胆に」したい場合は、下の「自分で調整する」から数値を変更できます。"
            )
            for w in st.session_state.warnings:
                st.warning(w)

    # スタイルタグ
    tags = _detect_style_tags(p)
    tag_html = "".join(f'<span class="tag">{icon} {word}</span>' for icon, word in tags)
    st.markdown(
        f'<div style="margin:0.5rem 0 1rem;">'
        f'<span style="font-size:0.85rem;color:#888;">検出されたスタイル ▶ </span>'
        f'{tag_html}</div>',
        unsafe_allow_html=True,
    )

    # メーター表示
    st.markdown('<div class="style-card">', unsafe_allow_html=True)
    _meter("☀️ 明るさ",       p.brightness, 0.5, 1.6, "暗め",    "明るめ",   "#f5a623")
    _meter("⚡ くっきりさ",   p.contrast,   0.6, 1.4, "ふんわり", "くっきり", "#7ed321")
    _meter("🌈 色の鮮やかさ", p.saturation, 0.5, 1.5, "薄い・レトロ", "鮮やか", "#bd10e0")

    warmth_raw = (1.0 / max(p.gamma_r, 0.1)) - (1.0 / max(p.gamma_b, 0.1))
    warmth_val = 1.0 + warmth_raw * 0.4   # 1.0 を中心に正規化
    _meter("🔴 暖かみ",       warmth_val,   0.5, 1.5, "寒色・クール", "暖色・温かみ", "#e05050")
    st.markdown('</div>', unsafe_allow_html=True)

    st.divider()


# ════════════════════════════════════════════════════════════════════════════
# STEP 3 – プレビューとダウンロード
# ════════════════════════════════════════════════════════════════════════════

if st.session_state.analyzed:
    p = st.session_state.params

    st.subheader("👁️ STEP 3 ｜ 仕上がりをプレビュー")
    st.caption(
        "左が元の写真、右がフィルターを当てたときの予想です。"
        "V105シミュレーションをONにすると、実機特有のノイズや周辺の暗さなども再現します。"
    )

    show_sim = st.toggle("📷 V105の実機に近い見え方でシミュレートする", value=False)
    preview_src = st.session_state.base_img or st.session_state.target_img

    if show_sim:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.caption("元の写真")
            st.image(preview_src, use_container_width=True)
        with c2:
            st.caption("フィルター適用後")
            st.image(apply_filter(preview_src, p), use_container_width=True)
        with c3:
            st.caption("V105実機シミュレーション")
            with st.spinner(""):
                st.image(simulate_v105(preview_src, p), use_container_width=True)
        st.caption(
            "シミュレーションでは、V105特有の粒状感・低解像度感・"
            "明暗の限界・周辺光量落ち・色温度のクセを再現しています。"
            "実際の写りとは異なる場合があります。"
        )
    else:
        c1, c2 = st.columns(2)
        with c1:
            st.caption("元の写真")
            st.image(preview_src, use_container_width=True)
        with c2:
            st.caption("フィルター適用後")
            st.image(apply_filter(preview_src, p), use_container_width=True)

    st.divider()

    # ── ダウンロード ─────────────────────────────────────────────────────────

    st.subheader("💾 STEP 4 ｜ フィルターをダウンロード")

    flt_name = st.text_input(
        "フィルターの名前（半角英数字推奨）",
        value="my_filter",
        help="SDカード上のファイル名になります。日本語・スペースは避けてください。",
    )

    flt_bytes = to_flt_bytes(p)

    st.download_button(
        label="📥 フィルターファイル (.flt) をダウンロード",
        data=flt_bytes,
        file_name=f"{flt_name}.flt",
        mime="text/plain",
        use_container_width=True,
        type="primary",
    )

    with st.expander("📖 SDカードへの入れ方", expanded=False):
        st.markdown("""
1. SDカードをパソコンに挿す
2. `FILTERS` というフォルダを開く（なければ作成）
3. ダウンロードした `.flt` ファイルをそのフォルダにコピーする
4. SDカードをV105に戻して電源を入れる

**起動時に画面に `CUS` と表示されれば読み込み成功です。**
フィルター選択でこのフィルターを選んで撮影してみてください。
""")

    st.divider()

    # ════════════════════════════════════════════════════════════════════════
    # 上級者向け調整パネル（折りたたみ）
    # ════════════════════════════════════════════════════════════════════════

    with st.expander("🔧 自分で細かく調整したい方へ", expanded=False):
        st.caption(
            "自動生成された数値をここで自由に変えられます。"
            "スライダーを動かすと、上のプレビューにも即座に反映されます。"
        )

        safety = DEFAULT_SAFETY
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**全体の雰囲気**")
            brightness = st.slider(
                "☀️ 明るさ",
                safety.brightness_min, safety.brightness_max, float(p.brightness), 0.01,
                help="大きくすると全体が明るく、小さくすると暗くなります。基準値は 1.0。",
            )
            contrast = st.slider(
                "⚡ くっきりさ（コントラスト）",
                safety.contrast_min, safety.contrast_max, float(p.contrast), 0.01,
                help="大きくすると明暗のメリハリが増してシャープに。小さくするとふんわり柔らかくなります。",
            )
            saturation = st.slider(
                "🌈 色の鮮やかさ（彩度）",
                safety.saturation_min, safety.saturation_max, float(p.saturation), 0.01,
                help="大きくすると色が濃く鮮やかに。小さくすると色が薄くなり、0に近いとほぼモノクロになります。",
            )

        with col2:
            st.markdown("**色のトーン調整**")
            st.caption(
                "赤・緑・青それぞれの「トーン」を個別に動かせます。"
                "数値が小さいほどそのチャンネルが明るく強調されます（1.0 ＝ 変化なし）。"
            )
            gamma_r = st.slider(
                "🔴 赤みの強さ（暖かさ）",
                safety.gamma_min, safety.gamma_max, float(p.gamma_r), 0.01,
                help="小さくすると赤みが増して温かい雰囲気に。大きくすると赤みが抑えられます。",
            )
            gamma_g = st.slider(
                "🟢 緑みの強さ（自然さ）",
                safety.gamma_min, safety.gamma_max, float(p.gamma_g), 0.01,
                help="小さくすると緑が強調されます。肌色や植物の見え方に影響します。",
            )
            gamma_b = st.slider(
                "🔵 青みの強さ（涼しさ）",
                safety.gamma_min, safety.gamma_max, float(p.gamma_b), 0.01,
                help="小さくすると青みが増してクールな印象に。大きくすると青みが抑えられます。",
            )

        adjusted = FltParams(
            brightness=brightness, contrast=contrast, saturation=saturation,
            hue=0, gamma_r=gamma_r, gamma_g=gamma_g, gamma_b=gamma_b,
        )

        # 調整後に適用
        if adjusted.to_dict() != p.to_dict():
            st.session_state.params = adjusted
            st.rerun()

        st.markdown("**生成されるファイルの中身（確認用）**")
        st.code(to_flt_bytes(p).decode(), language="ini")


# ════════════════════════════════════════════════════════════════════════════
# サイドバー：作成済みフィルターの読み込み
# ════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.header("📂 以前作ったフィルターを読み込む")
    st.caption("このツールで作ったフィルターファイル(.flt)を読み込んで、数値を調整し直せます。")
    flt_upload = st.file_uploader("フィルターファイル (.flt) を選択", type=["flt"])
    if flt_upload is not None:
        try:
            st.session_state.params  = load_flt(flt_upload.read())
            st.session_state.analyzed = True
            st.success("読み込みました。プレビューを確認してください。")
        except Exception as e:
            st.error(f"読み込みエラー: {e}")

    st.divider()
    st.caption(
        "**このアプリについて**\n\n"
        "Camp Snap V105用のカスタムフィルター(.flt)を\n"
        "写真1枚から自動生成するツールです。\n\n"
        "生成したフィルターはSDカードの `FILTERS/` フォルダに入れることで使用できます。"
    )
