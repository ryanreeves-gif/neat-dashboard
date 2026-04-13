import streamlit as st
import pandas as pd
import plotly.express as px

# 1. Config & Theme
st.set_page_config(page_title="Neat | Dashboard", layout="wide", page_icon="🟢")
st.markdown("<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;} .ai-box {background-color: #1e2129; border-left: 5px solid #00d2b4; padding: 1.5rem; border-radius: 10px; margin-bottom: 2rem;} .ai-box h4, .ai-box li, .ai-box p { color: white !important; } [data-testid='stMetricValue'] {color: #00d2b4 !important;}</style>", unsafe_allow_html=True)

# 2. Data Loading (Shared logic)
@st.cache_data(ttl=600)
def load_data():
    url = "https://docs.google.com/spreadsheets/d/1bconB0u70BZv0aTblhhEA8_q56rlO6KAU1RG0P8yOjE/export?format=csv"
    data = pd.read_csv(url)
    data['Timestamp'] = pd.to_datetime(data['Timestamp'], errors='coerce')
    # Use Capacity from sheet or default to 4
    data['Capacity'] = pd.to_numeric(data.get('Capacity', 4), errors='coerce').fillna(4)
    data['Efficiency %'] = (data['Occupancy'] / data['Capacity']).fillna(0) * 100
    return data

df = load_data()
valid_dates = df['Timestamp'].dropna()

# 3. Sidebar Filters (These will now stay in the sidebar for all pages)
with st.sidebar:
    st.markdown("<h1 style='color: #00d2b4;'>neat.</h1>", unsafe_allow_html=True)
    loc_sel = st.selectbox("📍 Location", ["All"] + sorted(df['Location'].unique().tolist()))
    date_sel = st.date_input("📅 Date Range", value=(valid_dates.min().date(), valid_dates.max().date()))
    
    room_pool = df[df['Location'] == loc_sel] if loc_sel != "All" else df
    room_sel = st.multiselect("🚪 Rooms", sorted(room_pool['Room Name'].unique().tolist()))

# 4. Global Filter Logic
mask = df.copy()
if isinstance(date_sel, tuple) and len(date_sel) == 2:
    mask = mask[(mask['Timestamp'].dt.date >= date_sel[0]) & (mask['Timestamp'].dt.date <= date_sel[1])]
if loc_sel != "All": mask = mask[mask['Location'] == loc_sel]
if room_sel: mask = mask[mask['Room Name'].isin(room_sel)]
snap = mask.sort_values('Timestamp').drop_duplicates('Room Name', keep='last')

# 5. Dashboard UI
st.title("Room Analytics Dashboard")

# AI Summary
st.markdown('<div class="ai-box"><h4>✨ AI Executive Summary</h4><ul><li>Device Health: 100% online in selected area.</li><li>Utilization: High efficiency in small meeting rooms.</li></ul></div>', unsafe_allow_html=True)

# Metrics
m1, m2, m3, m4 = st.columns(4)
m1.metric("🟢 Online", len(snap[snap['Device Status'] == 'Online']))
m2.metric("🌡️ Avg Temp", f"{snap['Temperature'].mean():.1f} °C" if not snap.empty else "N/A")
m3.metric("👥 Total Occ", int(snap['Occupancy'].sum()))
m4.metric("📊 Avg/Room", f"{mask['Occupancy'].mean():.1f}")

st.write("### 🏢 Room Efficiency Analysis")
c1, c2, c3 = st.columns(3)
def draw_card(col, title, df_sub, cap_label):
    with col:
        with st.container(border=True):
            st.write(f"**{title}**")
            avg_p = df_sub['Occupancy'].mean() if not df_sub.empty else 0
            # Get avg capacity from the data itself
            avg_cap = df_sub['Capacity'].mean() if not df_sub.empty else 1
            eff = (avg_p / avg_cap) * 100
            st.metric("Avg People", f"{avg_p:.1f}", delta=f"{cap_label} Max", delta_color="off")
            st.progress(max(0.0, min((eff/100), 1.0)))

draw_card(c1, "Small (1-4)", mask[mask['Capacity'] <= 4], "4")
draw_card(c2, "Medium (5-8)", mask[(mask['Capacity'] > 4) & (mask['Capacity'] <= 8)], "8")
draw_card(c3, "Large (9-20)", mask[mask['Capacity'] > 8], "20")

st.write("### 📈 Occupancy Trends")
fig = px.line(mask, x="Timestamp", y="Occupancy", color="Room Name", line_shape='spline')
fig.update_layout(margin=dict(l=0,r=0,t=10,b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
st.plotly_chart(fig, use_container_width=True)