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
from src.advanced_analyzer import AdvancedAnalyzer
from src.flt_io import to_flt_bytes, load_flt
from src.preview import apply_filter, simulate_v105
from src.preset_builder import load_presets, preset_to_flt_params
from src.histogram import histogram_dataframe


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


def _run_analysis(
    target_img: Image.Image,
    base_img=None,
    engine: str = "高精度モード",
) -> tuple[FltParams, list[str], dict]:
    """
    戻り値: (params, warnings, diag_info)
    diag_info は表示用の補足情報 dict
    """
    if base_img is not None:
        if engine == "高精度モード":
            analyzer = AdvancedAnalyzer()
            params, diag = analyzer.analyze(base_img, target_img, safety=DEFAULT_SAFETY)
            diag_info = {
                "lab_base":    diag.lab_base,
                "lab_target":  diag.lab_target,
                "region_weights": diag.region_weights,
                "spline_gamma":   diag.spline_gamma,
            }
            return params, diag.warnings, diag_info
        else:
            analyzer = HistogramAnalyzer()
            params, diag = analyzer.analyze(base_img, target_img, safety=DEFAULT_SAFETY)
            return params, diag.warnings, {}
    else:
        analyzer = ImageAnalyzer()
        params, warnings = analyzer.analyze_from_target_only(target_img, safety=DEFAULT_SAFETY)
        return params, warnings, {}


# ── セッション初期化 ────────────────────────────────────────────────────────

