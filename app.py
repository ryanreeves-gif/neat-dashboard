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
    
    # Smart Capacity Fix
    if 'Capacity' in data.columns:
        data['Capacity'] = pd.to_numeric(data['Capacity'], errors='coerce')
    else:
        data['Capacity'] = float('nan')
    data['Capacity'] = data.groupby('Room Name')['Capacity'].transform('max')
    data['Capacity'] = data['Capacity'].fillna(4)
    
    # --- NEW: Safely load VOC and Light Level (Defaults to 0 if missing) ---
    data['VOC'] = pd.to_numeric(data.get('VOC', 0), errors='coerce').fillna(0)
    data['Light Level'] = pd.to_numeric(data.get('Light Level', 0), errors='coerce').fillna(0)
    
    data['Hour'] = data['Timestamp'].dt.hour
    data['Day'] = data['Timestamp'].dt.strftime('%A')
    
    is_weekday = data['Day'].isin(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'])
    is_weekend = data['Day'].isin(['Saturday', 'Sunday'])
    is_daytime = (data['Hour'] >= 9) & (data['Hour'] < 18)
    
    data['Is_Work_Hour'] = is_weekday & is_daytime
    data['Is_Night_Hour'] = is_weekday & ~is_daytime
    data['Is_Weekend_Hour'] = is_weekend
    
    data['Unproductive_Time'] = data['Is_Work_Hour'] & (data['Occupancy'] == 0)
    hvac_base = (data['Occupancy'] == 0) & (data['Temperature'] > 22.0)
    data['HVAC_Work_Waste'] = hvac_base & data['Is_Work_Hour']
    data['HVAC_Night_Waste'] = hvac_base & data['Is_Night_Hour']
    data['HVAC_Weekend_Waste'] = hvac_base & data['Is_Weekend_Hour']
    
    # --- NEW: Vampire Lighting (Empty room, but lights are ON > 50) ---
    data['Vampire_Lighting'] = (data['Occupancy'] == 0) & (data['Light Level'] > 50)
    
    return data

df = load_data()
valid_dates = df['Timestamp'].dropna()

if valid_dates.empty:
    st.error("No valid timestamps found.")
    st.stop()

# 3. GLOBALLY SYNCED SIDEBAR
if 'saved_loc' not in st.session_state: st.session_state['saved_loc'] = "All"
if 'saved_dates' not in st.session_state: st.session_state['saved_dates'] = (valid_dates.min().date(), valid_dates.max().date())
if 'saved_rooms' not in st.session_state: st.session_state['saved_rooms'] = []

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

if loc_sel != "All": mask = mask[mask['Location'] == loc_sel]
if room_sel: mask = mask[mask['Room Name'].isin(room_sel)]
snap = mask.sort_values('Timestamp').drop_duplicates('Room Name', keep='last')

# 5. Dashboard UI
st.title("Room Analytics Dashboard")

# --- DYNAMIC AI ENGINE LOGIC ---
# Pre-calculate totals for the AI to "read"
mask['Date'] = mask['Timestamp'].dt.date
g_cols = ['Date', 'Hour', 'Room Name']
cost_per_hr = 2.50

unproductive_hrs = mask[mask['Unproductive_Time']].groupby(g_cols).ngroups
hvac_wk = mask[mask['HVAC_Work_Waste']].groupby(g_cols).ngroups
hvac_nt = mask[mask['HVAC_Night_Waste']].groupby(g_cols).ngroups
hvac_we = mask[mask['HVAC_Weekend_Waste']].groupby(g_cols).ngroups
total_waste_cost = (hvac_wk + hvac_nt + hvac_we) * cost_per_hr

# 1. Real Estate Insight
if unproductive_hrs > 0:
    worst_unprod_room = mask[mask['Unproductive_Time']]['Room Name'].value_counts().idxmax()
    unprod_text = f"<b>Real Estate:</b> '{worst_unprod_room}' is our most underutilized asset in this selection. Consider repurposing it to maximize ROI."
else:
    unprod_text = "<b>Real Estate:</b> Room utilization is highly efficient across the selected range. No major ghost-meeting anomalies detected."

# 2. Sustainability Insight
if total_waste_cost > 0:
    sust_text = f"<b>Sustainability:</b> We have identified <b>£{total_waste_cost:,.0f}</b> in estimated HVAC waste. Automating BMS shutdowns during nights/weekends will immediately recover this."
else:
    sust_text = "<b>Sustainability:</b> Zero HVAC waste detected for this selection. Building efficiency is optimal."

# 3. Wellness Insight
high_voc_mask = mask[mask['VOC'] > 1000]
if not high_voc_mask.empty:
    worst_voc_room = high_voc_mask['Room Name'].value_counts().idxmax()
    well_text = f"<b>Wellness:</b> Critical warning: High VOCs detected frequently in '{worst_voc_room}'. Immediate HVAC ventilation check required to protect cognitive performance."
else:
    well_text = "<b>Wellness:</b> Air quality and VOC metrics are within healthy, optimal ranges. Low risk of cognitive fatigue."

# Render the dynamic summary
st.markdown(
    f"""
    <div class="ai-box">
        <h4 style="margin-top:0;">✨ AI Executive Summary</h4>
        <ul>
            <li>{unprod_text}</li>
            <li>{sust_text}</li>
            <li>{well_text}</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

# 6. Top Metrics (6 Columns)

# 6. Top Metrics (6 Columns)
m1, m2, m3, m4, m5, m6 = st.columns(6)

on_count = len(snap[snap['Device Status'] == 'Online']) if not snap.empty else 0
avg_occ = mask[mask['Is_Work_Hour']]['Occupancy'].mean() if not mask[mask['Is_Work_Hour']].empty else 0.0

m1.metric("🟢 Online", on_count)
m2.metric("👥 Avg/Room (9-6)", f"{avg_occ:.1f}")

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

# 7. Efficiency Cards
st.write("### 🏢 Room Efficiency Analysis (Work Hours Only)")
c1, c2, c3 = st.columns(3)
work_mask = mask[mask['Is_Work_Hour'] == True]

def draw_card(col, title, df_sub, cap_label):
    with col:
        with st.container(border=True):
            st.write(f"**{title}**")
            in_use_df = df_sub[df_sub['Occupancy'] > 0]
            avg_p = in_use_df['Occupancy'].mean() if not in_use_df.empty else 0.0
            avg_cap = df_sub['Capacity'].mean() if not df_sub.empty else 1.0
            if pd.isna(avg_p): avg_p = 0.0
            if pd.isna(avg_cap) or avg_cap <= 0: avg_cap = 1.0
            st.metric("Avg People (When In Use)", f"{avg_p:.1f}", delta=f"{cap_label} Max", delta_color="off")
            st.progress(max(0.0, min((avg_p / avg_cap), 1.0)))

draw_card(c1, "Small (1-4)", work_mask[work_mask['Capacity'] <= 4], "4")
draw_card(c2, "Medium (5-8)", work_mask[(work_mask['Capacity'] > 4) & (work_mask['Capacity'] <= 8)], "8")
draw_card(c3, "Large (9-20)", work_mask[work_mask['Capacity'] > 8], "20")

# 8. Wellness & Energy Expansion
st.write("### 🌿 Environmental Health & Operations Risk")
w1, w2, w3, w4 = st.columns(4)

avg_humidity = mask[mask['Humidity'] > 0]['Humidity'].mean() if not mask.empty else 0
if pd.isna(avg_humidity): avg_humidity = 0

good_aq = len(mask[mask['Air Quality'] == 'Good'])
total_aq = len(mask[mask['Air Quality'].notna() & (mask['Air Quality'] != 'Unknown')])
good_aq_pct = (good_aq / total_aq * 100) if total_aq > 0 else 0

vampire_hrs = mask[mask['Vampire_Lighting']].groupby(g_cols).ngroups
high_voc_hrs = mask[mask['VOC'] > 1000].groupby(g_cols).ngroups # Assuming > 1000 ppb is high

with w1:
    with st.container(border=True): st.metric("💧 Avg Humidity", f"{avg_humidity:.1f}%", "Optimal: 30-50%", delta_color="off")
with w2:
    with st.container(border=True): st.metric("🌬️ Air Quality (Good)", f"{good_aq_pct:.1f}%", "Target: >95%", delta_color="off")
with w3:
    with st.container(border=True): st.metric("⚠️ High VOC Risk", f"{high_voc_hrs} Hrs", "Cognitive Decline Risk", delta_color="inverse")
with w4:
    with st.container(border=True): st.metric("💡 Vampire Lighting", f"{vampire_hrs} Hrs", "Empty but Lights ON", delta_color="inverse")

# 9. Environmental & Occupancy Trends Tabs
st.write("### 📈 Full IoT Telemetry Trends")
if not mask.empty and 'Timestamp' in mask.columns:
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["👥 Occupancy", "🌡️ Temperature", "💧 Humidity", "🌬️ VOC", "💡 Light Level"])
    
    def render_chart(y_col):
        if y_col in mask.columns:
            fig = px.line(mask, x="Timestamp", y=y_col, color="Room Name", line_shape='spline')
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)
            
    with tab1: render_chart("Occupancy")
    with tab2: render_chart("Temperature")
    with tab3: render_chart("Humidity")
    with tab4: render_chart("VOC")
    with tab5: render_chart("Light Level")
else:
    st.info("Insufficient data to display Trends.")
