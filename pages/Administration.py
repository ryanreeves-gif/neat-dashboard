import streamlit as st
import pandas as pd
import plotly.express as px

# 1. Config & Corporate Theme
st.set_page_config(page_title="Neat | Admin", layout="wide", page_icon="🛠️")
st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    [data-testid="stSidebarNav"] {display: none !important;}
    .ai-box {background-color: #15171c; border: 1px solid #2a2d37; border-left: 5px solid #00d2b4; padding: 1.5rem; border-radius: 8px; margin-bottom: 2rem;}
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
    
    platform_mapping = {'msteams': 'Microsoft Teams', 'zoom': 'Zoom', 'google_meet': 'Google Meet', 'apphub': 'Neat App Hub', 'usb': 'BYOD (USB Mode)', 'avos': 'App Hub Partner', 'none': 'Unprovisioned'}
    data['Platform'] = data['Platform'].replace(platform_mapping)
    
    # Ensure numeric columns are safe to evaluate
    data['VOC'] = pd.to_numeric(data.get('VOC', 0), errors='coerce').fillna(0)
    data['Temperature'] = pd.to_numeric(data.get('Temperature', 0), errors='coerce').fillna(0)
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
    st.markdown("<h1 style='color: #00d2b4; font-size: 3.5rem; margin-bottom: 0; padding-bottom: 0; line-height: 1;'>neat.</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #888; font-size: 0.9rem; font-weight: 600; letter-spacing: 1px; margin-top: 0; margin-bottom: 30px;'>ENTERPRISE OPERATIONS</p>", unsafe_allow_html=True)
    
    st.markdown("<p style='color: #00d2b4; font-size: 0.8rem; font-weight: bold; margin-bottom: 5px;'>MENU</p>", unsafe_allow_html=True)
    st.page_link("app.py", label="Analytics", icon="📊")
    st.page_link("pages/Administration.py", label="Admin", icon="🛠️")
    st.page_link("pages/AI_Search.py", label="AI Search", icon="🤖")
    
    st.markdown("---")
    st.markdown("<p style='color: #00d2b4; font-size: 0.8rem; font-weight: bold; margin-bottom: 5px;'>GLOBAL FILTERS</p>", unsafe_allow_html=True)
    loc_opts = ["All"] + sorted(df['Location'].dropna().unique().tolist())
    loc_sel = st.selectbox("📍 Location", loc_opts, index=loc_opts.index(st.session_state['saved_loc']), key="loc_filter", on_change=save_selections)
    date_sel = st.date_input("📅 Date Range", value=st.session_state['saved_dates'], key="date_filter", on_change=save_selections)
    room_opts = sorted(df['Room Name'].dropna().unique().tolist())
    room_sel = st.multiselect("🚪 Rooms", room_opts, default=st.session_state['saved_rooms'], key="room_filter", on_change=save_selections)
    
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Refresh Telemetry", use_container_width=True, type="primary"):
        st.cache_data.clear()
        st.rerun()

# 4. Filter Logic
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

# Get the absolute latest snapshot of the fleet
snap = mask.sort_values('Timestamp').drop_duplicates('Room Name', keep='last').copy()

# ==========================================
# 5. HEATMAP LOGIC WITH SMART ISSUE LISTS
# ==========================================
st.title("🛠️ IT Operations & Administration")

def generate_issue_list(row):
    """Diagnoses the room and returns an HTML formatted bullet list of issues."""
    issues = []
    
    if row['Device Status'] == 'Offline':
        issues.append("🔌 Device Offline")
    if pd.to_numeric(row.get('VOC', 0), errors='coerce') > 1000:
        issues.append("⚠️ High VOC (>1000)")
    if pd.to_numeric(row.get('Temperature', 0), errors='coerce') > 24.0:
        issues.append("🌡️ High Temp (>24°C)")
        
    if not issues:
        return "✅ Optimal"
    
    # Join with HTML line breaks for Plotly
    return "<br>".join(issues)

# Apply diagnosis to generate the list
snap['Issue_Details'] = snap.apply(generate_issue_list, axis=1)
snap['Root'] = 'Global Fleet'
snap['Size'] = 1  # Equal size boxes

# Assign exact colors based on the diagnosis
def map_color(row):
    if 'Offline' in row['Issue_Details']:
        return 'Critical'
    elif '⚠️' in row['Issue_Details'] or '🌡️' in row['Issue_Details']:
        return 'Warning'
    else:
        return 'Healthy'
        
snap['Status_Color'] = snap.apply(map_color, axis=1)

color_map = {
    'Healthy': '#00d2b4',     # Neat Green
    'Warning': '#ffb000',     # Yellow/Orange
    'Critical': '#ff4b4b',    # Red
}

st.write("### 🌍 Global Fleet Health Heatmap")
st.markdown("Current status of all devices. **Issues are listed directly inside the affected rooms.**")

if not snap.empty:
    fig = px.treemap(
        snap,
        path=['Root', 'Location', 'Room Name'],
        values='Size',
        color='Status_Color',
        color_discrete_map=color_map,
        custom_data=['Issue_Details']  # Pass the bullet list to Plotly
    )
    
    # Format the text: Room Name in Bold, double line break, then the issue list
    fig.update_traces(
        texttemplate="<b>%{label}</b><br><br>%{customdata[0]}",
        textposition="middle center",
        textfont=dict(size=14, color="white"),
        hovertemplate="<b>%{label}</b><br>%{customdata[0]}<extra></extra>"
    )

    fig.update_layout(
        margin=dict(t=20, l=10, r=10, b=10),
        height=650,  # Increased height to fit lists comfortably
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)"
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No data available to display heatmap.")

# ==========================================
# 6. FLEET INVENTORY & PLATFORMS
# ==========================================
st.markdown("---")
st.write("### 🏢 Fleet Configuration & App Hub Platforms")

col1, col2 = st.columns([1, 2])

with col1:
    if not snap.empty:
        fig_pie = px.pie(
            snap, 
            names='Platform', 
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig_pie.update_layout(
            margin=dict(t=20, b=20, l=20, r=20),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
        )
        st.plotly_chart(fig_pie, use_container_width=True)

with col2:
    st.dataframe(
        snap[['Room Name', 'Location', 'Device Status', 'Platform', 'Software Version']].reset_index(drop=True),
        use_container_width=True,
        hide_index=True
    )
