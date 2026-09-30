from __future__ import annotations
import os
from io import BytesIO
from pathlib import Path
from urllib.request import Request, urlopen
import pandas as pd
import streamlit as st
from workplace.analytics import prepare, demo_data

DEFAULT_CSV = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSnuQD0k37rAqGskyHXOhri32cd8nsV8yiEFDLF7nuqKBkEdDfgkdrtYtx2Tw1pXyU_N3bADMcVD8iX/pub?output=csv"


def setting(name: str, default=""):
    if os.environ.get(name) is not None:
        return os.environ[name]
    try:
        return st.secrets.get(name, default)
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return default


@st.cache_data(ttl=600, max_entries=4, show_spinner=False)
def fetch(source: str, order: str, demo: bool = False):
    if demo:
        raw = demo_data()
    elif source.startswith(("https://", "http://")):
        with urlopen(Request(source, headers={"User-Agent": "NeatWorkplaceDashboard/1.0"}), timeout=60) as response:
            raw = pd.read_csv(BytesIO(response.read()))
    else:
        raw = pd.read_csv(Path(source))
    data, quality = prepare(raw, order)
    return data, quality, pd.Timestamp.now()


def load():
    demo = st.session_state.get("demo_mode", False)
    source = setting("NEAT_TELEMETRY_CSV", DEFAULT_CSV)
    order = setting("NEAT_DATE_ORDER", "legacy_mixed")
    try:
        with st.spinner("Loading room observations…"):
            data, quality, fetched = fetch(source, order, demo)
    except Exception as exc:
        st.error("The telemetry feed could not be loaded. Check its availability and CSV columns, then try again.")
        with st.expander("Connection details"):
            st.write(type(exc).__name__)
            if isinstance(exc, ValueError):
                st.write(str(exc))
        if st.button("Retry connection"):
            fetch.clear()
            st.rerun()
        st.button("Explore with clearly labelled sample data", on_click=lambda: st.session_state.update(demo_mode=True))
        st.stop()
    if data.empty:
        st.warning("The feed contains no usable room observations.")
        st.stop()
    if demo:
        st.info("Demonstration mode · All readings on this page are generated sample data.")
    return data, quality, fetched
