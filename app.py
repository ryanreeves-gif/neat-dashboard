import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Neat | Dashboard", layout="wide", page_icon="🟢")
st.markdown("<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;} .ai-box {background-color: #1e2129; border-left: 5px solid #00d2b4; padding: 1.5rem; border-radius: 10px; margin-bottom: 2rem;} .ai-box h4, .ai-box li, .ai-box p { color: white !important; } [data-testid='stMetricValue'] {color: #00d2b4 !important;}</style>", unsafe_allow_html=True)

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
    is_daytime = (data['Hour'] >= 9) & (data['Hour'] < 18)
    
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

with st.sidebar:
    st.markdown("<h1 style='color: #00d2b4;'>neat.</h1>", unsafe_allow_html=True)
    loc_sel = st.selectbox("📍 Location", ["All"] + sorted(df['Location'].dropna().unique().tolist()))
    date_sel = st.date_input("📅 Date Range", value=(valid_dates.min().date(), valid_dates.max().date()))
    room_pool = df[df['Location'] == loc_sel] if loc_sel != "All" else df
    room_sel = st.multiselect("🚪 Rooms", sorted(room_pool['Room Name'].dropna().unique().tolist()))

mask = df.copy()
if isinstance(date_sel, tuple) and len(date_sel) == 2: mask = mask[(mask['Timestamp'].dt.date >= date_sel[0]) & (mask['Timestamp'].dt.date <= date_sel[1])]
if loc_sel != "All": mask = mask[mask['Location'] == loc_sel]
if room_sel: mask = mask[mask['Room Name'].isin(room_sel)]

snap = mask.sort_values('Timestamp').drop_duplicates('Room Name', keep='last')

st.title("Room Analytics Dashboard")
st.markdown('<div class="ai-box"><h4 style="margin-top:0;">✨ AI Executive Summary</h4><ul><li><b>Real Estate:</b> Unproductive time identified. Consider repurposing consistently empty spaces.</li><li><b>Sustainability:</b> HVAC waste categorized. Adjust building management schedules for Nights and Weekends.</li><li><b>Wellness:</b> Air quality tracked against occupancy to ensure high cognitive performance.</li></ul></div>', unsafe_allow_html=True)

m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("🟢 Online", len(snap[snap['Device Status'] == 'Online']) if not snap.empty else 0)
m2.metric("👥 Avg/Room", f"{mask['Occupancy'].mean():.1f}" if not mask.empty else "0.0")

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

st.write("### 🏢 Room Efficiency Analysis")
c1, c2, c3 = st.columns(3)
def draw_card(col, title, df_sub, cap_label):
    with col:
        with st.container(border=True):
            st.write(f"**{title}**")
            avg_p = df_sub['Occupancy'].mean() if not df_sub.empty else 0.0
            avg_cap = df_sub['Capacity'].mean() if not df_sub.empty else 1.0
            if pd.isna(avg_p): avg_p = 0.0
            if pd.isna(avg_cap) or avg_cap <= 0: avg_cap = 1.0
            st.metric("Avg People", f"{avg_p:.1f}", delta=f"{cap_label} Max", delta_color="off")
            st.progress(max(0.0, min((avg_p / avg_cap), 1.0)))

draw_card(c1, "Small (1-4)", mask[mask['Capacity'] <= 4], "4")
draw_card(c2, "Medium (5-8)", mask[(mask['Capacity'] > 4) & (mask['Capacity'] <= 8)], "8")
draw_card(c3, "Large (9-20)", mask[mask['Capacity'] > 8], "20")

# --- V3.0 Wellness Section ---
st.write("### 🌿 Environmental Health & Wellness")
w1, w2, w3 = st.columns(3)
mask['Humidity'] = pd.to_numeric(mask.get('Humidity', 0), errors='coerce').fillna(0)
avg_humidity = mask[mask['Humidity'] > 0]['Humidity'].mean()
if pd.isna(avg_humidity): avg_humidity = 0

good_aq = len(mask[mask['Air Quality'] == 'Good'])
total_aq = len(mask[mask['Air Quality'].notna() & (mask['Air Quality'] != 'Unknown')])
good_aq_pct = (good_aq / total_aq * 100) if total_aq > 0 else 0

mask['Productivity_Risk'] = (mask['Occupancy'] > 0) & (mask['Air Quality'].isin(['Moderate', 'Poor']))
risk_hrs = mask[mask['Productivity_Risk']].groupby(g_cols).ngroups

with w1:
    with st.container(border=True): st.metric("💧 Avg Humidity", f"{avg_humidity:.1f}%", "Optimal: 30-50%", delta_color="off")
with w2:
    with st.container(border=True): st.metric("🌬️ Air Quality (Good)", f"{good_aq_pct:.1f}%", "Target: >95%", delta_color="off")
with w3:
    with st.container(border=True): st.metric("⚠️ Productivity Risk", f"{risk_hrs} Hrs", "- Occupied + Poor Air", delta_color="inverse")

st.write("### 📈 Occupancy Trends")
if not mask.empty and 'Timestamp' in mask.columns and 'Occupancy' in mask.columns:
    fig = px.line(mask, x="Timestamp", y="Occupancy", color="Room Name", line_shape='spline')
    fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)