for key, default in [
    ("params", FltParams()),
    ("target_img", None),
    ("base_img", None),
    ("analyzed", False),
    ("warnings", []),
    ("strength", 1.0),
    ("diag_info", {}),
    ("engine", "高精度モード"),
    ("flt_name", "my_filter"),
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
        params, warnings, diag_info = _run_analysis(
            st.session_state.target_img,
            st.session_state.base_img,
            st.session_state.engine,
        )
    st.session_state.params    = params
    st.session_state.warnings  = warnings
    st.session_state.diag_info = diag_info
    st.session_state.analyzed  = True

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
# STEP 3 – 調整 → プレビュー → ダウンロード
# スライダーをプレビューより前に定義することで、
# 値の変更が同フレーム内でプレビューに反映される（st.rerun()不要）
# ════════════════════════════════════════════════════════════════════════════

if st.session_state.analyzed:
    p = st.session_state.params

    st.subheader("👁️ STEP 3 ｜ 仕上がりをプレビュー")

    # ── フィルター強度スライダー ──────────────────────────────────────────────
    strength = st.slider(
        "🎚️ フィルターの効き具合",
        min_value=0, max_value=100,
        value=int(st.session_state.strength * 100),
        step=5,
        format="%d%%",
        help="0% = 変化なし、100% = フル適用。ちょうどよい強さに調整してください。",
    )
    st.session_state.strength = strength / 100

    # ── 細かく調整パネル（プレビューより前に定義）────────────────────────────
    safety = DEFAULT_SAFETY
    with st.expander("🔧 自分で細かく調整したい方へ", expanded=False):
        st.caption(
            "スライダーを動かすと下のプレビューにすぐ反映されます。"
        )
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
            st.caption("数値が小さいほどそのチャンネルが明るく強調されます（1.0 ＝ 変化なし）。")
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

    # スライダーの値で params を更新（rerun 不要・同フレームで反映）
    p = FltParams(
        brightness=brightness, contrast=contrast, saturation=saturation,
        hue=0, gamma_r=gamma_r, gamma_g=gamma_g, gamma_b=gamma_b,
    )
    st.session_state.params = p

    # 強度ブレンド適用
    p_blended = p.blend(st.session_state.strength)

    # ── プレビュー ────────────────────────────────────────────────────────────
    preview_src = st.session_state.base_img or st.session_state.target_img
    show_sim = st.toggle("📷 V105の実機に近い見え方でシミュレートする", value=False)

    if show_sim:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.caption("元の写真")
            st.image(preview_src, use_container_width=True)
        with c2:
            st.caption(f"フィルター適用後（{strength}%）")
            st.image(apply_filter(preview_src, p_blended), use_container_width=True)
        with c3:
            st.caption("V105実機シミュレーション")
            with st.spinner(""):
                st.image(simulate_v105(preview_src, p_blended), use_container_width=True)
        st.caption(
            "シミュレーションでは、V105特有の粒状感・低解像度感・"
            "明暗の限界・周辺光量落ち・色温度のクセを再現しています。"
        )
    else:
        c1, c2 = st.columns(2)
        with c1:
            st.caption("元の写真")
            st.image(preview_src, use_container_width=True)
        with c2:
            st.caption(f"フィルター適用後（{strength}%）")
            st.image(apply_filter(preview_src, p_blended), use_container_width=True)

    # ── ヒストグラム ──────────────────────────────────────────────────────────
    with st.expander("📊 色の分布グラフ（ヒストグラム）を見る", expanded=False):
        st.caption("横軸=色の明るさ（左:暗い〜右:明るい）、縦軸=そのピクセルの多さ。")
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

    st.divider()

    # ── ダウンロード ──────────────────────────────────────────────────────────
    st.subheader("💾 STEP 4 ｜ フィルターをダウンロード")

    flt_name = st.text_input(
        "フィルターの名前（半角英数字推奨）",
        key="flt_name",
        help="SDカード上のファイル名になります。日本語・スペースは避けてください。",
    )

    flt_bytes = to_flt_bytes(p_blended)
    st.code(flt_bytes.decode(), language="ini")

    st.download_button(
        label=f"📥 フィルターファイル (.flt) をダウンロード（強度 {strength}%）",
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
""")

    st.divider()


# ════════════════════════════════════════════════════════════════════════════
# サイドバー：作成済みフィルターの読み込み
# ════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.subheader("🔬 解析エンジン")
    engine = st.radio(
        "エンジン",
        ["高精度モード", "標準モード", "かんたんモード"],
        index=0,
        label_visibility="collapsed",
    )
    st.session_state.engine = engine
    ENGINE_DESC = {
        "高精度モード": (
            "**Lab色空間 ＋ 分割領域 ＋ スプライン**\n\n"
            "明暗・色味を人間の知覚に近い精度で解析。\n"
            "シャドウ/ハイライトも個別に補正。\n"
            "⚠️ 元画像と理想画像の **両方が必要**。"
        ),
        "標準モード": (
            "**ヒストグラムマッチング**\n\n"
            "色の分布を丸ごとマッチング。\n"
            "⚠️ 元画像と理想画像の **両方が必要**。"
        ),
        "かんたんモード": (
            "**統計比率**\n\n"
            "理想画像 **1枚のみ** で動作。\n"
            "精度は上2つより下がります。"
        ),
    }
    st.info(ENGINE_DESC[engine])

    # 高精度モード診断情報
    if st.session_state.diag_info and engine == "高精度モード":
        with st.expander("🔬 Lab解析の詳細", expanded=False):
            d = st.session_state.diag_info
            if "lab_base" in d and "lab_target" in d:
                b, t = d["lab_base"], d["lab_target"]
                st.caption("**Lab 統計値（Base → Target）**")
                st.markdown(f"明るさ(L*): `{b['L_mean']:.1f}` → `{t['L_mean']:.1f}`")
                st.markdown(f"コントラスト(L* std): `{b['L_std']:.1f}` → `{t['L_std']:.1f}`")
                st.markdown(f"色の鮮やかさ(Chroma): `{b['chroma']:.1f}` → `{t['chroma']:.1f}`")
                delta_b = t['b_mean'] - b['b_mean']
                delta_a = t['a_mean'] - b['a_mean']
                tone = "暖色寄り 🔴" if delta_b > 2 else ("寒色寄り 🔵" if delta_b < -2 else "ニュートラル ⚪")
                tint = "赤/マゼンタ寄り" if delta_a > 2 else ("緑寄り" if delta_a < -2 else "なし")
                st.markdown(f"色温度の変化: **{tone}** (Δb={delta_b:+.1f})")
                st.markdown(f"色かぶり: **{tint}** (Δa={delta_a:+.1f})")
            if "region_weights" in d:
                st.caption("**領域ごとの解析ウェイト**")
                for region, w in d["region_weights"].items():
                    label = {"shadow":"シャドウ","midtone":"ミッドトーン","highlight":"ハイライト"}[region]
                    st.markdown(f"{label}: {w*100:.0f}%")
            if "spline_gamma" in d:
                st.caption("**スプライン推定ガンマ（生値）**")
                for ch, g in d["spline_gamma"].items():
                    st.markdown(f"Gamma{ch}: `{g:.3f}`")

    st.divider()
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
