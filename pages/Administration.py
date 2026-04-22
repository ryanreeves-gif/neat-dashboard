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

# 2. Data Loading
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

# 3. Sidebar
with st.sidebar:
    st.markdown("<h1 style='color: #00d2b4;'>neat.</h1>", unsafe_allow_html=True)
    loc_opts = ["All"] + sorted(df['Location'].dropna().unique().tolist())
    loc_sel = st.selectbox("📍 Location", loc_opts, index=0)
    if st.button("🔄 Refresh Telemetry"):
        st.cache_data.clear()
        st.rerun()

# 4. Logic
mask = df[df['Location'] == loc_sel] if loc_sel != "All" else df
# Get the absolute latest status for every room
snap = mask.sort_values('Timestamp').drop_duplicates('Room Name', keep='last').copy()

# 5. UI
st.title("🛠️ IT Administration & Operations")

offline_count = len(snap[snap['Device Status'] == 'Offline'])
app_hub_count = len(snap[snap['Platform'] == 'App Hub Partner'])

st.markdown(f"""
    <div class="ai-box">
        <h4 style="margin-top:0;">✨ AI Operations Summary</h4>
        <ul>
            <li><b>Fleet Status:</b> {offline_count} devices require immediate attention. Availability is the top priority for this selection.</li>
            <li><b>Platform Strategy:</b> <b>{app_hub_count}</b> devices are running 'App Hub Partner' software, supporting specialized workflows.</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

# 6. Fleet Health Heatmap (FIXED SIZING)
st.write("### 🌍 Global Fleet Health Heatmap")
st.write("Current status of all devices in the selected location. Click a square to investigate.")

# Map Risk Levels to Numbers for the Heatmap Colors
status_map = {'Healthy': 3, 'Medium': 2, 'High': 1, 'Unknown': 0}

# Fix: If offline, force High risk. Else use the map.
snap['Health_Score'] = snap.apply(lambda x: 1 if x['Device Status'] == 'Offline' else status_map.get(x['Risk Level'], 0), axis=1)

# Fix: Add a dummy column so every room is exactly the same size on the grid
snap['Grid_Size'] = 1 

fig_health = px.treemap(
    snap, 
    path=['Location', 'Room Name'], 
    values='Grid_Size', # <--- The Bug Fix!
    color='Health_Score',
    color_continuous_scale=['#ff4b4b', '#ffa500', '#00d2b4'], # Red, Orange, Green
    custom_data=['Device Status', 'Platform', 'Notes']
)

fig_health.update_traces(
    hovertemplate="<b>%{label}</b><br>Status: %{customdata[0]}<br>Platform: %{customdata[1]}<br>Issue: %{customdata[2]}"
)
fig_health.update_layout(margin=dict(t=0, l=0, r=0, b=0), coloraxis_showscale=False)
st.plotly_chart(fig_health, use_container_width=True)

# 7. Licensing ROI
st.write("---")
c1, c2 = st.columns([1, 1])

with c1:
    st.write("### 💰 Licensing Mix")
    platform_counts = snap.groupby('Platform').size().reset_index(name='Count')
    fig_pie = px.pie(platform_counts, values='Count', names='Platform', hole=0.5, color_discrete_sequence=px.colors.qualitative.Pastel)
    st.plotly_chart(fig_pie, use_container_width=True)

with c2:
    st.write("### 📋 Quick Issue Log")
    issues = snap[snap['Device Status'] == 'Offline'][['Room Name', 'Notes', 'Platform']]
    if not issues.empty:
        st.dataframe(issues, hide_index=True, use_container_width=True)
    else:
        st.success("No active critical issues detected.")

st.write("### 📂 Full Fleet Inventory")
st.dataframe(snap[['Room Name', 'Location', 'Device Status', 'Platform', 'Software Version', 'Notes']], hide_index=True, use_container_width=True)
