import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Neat | Administration", layout="wide")

@st.cache_data(ttl=600)
def load_data():
    url = "https://docs.google.com/spreadsheets/d/1bconB0u70BZv0aTblhhEA8_q56rlO6KAU1RG0P8yOjE/export?format=csv"
    data = pd.read_csv(url)
    data['Timestamp'] = pd.to_datetime(data['Timestamp'], errors='coerce')
    data['Offline Minutes'] = pd.to_numeric(data.get('Offline Minutes', 0), errors='coerce').fillna(0)
    data['Occupancy'] = pd.to_numeric(data.get('Occupancy', 0), errors='coerce').fillna(0)
    data['Hour'] = data['Timestamp'].dt.hour
    data['Day'] = data['Timestamp'].dt.strftime('%A')
    return data

df = load_data()
valid_dates = df['Timestamp'].dropna()

# --- GLOBALLY SYNCED SIDEBAR (With Permanent Memory) ---
# 1. Initialize permanent memory vault
if 'saved_loc' not in st.session_state: 
    st.session_state['saved_loc'] = "All"
if 'saved_dates' not in st.session_state: 
    st.session_state['saved_dates'] = (valid_dates.min().date(), valid_dates.max().date())
if 'saved_rooms' not in st.session_state: 
    st.session_state['saved_rooms'] = []

# 2. Update function to save changes to the vault instantly
def save_selections():
    st.session_state['saved_loc'] = st.session_state['loc_filter']
    st.session_state['saved_dates'] = st.session_state['date_filter']
    st.session_state['saved_rooms'] = st.session_state['room_filter']

with st.sidebar:
    st.markdown("<h1 style='color: #00d2b4;'>neat.</h1>", unsafe_allow_html=True)
    
    # Location
    loc_opts = ["All"] + sorted(df['Location'].dropna().unique().tolist())
    loc_idx = loc_opts.index(st.session_state['saved_loc']) if st.session_state['saved_loc'] in loc_opts else 0
    loc_sel = st.selectbox("📍 Location", loc_opts, index=loc_idx, key="loc_filter", on_change=save_selections)
    
    # Dates
    date_sel = st.date_input("📅 Date Range", value=st.session_state['saved_dates'], key="date_filter", on_change=save_selections)
    
    # Rooms (Smart filter that drops invalid rooms if location changes)
    room_pool = df[df['Location'] == loc_sel] if loc_sel != "All" else df
    room_opts = sorted(room_pool['Room Name'].dropna().unique().tolist())
    valid_rooms = [r for r in st.session_state['saved_rooms'] if r in room_opts]
    room_sel = st.multiselect("🚪 Rooms", room_opts, default=valid_rooms, key="room_filter", on_change=save_selections)
    st.markdown("---")
    if st.button("🔄 Refresh Telemetry", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
# --- END SIDEBAR ---

mask = df.copy()
if isinstance(date_sel, tuple) and len(date_sel) == 2:
    mask = mask[(mask['Timestamp'].dt.date >= date_sel[0]) & (mask['Timestamp'].dt.date <= date_sel[1])]
elif isinstance(date_sel, tuple) and len(date_sel) == 1:
    mask = mask[mask['Timestamp'].dt.date == date_sel[0]]

if loc_sel != "All": mask = mask[mask['Location'] == loc_sel]
if room_sel: mask = mask[mask['Room Name'].isin(room_sel)]

snap = mask.sort_values('Timestamp').drop_duplicates('Room Name', keep='last')

# --- ADMIN UI ---
st.title("🛠️ IT Administration & Operations")

st.markdown('''<div style="background-color: #1e2129; border-left: 5px solid #00d2b4; padding: 1.5rem; border-radius: 10px; margin-bottom: 2rem;">
<h4 style="margin-top:0; color:#00d2b4;">✨ AI Operations Summary</h4>
<ul style="color: white;">
<li><b>Uptime SLA:</b> Tracking active offline minutes to protect availability targets.</li>
<li><b>Proactive IT:</b> Monitoring risk levels to dispatch technicians before executive meetings.</li>
<li><b>Licensing:</b> Correlating platform usage with occupancy to eliminate redundant SaaS costs.</li>
</ul></div>''', unsafe_allow_html=True)

# 1. Pre-Failure Watchlist
st.write("### 🚨 Pre-Failure Watchlist")
watchlist = snap[(snap['Device Status'] == 'Online') & (snap['Risk Level'].isin(['Medium', 'High', 'Critical']))]
if not watchlist.empty:
    st.warning(f"Found {len(watchlist)} online devices reporting degraded risk levels in this location.")
    st.dataframe(watchlist[['Room Name', 'Location', 'Platform', 'Risk Level', 'Notes']], use_container_width=True, hide_index=True)
else:
    st.success("No devices currently reporting elevated risk levels. Systems normal.")

# 2. SLA & Licensing
col_a, col_b = st.columns(2)
with col_a:
    with st.container(border=True):
        st.write("### ⏱️ Current Outages (SLA)")
        total_offline = snap['Offline Minutes'].sum()
        st.metric("Total Active Offline Minutes", f"{total_offline:,.0f} mins", delta="- Impacts 99.9% Uptime SLA", delta_color="inverse")
        offline_df = snap[snap['Offline Minutes'] > 0][['Room Name', 'Location', 'Offline Minutes']].sort_values('Offline Minutes', ascending=False)
        if not offline_df.empty:
            st.dataframe(offline_df, hide_index=True, use_container_width=True)

with col_b:
    with st.container(border=True):
        st.write("### 💰 Platform Licensing ROI")
        st.write("Total occupied hours by platform for selected location.")
        mask['Date'] = mask['Timestamp'].dt.date
        roi_df = mask[mask['Occupancy'] > 0].groupby(['Platform', 'Date', 'Hour', 'Room Name']).size().reset_index()
        roi_summary = roi_df.groupby('Platform').size().reset_index(name='Occupied Hours')
        
        fig_roi = px.bar(roi_summary, x='Platform', y='Occupied Hours', color='Platform')
        fig_roi.update_layout(margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", showlegend=False)
        st.plotly_chart(fig_roi, use_container_width=True)

# 3. Firmware
st.write("### 🖥️ Firmware Compliance")
baseline = "NFA2.20260312.1312"
fw_df = snap.groupby(['Platform', 'Software Version']).size().reset_index(name='Count')
fw_df['Status'] = fw_df['Software Version'].apply(lambda x: "✅ Compliant" if x == baseline else "⚠️ Update Required")
st.dataframe(fw_df, use_container_width=True, hide_index=True)

st.write("### 📅 Maintenance Window Heatmap")
d_ord = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
if not mask.empty:
    pivot = mask.pivot_table(index='Day', columns='Hour', values='Occupancy', aggfunc='mean').reindex(d_ord)
    fig_h = px.imshow(pivot, aspect="auto", color_continuous_scale="Tealgrn")
    fig_h.update_layout(margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig_h, use_container_width=True)
else:
    st.info("No data available for the selected filters.")
