import streamlit as st
import pandas as pd
import plotly.express as px

# 1. Config
st.set_page_config(page_title="Neat | Admin", layout="wide", page_icon="🛠️")
st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    .ai-box {background-color: #1e2129; border-left: 5px solid #00d2b4; padding: 1.5rem; border-radius: 10px; margin-bottom: 2rem;}
    .ai-box h4, .ai-box li, .ai-box p { color: white !important; }
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
    
    # Professional Naming
    platform_mapping = {
        'msteams': 'Microsoft Teams', 'zoom': 'Zoom', 'google_meet': 'Google Meet',
        'apphub': 'Neat App Hub', 'usb': 'BYOD (USB Mode)', 'avos': 'App Hub Partner', 'none': 'Unprovisioned'
    }
    data['Platform'] = data['Platform'].replace(platform_mapping)
    return data

df = load_data()

# 3. Sidebar (Synced Memory)
with st.sidebar:
    st.markdown("<h1 style='color: #00d2b4;'>neat.</h1>", unsafe_allow_html=True)
    loc_opts = ["All"] + sorted(df['Location'].dropna().unique().tolist())
    loc_sel = st.selectbox("📍 Location", loc_opts, index=0)
    if st.button("🔄 Refresh Telemetry"):
        st.cache_data.clear()
        st.rerun()

# 4. Filters & Logic
mask = df[df['Location'] == loc_sel] if loc_sel != "All" else df
snap = mask.sort_values('Timestamp').drop_duplicates('Room Name', keep='last')

# 5. UI - Dynamic Admin AI Summary
st.title("🛠️ IT Administration & Operations")

offline_count = len(snap[snap['Device Status'] == 'Offline'])
app_hub_count = len(snap[snap['Platform'] == 'App Hub Partner'])

st.markdown(f"""
    <div class="ai-box">
        <h4 style="margin-top:0;">✨ AI Operations Summary</h4>
        <ul>
            <li><b>Uptime SLA:</b> {offline_count} devices are currently offline. Critical availability target is 99.9%.</li>
            <li><b>Licensing ROI:</b> Found <b>{app_hub_count}</b> 'App Hub Partner' deployments (Booking/Reception). Verify specialized license allocation.</li>
            <li><b>Software Status:</b> Fleet versioning is being tracked against the latest Neat NFK stable branch.</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

# 6. Admin Visuals
col1, col2 = st.columns(2)

with col1:
    st.write("### 💰 Platform Licensing Mix")
    platform_counts = snap.groupby('Platform').size().reset_index(name='Device Count')
    fig_p = px.pie(platform_counts, values='Device Count', names='Platform', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
    st.plotly_chart(fig_p, use_container_width=True)

with col2:
    st.write("### 📉 Offline Minutes (Active Risk)")
    mask['Offline Minutes'] = pd.to_numeric(mask.get('Offline Minutes', 0), errors='coerce').fillna(0)
    fig_off = px.bar(mask[mask['Device Status'] == 'Offline'], x='Timestamp', y='Offline Minutes', color='Room Name')
    st.plotly_chart(fig_off, use_container_width=True)

st.write("### 🚪 Room Snapshot Table")
st.dataframe(snap[['Room Name', 'Location', 'Device Status', 'Platform', 'Software Version', 'Notes']], hide_index=True, use_container_width=True)
