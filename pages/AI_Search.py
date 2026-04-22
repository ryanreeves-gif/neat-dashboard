import streamlit as st
import pandas as pd
import time

# 1. Config
st.set_page_config(page_title="Neat | AI Actions", layout="wide", page_icon="🤖")
st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    .action-card {background-color: #1e2129; border-left: 5px solid #00d2b4; padding: 1.5rem; border-radius: 10px; margin-top: 1rem; color: white;}
    .stTextInput input {background-color: #1e2129; color: white; border: 1px solid #00d2b4;}
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
    platform_mapping = {
        'msteams': 'Microsoft Teams', 'zoom': 'Zoom', 'avos': 'App Hub Partner', 'none': 'Unprovisioned'
    }
    data['Platform'] = data['Platform'].replace(platform_mapping)
    return data

df = load_data()
snap = df.sort_values('Timestamp').drop_duplicates('Room Name', keep='last')

# 3. UI
st.title("🤖 AI Insights & Actions")
st.write("Ask questions in plain English to trigger automated workflows and API simulations.")

query = st.text_input("💬 Ask the Assistant:", placeholder="e.g., 'Reboot offline devices' or 'Check VOC health'")

if query:
    q = query.lower()
    
    # Scenario: Offline Devices
    if "offline" in q or "down" in q or "reboot" in q:
        offline = snap[snap['Device Status'] == 'Offline']
        if not offline.empty:
            st.error(f"🚨 Found {len(offline)} offline device(s).")
            st.dataframe(offline[['Room Name', 'Location', 'Notes']], hide_index=True)
            st.markdown("<div class='action-card'><b>AI Recommendation:</b> Execute remote reboot via <b>Neat Pulse REST API</b>.</div>", unsafe_allow_html=True)
            if st.button("🔌 Execute Remote Reboot (Simulated API)"):
                with st.spinner("Authenticating with Neat API..."):
                    time.sleep(1)
                    st.success("API Command Sent: Reboot sequence initiated.")
        else:
            st.success("✅ All systems report online.")

    # Scenario: App Hub/AVOS
    elif "app hub" in q or "partner" in q or "avos" in q:
        partners = snap[snap['Platform'] == 'App Hub Partner']
        st.info(f"Found {len(partners)} specialized App Hub Partner devices.")
        st.dataframe(partners[['Room Name', 'Location', 'Platform']], hide_index=True)
        st.markdown("<div class='action-card'><b>Proactive Suggestion:</b> Update these devices to the latest NFK firmware for enhanced App Hub performance.</div>", unsafe_allow_html=True)

    # Fallback
    else:
        st.write("I can help you manage your fleet. Try asking:")
        st.markdown("- *'Show me offline rooms'*")
        st.markdown("- *'Which rooms are running App Hub Partner software?'*")
        st.markdown("- *'Are there any hot rooms?'*")
