import streamlit as st

st.set_page_config(
    page_title="Camp Snap V105 Filter Generator",
    page_icon="📷",
    layout="centered",
    initial_sidebar_state="collapsed",
)

pg = st.navigation(
    [
        st.Page("pages/home.py",           title="ホーム",                   default=True),
        st.Page("pages/editor.py",         title="編集"),
        st.Page("pages/filter_gen.py",     title="写真から作る"),
        st.Page("pages/preset_builder.py", title="ゼロから作る"),
        st.Page("pages/compare.py",        title="フィルター比較"),
    ],
    position="hidden",
)

pg.run()
