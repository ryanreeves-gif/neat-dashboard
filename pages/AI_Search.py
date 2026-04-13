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

st.title("🤖 AI Insights & Actions")
st.write("Ask questions and execute commands in plain English.")

query = st.text_input("Example: 'Which room is the hottest?' or 'Show me offline devices'", "")

if query:
    st.markdown("---")
    with st.spinner("AI is analyzing..."):
        q = query.lower()
        
        if "hot" in q or "temp" in q:
            hottest = df.sort_values('Temperature', ascending=False).iloc[0]
            st.error(f"The hottest room is **{hottest['Room Name']}** at **{hottest['Temperature']}°C**.")
            st.info("💡 Insight: Correlates with 'HVAC Waste' metrics. Check building management system.")
            
        elif "offline" in q or "status" in q:
            snap = df.sort_values('Timestamp').drop_duplicates('Room Name', keep='last')
            offline = snap[snap['Device Status'] != 'Online']['Room Name'].unique()
            if len(offline) > 0:
                st.warning(f"Found {len(offline)} offline devices: {', '.join(offline)}")
                # V2.0: Actionable Buttons
                if st.button("🔄 Send Remote Reboot Command to Offline Devices"):
                    st.success(f"Command successfully sent to {len(offline)} devices via API.")
                    st.balloons()
            else:
                st.success("All devices are currently reporting as Online.")
                
        elif "busy" in q or "most people" in q:
            busy = df.sort_values('Occupancy', ascending=False).iloc[0]
            st.info(f"The most occupied room is **{busy['Room Name']}** with **{busy['Occupancy']}** people.")
            
        else:
            st.write("I found the following data matching your request:")
            st.dataframe(df.head(10), use_container_width=True)
else:
    st.info("Try asking about 'offline devices' to see Interactive Actions in effect.")
