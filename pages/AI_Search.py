import streamlit as st
import pandas as pd
import time

# 1. Config & Theme
st.set_page_config(page_title="Neat | AI Actions", layout="wide", page_icon="🤖")
st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;} 
    footer {visibility: hidden;} 
    .stTextInput input {background-color: #1e2129; color: white; border: 1px solid #00d2b4;}
    .action-card {background-color: #1e2129; border-left: 5px solid #00d2b4; padding: 1.5rem; border-radius: 10px; margin-top: 1rem;}
    </style>
    """, unsafe_allow_html=True
)

# 2. Data Loading (Synced with main app)
@st.cache_data(ttl=600)
def load_data():
    url = "https://docs.google.com/spreadsheets/d/1bconB0u70BZv0aTblhhEA8_q56rlO6KAU1RG0P8yOjE/export?format=csv"
    data = pd.read_csv(url)
    data.columns = data.columns.str.strip()
    data['Timestamp'] = pd.to_datetime(data['Timestamp'], errors='coerce')
    
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
    
    return data

df = load_data()
valid_dates = df['Timestamp'].dropna()

# 3. Sidebar (Synced Memory)
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

# 4. Filter Logic
mask = df.copy()
if isinstance(date_sel, tuple) and len(date_sel) == 2:
    mask = mask[(mask['Timestamp'].dt.date >= date_sel[0]) & (mask['Timestamp'].dt.date <= date_sel[1])]
elif isinstance(date_sel, tuple) and len(date_sel) == 1:
    mask = mask[mask['Timestamp'].dt.date == date_sel[0]]
if loc_sel != "All": mask = mask[mask['Location'] == loc_sel]
if room_sel: mask = mask[mask['Room Name'].isin(room_sel)]
snap = mask.sort_values('Timestamp').drop_duplicates('Room Name', keep='last')

# 5. The AI Command Center UI
st.title("🤖 AI Insights & Actions")
st.write("Ask questions in plain English to query the fleet and execute automated API workflows.")

query = st.text_input("💬 Ask the Assistant:", placeholder="e.g., 'Are any devices offline?' or 'Find hot rooms'")

if query:
    query_lower = query.lower()
    
    # --- SCENARIO 1: IT Operations (Offline Devices) ---
    if "offline" in query_lower or "down" in query_lower or "broken" in query_lower:
        offline_df = snap[snap['Device Status'] == 'Offline']
        
        if not offline_df.empty:
            st.error(f"🚨 Found {len(offline_df)} offline device(s).")
            st.dataframe(offline_df[['Room Name', 'Location', 'Platform', 'Notes']], hide_index=True)
            
            st.markdown("<div class='action-card'><b>Suggested Action:</b> Trigger Neat REST API `PUT /api/v1/device/reboot` via Zero-Touch Management.</div>", unsafe_allow_html=True)
            if st.button("🔌 Execute Remote Reboot (API)"):
                with st.spinner("Authenticating with Neat API..."):
                    time.sleep(1)
                    st.success("API Command Sent! 1 Device rebooting.")
        else:
            st.success("✅ All devices are currently online in this selection.")
            
    # --- SCENARIO 2: Facilities (HVAC & Temp) ---
    elif "hot" in query_lower or "warm" in query_lower or "temperature" in query_lower:
        hot_df = snap[snap['Temperature'] > 24.0]
        
        if not hot_df.empty:
            st.warning(f"🌡️ Found {len(hot_df)} room(s) exceeding 24.0°C.")
            st.dataframe(hot_df[['Room Name', 'Temperature', 'Occupancy', 'Air Quality']], hide_index=True)
            
            st.markdown("<div class='action-card'><b>Suggested Action:</b> Fire Webhook to Building Management System (BMS) to increase AC flow.</div>", unsafe_allow_html=True)
            if st.button("❄️ Trigger HVAC Adjustment (Webhook)"):
                with st.spinner("Communicating with BMS..."):
                    time.sleep(1)
                    st.success("Webhook fired. HVAC flow increased for affected zones.")
        else:
            st.success("✅ All room temperatures are within normal ranges.")

    # --- SCENARIO 3: Real Estate (Ghost Meetings) ---
    elif "ghost" in query_lower or "empty" in query_lower or "unproductive" in query_lower:
        ghost_df = snap[(snap['Occupancy'] == 0) & (snap['Is_Work_Hour'] == True)]
        
        if not ghost_df.empty:
            st.info(f"👻 Found {len(ghost_df)} instance(s) of rooms empty during working hours.")
            st.dataframe(ghost_df[['Room Name', 'Timestamp', 'Temperature']], hide_index=True)
            
            st.markdown("<div class='action-card'><b>Suggested Action:</b> Talk to Microsoft Graph API to auto-delete the calendar events and free the rooms.</div>", unsafe_allow_html=True)
            if st.button("📅 Release Ghost Bookings (O365 API)"):
                with st.spinner("Syncing with Microsoft Exchange..."):
                    time.sleep(1.5)
                    st.success("Calendar events deleted. Rooms returned to the booking pool.")
        else:
            st.success("✅ No empty rooms detected during working hours for this selection.")
            
    # --- FALLBACK SCENARIO ---
    else:
        st.write("I am your Neat Fleet AI Assistant. Try asking me:")
        st.markdown("- *'Show me offline devices'*")
        st.markdown("- *'Find hot rooms'*")
        st.markdown("- *'Are there any ghost meetings?'*")
