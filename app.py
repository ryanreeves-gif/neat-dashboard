import streamlit as st
import pandas as pd
import plotly.express as px

# 1. Config & Theme
st.set_page_config(page_title="Neat | Dashboard", layout="wide", page_icon="🟢")
st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;} 
    footer {visibility: hidden;} 
    .ai-box {
        background-color: #1e2129; 
        border-left: 5px solid #00d2b4; 
        padding: 1.5rem; 
        border-radius: 10px; 
        margin-bottom: 2rem;
    } 
    .ai-box h4, .ai-box li, .ai-box p { color: white !important; } 
    [data-testid='stMetricValue'] {color: #00d2b4 !important;}
    </style>
    """, 
    unsafe_allow_html=True
)

# 2. Data Loading & Logic
@st.cache_data(ttl=600)
def load_data():
    url = "https://docs.google.com/spreadsheets/d/1bconB0u70BZv0aTblhhEA8_q56rlO6KAU1RG0P8yOjE/export?format=csv"
    data = pd.read_csv(url)
    data.columns = data.columns.str.strip()
    data['Timestamp'] = pd.to_datetime(data['Timestamp'], errors='coerce')
    
    # Platform Renaming
    platform_mapping = {
        'msteams': 'Microsoft Teams',
        'zoom': 'Zoom',
        'google_meet': 'Google Meet',
        'apphub': 'Neat App Hub',
        'usb': 'BYOD (USB Mode)',
        'avos': 'App Hub Partner',
        'none': 'Unprovisioned'
    }
    data['Platform'] = data['Platform'].replace(platform_mapping)

    # Smart Capacity Fix
    if 'Capacity' in data.columns:
        data['Capacity'] = pd.to_numeric(data['Capacity'], errors='coerce')
    else:
        data['Capacity'] = float('nan')
    data['Capacity'] = data.groupby('Room Name')['Capacity'].transform('max')
    data['Capacity'] = data['Capacity'].fillna(4)
    
    data['VOC'] = pd.to_numeric(data.get('VOC', 0), errors='coerce').fillna(0)
    data['Light Level'] = pd.to_numeric(data.get('Light Level', 0), errors='coerce').fillna(0)
    data['Hour'] = data['Timestamp'].dt.hour
    data['Day'] = data['Timestamp'].dt.strftime('%A')
    
    is_weekday = data['Day'].isin(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'])
    is_daytime = (data['Hour'] >= 9) & (data['Hour'] < 18)
    
    data['Is_Work_Hour'] = is_weekday & is_daytime
    data['Unproductive_Time'] = data['Is_Work_Hour'] & (data['Occupancy'] == 0)
    hvac_base = (data['Occupancy'] == 0) & (data['Temperature'] > 22.0)
    data['HVAC_Work_Waste'] = hvac_base & data['Is_Work_Hour']
    data['Vampire_Lighting'] = (data['Occupancy'] == 0) & (data['Light Level'] > 50)
    
    return data

df = load_data()
valid_dates = df['Timestamp'].dropna()

# 3. Sidebar
if 'saved_loc' not in st.session_state: st.session_state['saved_loc'] = "All"
if 'saved_dates' not in st.session_state: st.session_state['saved_dates'] = (valid_dates.min().date(), valid_dates.max().date())
if 'saved_rooms' not in st.session_state: st.session_state['saved_rooms'] = []

with st.sidebar:
    st.markdown("<h1 style='color: #00d2b4;'>neat.</h1>", unsafe_allow_html=True)
    loc_opts = ["All"] + sorted(df['Location'].dropna().unique().tolist())
    loc_sel = st.selectbox("📍 Location", loc_opts, index=loc_opts.index(st.session_state['saved_loc']), key="loc_filter")
    date_sel = st.date_input("📅 Date Range", value=st.session_state['saved_dates'], key="date_filter")
    room_opts = sorted(df['Room Name'].dropna().unique().tolist())
    room_sel = st.multiselect("🚪 Rooms", room_opts, default=st.session_state['saved_rooms'], key="room_filter")
    if st.button("🔄 Refresh Telemetry", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# 4. Filters
mask = df.copy()
if isinstance(date_sel, tuple) and len(date_sel) == 2:
    mask = mask[(mask['Timestamp'].dt.date >= date_sel[0]) & (mask['Timestamp'].dt.date <= date_sel[1])]
if loc_sel != "All": mask = mask[mask['Location'] == loc_sel]
if room_sel: mask = mask[mask['Room Name'].isin(room_sel)]

# 5. UI - Dynamic AI Summary
st.title("Room Analytics Dashboard")

# Calculation Logic for AI
unproductive_hrs = mask[mask['Unproductive_Time']].shape[0]
waste_cost = mask[mask['HVAC_Work_Waste']].shape[0] * 2.50

# AI Content
unprod_text = f"<b>Real Estate:</b> Underutilization identified. Consider repurposing empty spaces."
if unproductive_hrs > 50:
    unprod_text = f"<b>Real Estate:</b> High volume of 'Ghost Meetings' detected. Asset efficiency is currently sub-optimal."

sust_text = f"<b>Sustainability:</b> HVAC and Vampire Lighting waste tracked. Potential savings: <b>£{waste_cost:,.0f}</b>."
well_text = "<b>Wellness:</b> VOC and Air Quality levels are being monitored to ensure high cognitive performance."

st.markdown(f"""
    <div class="ai-box">
        <h4 style="margin-top:0;">✨ AI Executive Summary</h4>
        <ul><li>{unprod_text}</li><li>{sust_text}</li><li>{well_text}</li></ul>
    </div>
    """, unsafe_allow_html=True)

# ... [The rest of your Top Metrics and Efficiency Cards code remains the same]
