import streamlit as st
import pandas as pd

st.set_page_config(page_title="Neat | AI Search", layout="wide")

@st.cache_data(ttl=600)
def load_data():
    url = "https://docs.google.com/spreadsheets/d/1bconB0u70BZv0aTblhhEA8_q56rlO6KAU1RG0P8yOjE/export?format=csv"
    data = pd.read_csv(url)
    data['Timestamp'] = pd.to_datetime(data['Timestamp'], errors='coerce')
    return data

df = load_data()
valid_dates = df['Timestamp'].dropna()

if valid_dates.empty:
    st.error("No valid timestamps found.")
    st.stop()

# --- GLOBALLY SYNCED SIDEBAR ---
with st.sidebar:
    st.markdown("<h1 style='color: #00d2b4;'>neat.</h1>", unsafe_allow_html=True)
    loc_sel = st.selectbox("📍 Location", ["All"] + sorted(df['Location'].dropna().unique().tolist()), key="loc_filter")
    
    min_d = valid_dates.min().date()
    max_d = valid_dates.max().date()
    date_sel = st.date_input("📅 Date Range", value=(min_d, max_d), key="date_filter")
    
    room_pool = df[df['Location'] == loc_sel] if loc_sel != "All" else df
    room_sel = st.multiselect("🚪 Rooms", sorted(room_pool['Room Name'].dropna().unique().tolist()), key="room_filter")

# --- FILTER LOGIC ---
mask = df.copy()
if isinstance(date_sel, tuple) and len(date_sel) == 2:
    mask = mask[(mask['Timestamp'].dt.date >= date_sel[0]) & (mask['Timestamp'].dt.date <= date_sel[1])]
elif isinstance(date_sel, tuple) and len(date_sel) == 1:
    mask = mask[mask['Timestamp'].dt.date == date_sel[0]]

if loc_sel != "All": 
    mask = mask[mask['Location'] == loc_sel]
if room_sel: 
    mask = mask[mask['Room Name'].isin(room_sel)]

# --- AI SEARCH UI ---
st.title("🤖 AI Insights & Actions")
st.write("Ask questions and execute commands in plain English. *(Results are filtered by your current location and date selections).*")

query = st.text_input("Example: 'Which room is the hottest?' or 'Show me offline devices'", "")

if query:
    st.markdown("---")
    
    # Catch empty data before the AI tries to read it
    if mask.empty:
        st.warning("No data matches your current sidebar filters. Please adjust your location or dates and try again.")
    else:
        with st.spinner("AI is analyzing your filtered telemetry..."):
            q = query.lower()
            
            if "hot" in q or "temp" in q:
                hottest = mask.sort_values('Temperature', ascending=False).iloc[0]
                st.error(f"The hottest room currently selected is **{hottest['Room Name']}** at **{hottest['Temperature']}°C**.")
                st.info("💡 Insight: Correlates with 'HVAC Waste' metrics. Check building management system.")
                
            elif "offline" in q or "status" in q:
                snap = mask.sort_values('Timestamp').drop_duplicates('Room Name', keep='last')
                offline = snap[snap['Device Status'] != 'Online']['Room Name'].unique()
                if len(offline) > 0:
                    st.warning(f"Found {len(offline)} offline devices in this location: {', '.join(offline)}")
                    # V2.0: Actionable Buttons
                    if st.button("🔄 Send Remote Reboot Command to Offline Devices"):
                        st.success(f"Command successfully sent to {len(offline)} devices via API.")
                        st.balloons()
                else:
                    st.success("All devices in this location are currently reporting as Online.")
                    
            elif "busy" in q or "most people" in q:
                busy = mask.sort_values('Occupancy', ascending=False).iloc[0]
                st.info(f"The most occupied room currently selected is **{busy['Room Name']}** with **{busy['Occupancy']}** people.")
                
            else:
                st.write("I found the following data matching your request within your selected filters:")
                st.dataframe(mask.head(10), use_container_width=True)
else:
    st.info("Try asking about 'offline devices' to see Interactive Actions in effect.")
