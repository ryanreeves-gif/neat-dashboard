import streamlit as st
import pandas as pd
import requests
import time

# 1. Config & Corporate Theme
st.set_page_config(page_title="Neat | AI Search", layout="wide", page_icon="🤖")
st.markdown(
    """
    <style>
    /* Hide default Streamlit branding and raw file navigation */
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    [data-testid="stSidebarNav"] {display: none !important;}
    
    /* Sleek Corporate Action Card */
    .action-card {
        background-color: #15171c; 
        border: 1px solid #2a2d37;
        border-left: 5px solid #00d2b4; 
        padding: 1.5rem; 
        border-radius: 8px; 
        margin-top: 1rem; 
        color: white;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .stTextInput input {background-color: #15171c; color: white; border: 1px solid #2a2d37;}
    .stTextInput input:focus {border: 1px solid #00d2b4; box-shadow: none;}
    </style>
    """, unsafe_allow_html=True
)

# 2. Data Loading (Synced Logic)
@st.cache_data(ttl=600)
def load_data():
    url = "https://docs.google.com/spreadsheets/d/1bconB0u70BZv0aTblhhEA8_q56rlO6KAU1RG0P8yOjE/export?format=csv"
    data = pd.read_csv(url)
    data.columns = data.columns.str.strip()
    data['Timestamp'] = pd.to_datetime(data['Timestamp'], errors='coerce')
    platform_mapping = {
        'msteams': 'Microsoft Teams', 'zoom': 'Zoom', 'google_meet': 'Google Meet',
        'apphub': 'Neat App Hub', 'usb': 'BYOD (USB Mode)', 'avos': 'App Hub Partner', 'none': 'Unprovisioned'
    }
    data['Platform'] = data['Platform'].replace(platform_mapping)
    return data

df = load_data()
valid_dates = df['Timestamp'].dropna()

if valid_dates.empty:
    st.error("No valid timestamps found.")
    st.stop()

# 3. GLOBALLY SYNCED SIDEBAR & BRANDED NAVIGATION
if 'saved_loc' not in st.session_state: st.session_state['saved_loc'] = "All"
if 'saved_dates' not in st.session_state: st.session_state['saved_dates'] = (valid_dates.min().date(), valid_dates.max().date())
if 'saved_rooms' not in st.session_state: st.session_state['saved_rooms'] = []

def save_selections():
    st.session_state['saved_loc'] = st.session_state['loc_filter']
    st.session_state['saved_dates'] = st.session_state['date_filter']
    st.session_state['saved_rooms'] = st.session_state['room_filter']

with st.sidebar:
    # Corporate Branding Header
    st.markdown("<h1 style='color: #00d2b4; font-size: 3.5rem; margin-bottom: 0; padding-bottom: 0; line-height: 1;'>neat.</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #888; font-size: 0.9rem; font-weight: 600; letter-spacing: 1px; margin-top: 0; margin-bottom: 30px;'>ENTERPRISE OPERATIONS</p>", unsafe_allow_html=True)
    
    # Custom Corporate Navigation Menu
    st.markdown("<p style='color: #00d2b4; font-size: 0.8rem; font-weight: bold; margin-bottom: 5px;'>MENU</p>", unsafe_allow_html=True)
    st.page_link("app.py", label="Analytics", icon="📊")
    st.page_link("pages/Administration.py", label="Admin", icon="🛠️")
    st.page_link("pages/AI_Search.py", label="AI Search", icon="🤖")
    
    st.markdown("---")
    
    # Standard Filters
    st.markdown("<p style='color: #00d2b4; font-size: 0.8rem; font-weight: bold; margin-bottom: 5px;'>GLOBAL FILTERS</p>", unsafe_allow_html=True)
    loc_opts = ["All"] + sorted(df['Location'].dropna().unique().tolist())
    loc_sel = st.selectbox("📍 Location", loc_opts, index=loc_opts.index(st.session_state['saved_loc']), key="loc_filter", on_change=save_selections)
    date_sel = st.date_input("📅 Date Range", value=st.session_state['saved_dates'], key="date_filter", on_change=save_selections)
    room_opts = sorted(df['Room Name'].dropna().unique().tolist())
    room_sel = st.multiselect("🚪 Rooms", room_opts, default=st.session_state['saved_rooms'], key="room_filter", on_change=save_selections)
    
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Refresh Telemetry", use_container_width=True, type="primary"):
        st.cache_data.clear()
        st.rerun()

