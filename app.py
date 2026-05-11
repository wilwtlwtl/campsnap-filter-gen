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
        st.Page("pages/filter_gen.py",     title="📷 フィルターをつくる"),
        st.Page("pages/preset_builder.py", title="🎞️ プリセットをつくる"),
        st.Page("pages/compare.py",        title="🔍 フィルターを比較する"),
    ],
    position="hidden",
)

pg.run()
