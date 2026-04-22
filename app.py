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

# 3. Sidebar
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
    loc_sel = st.selectbox("📍 Location", loc_opts, index=loc_opts.index(st.session_state['saved_loc']), key="loc_filter", on_change=save_selections)
    date_sel = st.date_input("📅 Date Range", value=st.session_state['saved_dates'], key="date_filter", on_change=save_selections)
    room_opts = sorted(df['Room Name'].dropna().unique().tolist())
    room_sel = st.multiselect("🚪 Rooms", room_opts, default=st.session_state['saved_rooms'], key="room_filter", on_change=save_selections)
    st.markdown("---")
    if st.button("🔄 Refresh Telemetry", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# 4. Filter Logic
mask = df.copy()
if isinstance(date_sel, tuple) and len(date_sel) == 2:
    mask = mask[(mask['Timestamp'].dt.date >= date_sel[0]) & (mask['Timestamp'].dt.date <= date_sel[1])]
if loc_sel != "All": mask = mask[mask['Location'] == loc_sel]
if room_sel: mask = mask[mask['Room Name'].isin(room_sel)]
snap = mask.sort_values('Timestamp').drop_duplicates('Room Name', keep='last')

# 5. Dashboard UI
st.title("Room Analytics Dashboard")

# AI Logic
mask['Date'] = mask['Timestamp'].dt.date
g_cols = ['Date', 'Hour', 'Room Name']
cost_per_hr = 2.50
unproductive_hrs = mask[mask['Unproductive_Time']].groupby(g_cols).ngroups
hvac_wk_hrs = mask[mask['HVAC_Work_Waste']].groupby(g_cols).ngroups
total_waste_cost = hvac_wk_hrs * cost_per_hr

worst_unprod = mask[mask['Unproductive_Time']]['Room Name'].value_counts().idxmax() if not mask[mask['Unproductive_Time']].empty else "None"
high_voc_mask = mask[mask['VOC'] > 1000]
worst_voc = high_voc_mask['Room Name'].value_counts().idxmax() if not high_voc_mask.empty else "None"

st.markdown(f"""
    <div class="ai-box">
        <h4 style="margin-top:0;">✨ AI Executive Summary</h4>
        <ul>
            <li><b>Real Estate:</b> '{worst_unprod}' is identifying as a primary source of ghost-meeting waste.</li>
            <li><b>Sustainability:</b> HVAC waste identified. Potential savings of <b>£{total_waste_cost:,.0f}</b> discovered.</li>
            <li><b>Wellness:</b> {'High VOC levels detected in ' + worst_voc if worst_voc != "None" else "Air quality metrics are currently within healthy optimal ranges."}</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

# 6. Top Metrics (6 Columns)
m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("🟢 Online", len(snap[snap['Device Status'] == 'Online']))
m2.metric("👥 Avg/Room", f"{mask[mask['Is_Work_Hour']]['Occupancy'].mean():.1f}")
m3.metric("📉 Unproductive", f"{unproductive_hrs} Hrs")
m4.metric("☀️ HVAC Waste", f"£{total_waste_cost:,.0f}")
m5.metric("🌬️ VOC Avg", f"{mask['VOC'].mean():.0f}")
m6.metric("💡 Vampire Light", f"{mask[mask['Vampire_Lighting']].groupby(g_cols).ngroups} Hrs")

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
            st.metric("Avg People (When In Use)", f"{avg_p:.1f}", delta=f"{cap_label} Max", delta_color="off")
            st.progress(max(0.0, min((avg_p / avg_cap), 1.0)))

draw_card(c1, "Small (1-4)", work_mask[work_mask['Capacity'] <= 4], "4")
draw_card(c2, "Medium (5-8)", work_mask[(work_mask['Capacity'] > 4) & (work_mask['Capacity'] <= 8)], "8")
draw_card(c3, "Large (9-20)", work_mask[work_mask['Capacity'] > 8], "20")

# --- 8. THE RETURNED WELLNESS SECTION ---
st.write("### 🌿 Environmental Health & Operations Risk")
w1, w2, w3, w4 = st.columns(4)

avg_humidity = mask[mask['Humidity'] > 0]['Humidity'].mean() if not mask.empty else 0
good_aq = len(mask[mask['Air Quality'] == 'Good'])
total_aq = len(mask[mask['Air Quality'].notna() & (mask['Air Quality'] != 'Unknown')])
good_aq_pct = (good_aq / total_aq * 100) if total_aq > 0 else 0
high_voc_hrs = mask[mask['VOC'] > 1000].groupby(g_cols).ngroups
vampire_hrs = mask[mask['Vampire_Lighting']].groupby(g_cols).ngroups

with w1:
    with st.container(border=True): st.metric("💧 Avg Humidity", f"{avg_humidity:.1f}%", "Optimal: 30-50%", delta_color="off")
with w2:
    with st.container(border=True): st.metric("🌬️ Air Quality (Good)", f"{good_aq_pct:.1f}%", "Target: >95%", delta_color="off")
with w3:
    with st.container(border=True): st.metric("⚠️ High VOC Risk", f"{high_voc_hrs} Hrs", "Cognitive Decline Risk", delta_color="inverse")
with w4:
    with st.container(border=True): st.metric("💡 Vampire Lighting", f"{vampire_hrs} Hrs", "Empty but Lights ON", delta_color="inverse")

# 9. Environmental Trends Tabs
st.write("### 📈 Full IoT Telemetry Trends")
tab1, tab2, tab3, tab4, tab5 = st.tabs(["👥 Occupancy", "🌡️ Temperature", "💧 Humidity", "🌬️ VOC", "💡 Light Level"])

def render_chart(tab, y_col):
    with tab:
        if y_col in mask.columns:
            fig = px.line(mask, x="Timestamp", y=y_col, color="Room Name", line_shape='spline')
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

render_chart(tab1, "Occupancy"); render_chart(tab2, "Temperature"); render_chart(tab3, "Humidity"); render_chart(tab4, "VOC"); render_chart(tab5, "Light Level")