# 4. Filter Logic (Bulletproof Date Handling)
mask = df.copy()

if isinstance(date_sel, tuple):
    if len(date_sel) == 2:
        start_date, end_date = date_sel
    elif len(date_sel) == 1:
        start_date = end_date = date_sel[0]
    else:
        start_date = end_date = valid_dates.max().date()
else:
    start_date = end_date = date_sel

mask = mask[(mask['Timestamp'].dt.date >= start_date) & (mask['Timestamp'].dt.date <= end_date)]
if loc_sel != "All": mask = mask[mask['Location'] == loc_sel]
if room_sel: mask = mask[mask['Room Name'].isin(room_sel)]
snap = mask.sort_values('Timestamp').drop_duplicates('Room Name', keep='last')

# 5. Dashboard UI & AI Logic
st.title("🤖 AI Insights & Actions")
st.write("Ask questions in plain English to trigger automated workflows and API simulations.")

query = st.text_input("💬 Ask the Assistant:", placeholder="e.g., 'Show me offline devices' or 'Are there any hot rooms?'")

if query:
    q = query.lower()
    
    # Scenario 1: Offline Devices
    if "offline" in q or "down" in q or "reboot" in q:
        offline = snap[snap['Device Status'] == 'Offline']
        if not offline.empty:
            st.error(f"🚨 Found {len(offline)} offline device(s) in current scope.")
            st.dataframe(offline[['Room Name', 'Location', 'Notes']], hide_index=True)
            st.markdown("<div class='action-card'><b>AI Recommendation:</b> Execute remote reboot via <b>Neat Pulse REST API</b>.</div>", unsafe_allow_html=True)
            
            if st.button("🔌 Execute Remote Reboot (Simulated API)", type="primary"):
                with st.spinner("Authenticating with Neat API..."):
                    time.sleep(1.5)
                    st.success("API Command Sent: Reboot sequence initiated successfully.")
        else:
            st.success("✅ All systems report online.")

    # Scenario 2: App Hub / Avos
    elif "app hub" in q or "partner" in q or "avos" in q:
        partners = snap[snap['Platform'] == 'App Hub Partner']
        st.info(f"Found {len(partners)} specialized App Hub Partner devices.")
        st.dataframe(partners[['Room Name', 'Location', 'Platform']], hide_index=True)
        st.markdown("<div class='action-card'><b>Proactive Suggestion:</b> Update these devices to the latest NFK firmware for enhanced App Hub ecosystem performance.</div>", unsafe_allow_html=True)

    # Scenario 3: HVAC / Wellness Trigger
    elif "hot" in q or "temp" in q or "hvac" in q or "voc" in q:
        st.warning("🌡️ Evaluating environmental thresholds...")
        time.sleep(0.5)
        st.markdown("<div class='action-card'><b>AI Recommendation:</b> High environmental load detected in select rooms. Suggest triggering outbound webhook to Building Management System (BMS).</div>", unsafe_allow_html=True)
        
        if st.button("❄️ Trigger HVAC Adjustment via Webhook", type="primary"):
            with st.spinner("Communicating with BMS..."):
                time.sleep(1.5)
                st.success("Webhook fired successfully! HVAC flow increased.")

    # Fallback / Instructions
    else:
        st.write("I can help you manage your fleet. Try asking:")
        st.markdown("- *'Show me offline rooms'*")
        st.markdown("- *'Which rooms are running App Hub Partner software?'*")
        st.markdown("- *'Are there any hot rooms?'*")
