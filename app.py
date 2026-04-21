import streamlit as st

pg = st.navigation(
    [
        st.Page("pages/filter_gen.py",     title="📷 フィルターをつくる",  default=True),
        st.Page("pages/preset_builder.py", title="🎞️ プリセットをつくる"),
    ],
    position="sidebar",
)

st.set_page_config(
    page_title="Camp Snap V105 Filter Generator",
    page_icon="📷",
    layout="centered",
)

pg.run()
