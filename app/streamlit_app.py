"""Hello-world page: proves the app can open the warehouse read-only."""

import pandas as pd
import streamlit as st

from vgc.db import session, warehouse_path

st.set_page_config(page_title="VGC Teambuilding", page_icon="⚔️", layout="wide")
st.title("VGC Teambuilding Dashboard")
st.caption("Pokémon Champions VGC Doubles · Session 0 skeleton")

with st.sidebar:
    st.header("Team input")
    st.text_input("PokePaste URL", placeholder="https://pokepast.es/...", disabled=True)
    st.selectbox("Regulation", ["M-C", "M-B"], disabled=True)
    st.caption("Inputs go live in Phase 1.")

try:
    with session(read_only=True) as con:
        tables = con.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'main' ORDER BY table_name"
        ).fetchall()
        rows = [
            {"table": t, "rows": con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]}
            for (t,) in tables
        ]
except FileNotFoundError as e:
    st.error(str(e))
    st.stop()

st.success(f"Connected read-only to `{warehouse_path().name}`")
st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
