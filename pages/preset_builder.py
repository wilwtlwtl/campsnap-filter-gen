"""
プリセットビルダーページ
複数の参考画像からフィルムプリセットを自動生成する
"""

import streamlit as st
from PIL import Image
import numpy as np
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.preset_builder import build_preset_from_images, save_preset, load_presets, delete_preset
from src.flt_io import to_flt_bytes
from src.preview import apply_filter, simulate_v105


st.title("🎞️ フィルムプリセットをつくる")
st.markdown(
    "「こんな雰囲気で撮りたい」という**参考写真を複数枚**アップロードすると、"
    "その色の傾向を平均化して、再利用できる**プリセット**として保存します。\n\n"
    "写真が多いほど、より安定した仕上がりのプリセットになります。"
    "（目安: 3〜10枚）"
)
st.divider()


# ── STEP 1: 参考写真のアップロード ─────────────────────────────────────────

st.subheader("📸 STEP 1 ｜ 参考写真をまとめてアップロード")
st.caption(
    "同じ雰囲気・同じフィルムで撮った写真を複数枚選んでください。\n"
    "バラバラな雰囲気の写真を混ぜると、中途半端なプリセットになることがあります。"
)

uploaded_files = st.file_uploader(
    "JPG / PNG を複数選択できます",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True,
    label_visibility="collapsed",
)

images: list[Image.Image] = []
if uploaded_files:
    cols = st.columns(min(len(uploaded_files), 5))
    for i, f in enumerate(uploaded_files):
        img = Image.open(f).convert("RGB")
        images.append(img)
        with cols[i % 5]:
            st.image(img, use_container_width=True)
            st.caption(f"{i+1}枚目")

    st.info(f"{len(images)} 枚の写真を読み込みました。")


# ── STEP 2: プリセット名の入力 ──────────────────────────────────────────────

st.divider()
st.subheader("✏️ STEP 2 ｜ プリセットに名前をつける")

preset_name = st.text_input(
    "プリセット名",
    placeholder="例: フジフィルム風・ポートラ風・夕暮れフィルム",
    help="あとでメインページで選べる名前になります。わかりやすい名前にしてください。",
)


# ── STEP 3: 生成 ───────────────────────────────────────────────────────────

st.divider()
st.subheader("⚙️ STEP 3 ｜ プリセットを生成・保存")

can_generate = len(images) > 0 and preset_name.strip() != ""

if not can_generate:
    if len(images) == 0:
        st.info("参考写真をアップロードしてください。")
    elif preset_name.strip() == "":
        st.info("プリセット名を入力してください。")

