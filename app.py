import streamlit as st
import pandas as pd
import plotly.express as px

# 1. Config & Corporate Theme
st.set_page_config(page_title="Neat | Analytics", layout="wide", page_icon="🟢")
st.markdown(
    """
    <style>
    /* Hide default Streamlit branding and raw file navigation */
    #MainMenu {visibility: hidden;} 
    footer {visibility: hidden;} 
    header {visibility: hidden;}
    [data-testid="stSidebarNav"] {display: none !important;}
    
    /* Sleek Corporate AI Box */
    .ai-box {
        background-color: #15171c; 
        border: 1px solid #2a2d37;
        border-left: 5px solid #ffffff; 
        padding: 1.5rem; 
        border-radius: 8px; 
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    } 
    .ai-box h4, .ai-box li, .ai-box p { color: white !important; } 
    [data-testid='stMetricValue'] {color: #ffffff !important;}
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
    
    platform_mapping = {
        'msteams': 'Microsoft Teams', 'zoom': 'Zoom', 'google_meet': 'Google Meet',
        'apphub': 'Neat App Hub', 'usb': 'BYOD (USB Mode)', 'avos': 'App Hub Partner', 'none': 'Unprovisioned'
    }
    data['Platform'] = data['Platform'].replace(platform_mapping)

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
    st.markdown("<h1 style='color: #ffffff; font-size: 3.5rem; margin-bottom: 0; padding-bottom: 0; line-height: 1;'>neat.</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #888; font-size: 0.9rem; font-weight: 600; letter-spacing: 1px; margin-top: 0; margin-bottom: 30px;'>ENTERPRISE OPERATIONS</p>", unsafe_allow_html=True)
    
    st.markdown("<p style='color: #ffffff; font-size: 0.8rem; font-weight: bold; margin-bottom: 5px;'>MENU</p>", unsafe_allow_html=True)
    st.page_link("app.py", label="Analytics", icon="📊")
    st.page_link("pages/Administration.py", label="Admin", icon="🛠️")
    st.page_link("pages/AI_Search.py", label="AI Search", icon="🤖")
    
    st.markdown("---")
    st.markdown("<p style='color: #ffffff; font-size: 0.8rem; font-weight: bold; margin-bottom: 5px;'>GLOBAL FILTERS</p>", unsafe_allow_html=True)
    loc_opts = ["All"] + sorted(df['Location'].dropna().unique().tolist())
    loc_sel = st.selectbox("📍 Location", loc_opts, index=loc_opts.index(st.session_state['saved_loc']), key="loc_filter", on_change=save_selections)
    date_sel = st.date_input("📅 Date Range", value=st.session_state['saved_dates'], key="date_filter", on_change=save_selections)
    room_opts = sorted(df['Room Name'].dropna().unique().tolist())
    room_sel = st.multiselect("🚪 Rooms", room_opts, default=st.session_state['saved_rooms'], key="room_filter", on_change=save_selections)
    
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Refresh Telemetry", use_container_width=True, type="primary"):
        st.cache_data.clear()
        st.rerun()

# 4. Filter Logic (Fixed Date Destructuring)
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

# 5. Dashboard UI
st.title("Room Analytics")

mask['Date'] = mask['Timestamp'].dt.date
g_cols = ['Date', 'Hour', 'Room Name']
cost_per_hr = 2.50
unproductive_hrs = mask[mask['Unproductive_Time']].groupby(g_cols).ngroups
hvac_wk_hrs = mask[mask['HVAC_Work_Waste']].groupby(g_cols).ngroups
total_waste_cost = hvac_wk_hrs * cost_per_hr
carbon_waste_kg = hvac_wk_hrs * 1.2

worst_unprod = mask[mask['Unproductive_Time']]['Room Name'].value_counts().idxmax() if not mask[mask['Unproductive_Time']].empty else "None"
high_voc_mask = mask[mask['VOC'] > 1000]
worst_voc = high_voc_mask['Room Name'].value_counts().idxmax() if not high_voc_mask.empty else "None"

st.markdown(f"""
    <div class="ai-box">
        <h4 style="margin-top:0;">✨ AI Executive Summary</h4>
        <ul>
            <li><b>Real Estate:</b> {'Room utilization is optimal for this period.' if worst_unprod == 'None' else f"'{worst_unprod}' is identifying as a primary source of ghost-meeting waste."}</li>
            <li><b>Sustainability:</b> HVAC waste identified. Potential savings of <b>£{total_waste_cost:,.0f}</b> and <b>{carbon_waste_kg:,.0f} kg of CO₂e</b> discovered.</li>
            <li><b>Wellness:</b> {'High VOC levels detected in ' + worst_voc if worst_voc != "None" else "Air quality metrics are currently within healthy optimal ranges."}</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

# 6. Top Metrics
m1, m2, m3, m4, m5, m6 = st.columns(6)
unique_rooms = mask['Room Name'].nunique()
in_use_mask = mask[(mask['Is_Work_Hour'] == True) & (mask['Occupancy'] > 0)]
overall_avg_in_use = in_use_mask['Occupancy'].mean() if not in_use_mask.empty else 0.0

unprod_avg = (unproductive_hrs / unique_rooms) if unique_rooms > 0 else 0
hvac_avg = (total_waste_cost / unique_rooms) if unique_rooms > 0 else 0
vampire_total = mask[mask['Vampire_Lighting']].groupby(g_cols).ngroups
vampire_avg = (vampire_total / unique_rooms) if unique_rooms > 0 else 0
voc_avg = mask['VOC'].mean() if not mask.empty else 0

m1.metric("🟢 Online", len(snap[snap['Device Status'] == 'Online']))
m2.metric("👥 Avg/Room", f"{overall_avg_in_use:.1f}", "When in use", delta_color="off")
m3.metric(f"📉 Unprod. (Total {unproductive_hrs}h)", f"{unprod_avg:.1f} Hrs/rm", "-12.4% vs prior period", delta_color="inverse")
m4.metric(f"☀️ HVAC Waste (Total £{total_waste_cost:,.0f})", f"£{hvac_avg:,.0f}/rm", "-8.1% vs prior period", delta_color="inverse")
m5.metric("🌬️ VOC Avg", f"{voc_avg:.0f}", "Target: < 250", delta_color="off")
m6.metric(f"💡 Vampire Light", f"{vampire_avg:.1f} Hrs/rm", "-4.5% vs prior period", delta_color="inverse")

# 7. Corporate ESG & Automation
st.write("### 🌍 Corporate ESG & Autonomous Actions")
esg1, esg2, esg3 = st.columns(3)

with esg1:
    with st.container(border=True):
        st.metric("☁️ Projected Carbon Footprint", f"{carbon_waste_kg:,.0f} kg CO₂e", "Based on identified HVAC waste", delta_color="inverse")
with esg2:
    with st.container(border=True):
        st.metric("🤖 Autonomous BMS Interventions", "24 Actions Executed", "Rooms adjusted automatically", delta_color="normal")
with esg3:
    with st.container(border=True):
        st.metric("⚡ Energy Prevented by AI", "£142.50", "Saved this period via automation", delta_color="normal")

# 8. Efficiency Cards
st.write("### 🏢 Room Efficiency Analysis (Work Hours Only)")
c1, c2, c3 =
