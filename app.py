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
    data['Timestamp'] = pd.to_datetime(data['Timestamp'], errors='coerce')
    data['Capacity'] = pd.to_numeric(data.get('Capacity', 4), errors='coerce').fillna(4)
    data['Hour'] = data['Timestamp'].dt.hour
    data['Day'] = data['Timestamp'].dt.strftime('%A')
    
    is_weekday = data['Day'].isin(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'])
    is_weekend = data['Day'].isin(['Saturday', 'Sunday'])
    is_daytime = (data['Hour'] >= 9) & (data['Hour'] < 18) # 9am to 5:59pm
    
    data['Is_Work_Hour'] = is_weekday & is_daytime
    data['Is_Night_Hour'] = is_weekday & ~is_daytime
    data['Is_Weekend_Hour'] = is_weekend
    
    data['Unproductive_Time'] = data['Is_Work_Hour'] & (data['Occupancy'] == 0)
    hvac_base = (data['Occupancy'] == 0) & (data['Temperature'] > 22.0)
    data['HVAC_Work_Waste'] = hvac_base & data['Is_Work_Hour']
    data['HVAC_Night_Waste'] = hvac_base & data['Is_Night_Hour']
    data['HVAC_Weekend_Waste'] = hvac_base & data['Is_Weekend_Hour']
    
    return data

df = load_data()
valid_dates = df['Timestamp'].dropna()

if valid_dates.empty:
    st.error("No valid timestamps found.")
    st.stop()

# 3. GLOBALLY SYNCED SIDEBAR (With Permanent Memory)
if 'saved_loc' not in st.session_state: 
    st.session_state['saved_loc'] = "All"
if 'saved_dates' not in st.session_state: 
    st.session_state['saved_dates'] = (valid_dates.min().date(), valid_dates.max().date())
if 'saved_rooms' not in st.session_state: 
    st.session_state['saved_rooms'] = []

def save_selections():
    st.session_state['saved_loc'] = st.session_state['loc_filter']
    st.session_state['saved_dates'] = st.session_state['date_filter']
    st.session_state['saved_rooms'] = st.session_state['room_filter']

with st.sidebar:
    st.markdown("<h1 style='color: #00d2b4;'>neat.</h1>", unsafe_allow_html=True)
    
    loc_opts = ["All"] + sorted(df['Location'].dropna().unique().tolist())
    loc_idx = loc_opts.index(st.session_state['saved_loc']) if st.session_state['saved_loc'] in loc_opts else 0
    loc_sel = st.selectbox("📍 Location", loc_opts, index=loc_idx, key="loc_filter", on_change=save_selections)
    
    date_sel = st.date_input("📅 Date Range", value=st.session_state['saved_dates'], key="date_filter", on_change=save_selections)
    
    room_pool = df[df['Location'] == loc_sel] if loc_sel != "All" else df
    room_opts = sorted(room_pool['Room Name'].dropna().unique().tolist())
    valid_rooms = [r for r in st.session_state['saved_rooms'] if r in room_opts]
    room_sel = st.multiselect("🚪 Rooms", room_opts, default=valid_rooms, key="room_filter", on_change=save_selections)
    
    st.markdown("---")
    if st.button("🔄 Refresh Telemetry", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# 4. Filter Logic
mask = df.copy()
if isinstance(date_sel, tuple) and len(date_sel) == 2:
    mask = mask[(mask['Timestamp'].dt.date >= date_sel[0]) & (mask['Timestamp'].dt.date <= date_sel[1])]
elif isinstance(date_sel, tuple) and len(date_sel) == 1:
    mask = mask[mask['Timestamp'].dt.date == date_sel[0]]

if loc_sel != "All": 
    mask = mask[mask['Location'] == loc_sel]
if room_sel: 
    mask = mask[mask['Room Name'].isin(room_sel)]

snap = mask.sort_values('Timestamp').drop_duplicates('Room Name', keep='last')

# 5. Dashboard UI
st.title("Room Analytics Dashboard")

st.markdown(
    """
    <div class="ai-box">
        <h4 style="margin-top:0;">✨ AI Executive Summary</h4>
        <ul>
            <li><b>Real Estate:</b> Unproductive time identified. Consider repurposing consistently empty spaces.</li>
            <li><b>Sustainability:</b> HVAC waste categorized. Adjust building management schedules for Nights and Weekends.</li>
            <li><b>Wellness:</b> Air quality tracked against occupancy to ensure high cognitive performance.</li>
        </ul>
    </div>
    """, 
    unsafe_allow_html=True
)

# 6. Top Metrics (6 Columns Monetized)
m1, m2, m3, m4, m5, m6 = st.columns(6)

on_count = len(snap[snap['Device Status'] == 'Online']) if not snap.empty else 0
avg_occ = mask['Occupancy'].mean() if not mask.empty else 0.0

m1.metric("🟢 Online", on_count)
m2.metric("👥 Avg/Room", f"{avg_occ:.1f}")

mask['Date'] = mask['Timestamp'].dt.date
g_cols = ['Date', 'Hour', 'Room Name']

unproductive_hrs = mask[mask['Unproductive_Time']].groupby(g_cols).ngroups
total_work_hrs = mask[mask['Is_Work_Hour']].groupby(g_cols).ngroups
unprod_pct = (unproductive_hrs / total_work_hrs * 100) if total_work_hrs > 0 else 0

cost_per_hr = 2.50
hvac_wk = mask[mask['HVAC_Work_Waste']].groupby(g_cols).ngroups
hvac_nt = mask[mask['HVAC_Night_Waste']].groupby(g_cols).ngroups
hvac_we = mask[mask['HVAC_Weekend_Waste']].groupby(g_cols).ngroups

m3.metric("📉 Unproductive", f"{unproductive_hrs} Hrs", delta=f"- {unprod_pct:.1f}% of Work Hrs", delta_color="inverse")
m4.metric("☀️ HVAC (Day)", f"{hvac_wk} Hrs", delta=f"- £{hvac_wk * cost_per_hr:,.0f} Est. Loss", delta_color="inverse")
m5.metric("🌙 HVAC (Night)", f"{hvac_nt} Hrs", delta=f"- £{hvac_nt * cost_per_hr:,.0f} Est. Loss", delta_color="inverse")
m6.metric("🛋️ HVAC (Wknd)", f"{hvac_we} Hrs", delta=f"- £{hvac_we * cost_per_hr:,.0f} Est. Loss", delta_color="inverse")

# 7. Efficiency Cards (Fixed: Work Hours + When In Use Only)
st.write("### 🏢 Room Efficiency Analysis (Work Hours Only)")
c1, c2, c3 = st.columns(3)

work_mask = mask[mask['Is_Work_Hour'] == True]

def draw_card(col, title, df_sub, cap_label):
    with col:
        with st.container(border=True):
            st.write(f"**{title}**")