if st.button(
    "🎨 プリセットを自動生成する",
    type="primary",
    use_container_width=True,
    disabled=not can_generate,
):
    with st.spinner(f"{len(images)}枚の写真を解析中…"):
        params, diag = build_preset_from_images(images)

    st.success(f"✅ 解析完了！「{preset_name}」として保存できます。")

    # ── 結果の視覚化 ────────────────────────────────────────────────────────

    def _bar(label, value, lo, hi, lo_word, hi_word, color="#4a90d9"):
        pct = int(max(0, min(100, (value - lo) / (hi - lo) * 100)))
        mid = (lo + hi) / 2
        note = hi_word if value > mid else lo_word
        st.markdown(f"""
<div style="display:flex;align-items:center;gap:0.7rem;margin-bottom:0.4rem;font-size:0.95rem;">
  <span style="width:130px;flex-shrink:0;">{label}</span>
  <div style="flex:1;background:#e0e0e0;border-radius:6px;height:10px;overflow:hidden;">
    <div style="width:{pct}%;height:100%;border-radius:6px;background:{color};"></div>
  </div>
  <span style="width:100px;flex-shrink:0;color:#666;font-size:0.85rem;">{note}</span>
</div>""", unsafe_allow_html=True)

    st.markdown('<div style="background:#f7f7f7;border-radius:12px;padding:1rem 1.5rem;margin:0.5rem 0;">', unsafe_allow_html=True)
    _bar("☀️ 明るさ",       params.brightness, 0.5, 1.6, "暗め",       "明るめ",      "#f5a623")
    _bar("⚡ くっきりさ",   params.contrast,   0.6, 1.4, "ふんわり",   "くっきり",    "#7ed321")
    _bar("🌈 色の鮮やかさ", params.saturation, 0.5, 1.5, "薄い・淡い", "鮮やか",      "#bd10e0")
    warmth = 1.0 + ((1/max(params.gamma_r,0.1)) - (1/max(params.gamma_b,0.1))) * 0.4
    _bar("🔴 暖かみ",       warmth,            0.5, 1.5, "寒色・クール","暖色・温かみ","#e05050")
    st.markdown('</div>', unsafe_allow_html=True)

    # 安定性スコア（標準偏差が小さいほど安定）
    avg_std = np.mean([v for v in diag["std"].values()])
    stability = max(0, int((1 - avg_std * 5) * 100))
    st.markdown(
        f"**プリセットの安定性スコア: {stability}点 / 100点**　"
        f"{'（写真間の一貫性が高く、安定したプリセットです）' if stability >= 70 else '（写真間でバラつきがあります。似た雰囲気の写真だけに絞るとスコアが上がります）'}"
    )

    # 個別画像の解析結果
    with st.expander(f"各写真の個別解析結果（{diag['n_images']}枚）", expanded=False):
        st.caption("各写真の明るさ・くっきりさ・鮮やかさの推定値です。値がバラバラな場合は写真の選び直しを検討してください。")
        import pandas as pd
        rows = []
        for i, d in enumerate(diag["individual"]):
            rows.append({
                "写真": f"{i+1}枚目",
                "明るさ": round(d["Brightness"], 3),
                "くっきりさ": round(d["Contrast"], 3),
                "鮮やかさ": round(d["Saturation"], 3),
                "赤み(GammaR)": round(d["GammaR"], 3),
                "緑み(GammaG)": round(d["GammaG"], 3),
                "青み(GammaB)": round(d["GammaB"], 3),
            })
        rows.append({
            "写真": "▶ 平均",
            "明るさ": round(diag["mean"]["Brightness"], 3),
            "くっきりさ": round(diag["mean"]["Contrast"], 3),
            "鮮やかさ": round(diag["mean"]["Saturation"], 3),
            "赤み(GammaR)": round(diag["mean"]["GammaR"], 3),
            "緑み(GammaG)": round(diag["mean"]["GammaG"], 3),
            "青み(GammaB)": round(diag["mean"]["GammaB"], 3),
        })
        st.dataframe(pd.DataFrame(rows).set_index("写真"), use_container_width=True)

    # ── プレビュー ──────────────────────────────────────────────────────────

    st.markdown("**プレビュー（参考写真の1枚目にフィルターを適用）**")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.caption("元の写真")
        st.image(images[0], use_container_width=True)
    with c2:
        st.caption("フィルター適用後")
        st.image(apply_filter(images[0], params), use_container_width=True)
    with c3:
        st.caption("V105シミュレーション")
        st.image(simulate_v105(images[0], params), use_container_width=True)

    # ── 保存 ────────────────────────────────────────────────────────────────

    st.divider()

    col_save, col_dl = st.columns(2)

    with col_save:
        if st.button("💾 プリセットとして保存する", use_container_width=True, type="primary"):
            existing = load_presets()
            if preset_name in existing:
                st.warning(f"「{preset_name}」はすでに存在します。上書きしました。")
            save_preset(
                name=preset_name,
                params=params,
                meta={
                    "n_images": diag["n_images"],
                    "stability": stability,
                    "std": diag["std"],
                },
            )
            st.success(f"✅ 「{preset_name}」を保存しました。メインページで選択できます。")

    with col_dl:
        flt_bytes = to_flt_bytes(params)
        custom_name = st.text_input(
            "ファイル名（半角英数字推奨）",
            value=preset_name.replace(' ', '_'),
            key="dl_filename_input",
        )
        final_name = custom_name.strip() or preset_name.replace(' ', '_')
        st.download_button(
            label="📥 .flt ファイルをダウンロード",
            data=flt_bytes,
            file_name=f"{final_name}.flt",
            mime="application/octet-stream",
            use_container_width=True,
        )


# ── 保存済みプリセット一覧 ───────────────────────────────────────────────────

st.divider()
st.subheader("📋 保存済みプリセット一覧")

presets = load_presets()
if not presets:
    st.info("まだプリセットが保存されていません。上の手順で作成してください。")
else:
    for name, data in presets.items():
        with st.expander(f"🎞️ {name}", expanded=False):
            p = data["params"]
            meta = data.get("meta", {})

            col_info, col_vals = st.columns([1, 1])
            with col_info:
                if meta.get("n_images"):
                    st.caption(f"参考画像: {meta['n_images']}枚")
                if meta.get("stability") is not None:
                    st.caption(f"安定性スコア: {meta['stability']}点")
            with col_vals:
                st.code(
                    "\n".join(f"{k} = {v}" for k, v in p.items()),
                    language="ini",
                )

            if st.button(f"🗑️ 削除する", key=f"del_{name}"):
                delete_preset(name)
                st.rerun()
