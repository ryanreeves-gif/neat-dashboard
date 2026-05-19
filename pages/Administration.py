import streamlit as st
import pandas as pd
import plotly.express as px
import time

# 1. Config & Corporate Theme
st.set_page_config(page_title="Neat | Admin", layout="wide", page_icon="🛠️")
st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    [data-testid="stSidebarNav"] {display: none !important;}
    
    /* Sleek Corporate AI Box */
    .ai-box {background-color: #15171c; border: 1px solid #2a2d37; border-left: 5px solid #00d2b4; padding: 1.5rem; border-radius: 8px; margin-bottom: 2rem;}
    .ai-box h4, .ai-box li, .ai-box p { color: white !important; }
    
    /* Spatial Digital Twin Grid Layout */
    .floorplan-node {
        background-color: #15171c;
        border: 1px solid #2a2d37;
        border-radius: 6px;
        padding: 1rem;
        text-align: center;
        margin-bottom: 10px;
    }
    
    /* Technical Override Logger */
    .override-log {
        background-color: #1a1c23;
        border: 1px dashed #555;
        padding: 1rem;
        border-radius: 5px;
        font-family: monospace;
        font-size: 0.85rem;
        color: #a0aabf;
    }
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

snap = mask.sort_values('Timestamp').drop_duplicates('Room Name', keep='last').copy()

# Heatmap helper logic
def generate_issue_list(row):
    issues = []
    if row['Device Status'] == 'Offline': issues.append("🔌 Device Offline")
    if pd.to_numeric(row.get('VOC', 0), errors='coerce') > 1000: issues.append("⚠️ High VOC (>1000)")
    if pd.to_numeric(row.get('Temperature', 0), errors='coerce') > 24.0: issues.append("🌡️ High Temp (>24°C)")
    return "<br>".join(issues) if issues else "✅ Optimal"

snap['Issue_Details'] = snap.apply(generate_issue_list, axis=1)
snap['Root'] = 'Global Fleet'
snap['Size'] = 1  

def map_color(row):
    if 'Offline' in row['Issue_Details']: return 'Critical'
    elif '⚠️' in row['Issue_Details'] or '🌡️' in row['Issue_Details']: return 'Warning'
    return 'Healthy'
        
snap['Status_Color'] = snap.apply(map_color, axis=1)

color_map = {'Healthy': '#00d2b4', 'Warning': '#ffb000', 'Critical': '#ff4b4b'}

# ==========================================
# 5. ENTERPRISE BMS WORKSPACE TABS
# ==========================================
st.title("🛠️ Building Management & Operations System")

# Create tabs for the 3 new top-tier BMS elements
view_tab, twin_tab, alarm_tab, override_tab = st.tabs([
    "🌍 Fleet Heatmap", 
    "🗺️ Spatial Digital Twin (Floorplans)", 
    "🚨 Active Alarm Console", 
    "🎛️ BMS Manual Overrides"
])

# --- TAB 1: LOGICAL FLEET HEATMAP ---
with view_tab:
    st.write("### real-time Fleet Topology")
    if not snap.empty:
        fig = px.treemap(
            snap, path=['Root', 'Location', 'Room Name'], values='Size',
            color='Status_Color', color_discrete_map=color_map, custom_data=['Issue_Details']
        )
        fig.update_traces(
            texttemplate="<b>%{label}</b><br><br>%{customdata[0]}", textposition="middle center",
            textfont=dict(size=14, color="white"), hovertemplate="<b>%{label}</b><br>%{customdata[0]}<extra></extra>"
        )
        fig.update_layout(margin=dict(t=20, l=10, r=10, b=10), height=500, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No system assets found.")

# --- TAB 2: SPATIAL DIGITAL TWIN ---
with twin_tab:
    st.write("### 🏢 Physical Floor Plan Mapping (CAD Layer Mock)")
    st.markdown("Maps edge telemetry onto structured physical building wings instead of sorting tables.")
    
    if not snap.empty:
        # Group rooms into pseudo structural zones/wings
        wings = ["North Wing (Zone A)", "South Wing (Zone B)", "Executive Suite (Zone C)"]
        snap['Wing'] = [wings[i % len(wings)] for i in range(len(snap))]
        
        for wing in sorted(snap['Wing'].unique()):
            st.write(f"#### 📍 {wing}")
            wing_rooms = snap[snap['Wing'] == wing]
            cols = st.columns(4)
            for idx, (_, room) in enumerate(wing_rooms.iterrows()):
                col = cols[idx % 4]
                border_color = color_map[room['Status_Color']]
                with col:
                    st.markdown(f"""
                    <div class="floorplan-node" style="border-top: 4px solid {border_color};">
                        <span style="font-weight:bold; font-size:1.1rem; color:white;">{room['Room Name']}</span><br>
                        <span style="color:#888; font-size:0.85rem;">{room['Location']}</span><br><br>
                        <span style="font-size:0.9rem;">🌡️ {room['Temperature']:.1f}°C &nbsp;|&nbsp; 🌬️ {room['VOC']:.0f} VOC</span>
                    </div>
                    """, unsafe_allow_html=True)
    else:
        st.info("No spatial data mapped.")

# --- TAB 3: ACTIVE ALARM & TICKETING CONSOLE ---
with alarm_tab:
    st.write("### 🚨 Active Operational Breaches & ServiceNow Link")
    st.markdown("Automated ticket tracking lifecycle tied directly to system exceptions.")
    
    # Filter only rooms that have actual issues
    breached_rooms = snap[snap['Status_Color'] != 'Healthy'].copy()
    
    if not breached_rooms.empty:
        # Mocking active enterprise ticket parameters
        breached_rooms['Ticket ID'] = [f"INC-2026-{1042 + idx}" for idx in range(len(breached_rooms))]
        breached_rooms['Lifecycle'] = ["New" if status == 'Critical' else "Acknowledged" for status in breached_rooms['Status_Color']]
        breached_rooms['Breach Details'] = breached_rooms['Issue_Details'].str.replace("<br>", " | ")
        
        # Nicely presented table dashboard
        st.dataframe(
            breached_rooms[['Ticket ID', 'Room Name', 'Location', 'Breach Details', 'Lifecycle']],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.success("🎉 Zero Active Alarms. All environmental parameters operating within optimal tolerances.")

# --- TAB 4: DIRECT MANUAL OVERRIDES ---
with override_tab:
    st.write("### 🎛️ Direct Manual Edge Controller Overrides")
    st.markdown("Manually bypass the automated system logic and write instructions directly back to the room edge actuators.")
    
    if not snap.empty:
        c1, c2 = st.columns([1, 2])
        with c1:
            target_room = st.selectbox("🎯 Target Room Asset", sorted(snap['Room Name'].unique()))
            selected_room_data = snap[snap['Room Name'] == target_room].iloc[0]
            
            st.write(f"**Current Edge State:** `{selected_room_data['Status_Color']}`")
            st.write(f"🌡️ Temp: {selected_room_data['Temperature']:.1f}°C | 🌬️ VOC: {selected_room_data['VOC']:.0f}")
            
            st.write("---")
            override_action = st.radio("Execute Override Command", [
                "🔄 Release to Full System Autonomy",
                "💨 Force Max Air Purge Mode (High Air Flow)",
                "❄️ Lock VAV Box Setpoint Manual Override",
                "🔌 Force Remote Edge Device Cycle"
            ])
            
            if override_action == "❄️ Lock VAV Box Setpoint Manual Override":
                lock_temp = st.slider("Force Temporary Locked Setpoint", 16.0, 26.0, 21.0, 0.5, format="%f°C")
            
            st.write("<br>", unsafe_allow_html=True)
            if st.button("⚡ Broadcast Manual Edge Override Command", type="primary", use_container_width=True):
                with c2:
                    with st.spinner(f"Writing priority override frames to {target_room}..."):
                        time.sleep(1.2)
                        st.success(f"✅ Priority Write Confirmed. System logic bypassed for {target_room}.")
                        
                        st.markdown(f"""
                        <div class="override-log">
                            <b>[BACnet OUTBOUND GATEWAY LOG] PRIORITIZED POINT OVERRIDE EXECUTED:</b><br><br>
                            - <b>Target Object:</b> Room_Asset_{target_room.replace(' ', '_')}_HVAC_Control<br>
                            - <b>Command Origin:</b> Neat Admin Console Override Module<br>
                            - <b>Action Context:</b> Bypassed current automated optimization baseline.<br>
                            - <b>API Payload dispatched:</b> <code>{{"action": "force_override", "origin": "admin", "priority_level": 8}}</code><br>
                            - <b>Status:</b> Object locked at high-priority tier. Acknowledged by Niagara Server controller frame.
                        </div>
                        """, unsafe_allow_html=True)
    else:
        st.info("No active devices available for edge command targeting.")

# ==========================================
# 6. FLEET INVENTORY & PLATFORMS
# ==========================================
st.markdown("---")
st.write("### 🏢 Fleet Configuration & App Hub Platforms")

col1, col2 = st.columns([1, 2])

with col1:
    if not snap.empty:
        fig_pie = px.pie(
            snap, names='Platform', hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig_pie.update_layout(
            margin=dict(t=20, b=20, l=20, r=20), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
        )
        st.plotly_chart(fig_pie, use_container_width=True)

with col2:
    st.dataframe(
        snap[['Room Name', 'Location', 'Device Status', 'Platform', 'Software Version']].reset_index(drop=True),
        use_container_width=True, hide_index=True
    )
