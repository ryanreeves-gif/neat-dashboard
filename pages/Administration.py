import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import timedelta

st.set_page_config(page_title="Neat | Administration", layout="wide")

@st.cache_data(ttl=600)
def load_data():
    url = "https://docs.google.com/spreadsheets/d/1bconB0u70BZv0aTblhhEA8_q56rlO6KAU1RG0P8yOjE/export?format=csv"
    data = pd.read_csv(url)
    data['Timestamp'] = pd.to_datetime(data['Timestamp'], errors='coerce')
    data['Capacity'] = pd.to_numeric(data.get('Capacity', 4), errors='coerce').fillna(4)
    data['Hour'] = data['Timestamp'].dt.hour
    data['Day'] = data['Timestamp'].dt.strftime('%A')
    return data

df = load_data()
st.title("🛠️ IT Administration Hub")

snap = df.sort_values('Timestamp').drop_duplicates('Room Name', keep='last')
anoms = df[(df['Temperature'] > 25) | (df['Occupancy'] > df['Capacity'])].copy()

st.markdown(f'''<div style="background-color: #1e2129; border-left: 5px solid #00d2b4; padding: 1.5rem; border-radius: 10px; margin-bottom: 2rem;">
<h4 style="margin-top:0; color:#00d2b4;">✨ AI Admin Summary</h4>
<ul style="color: white;"><li><b>Fleet Health:</b> {len(snap[snap["Device Status"]!="Online"])} devices offline.</li>
<li><b>Action Required:</b> {len(anoms)} threshold breaches. Please review the Triage Queue.</li></ul></div>''', unsafe_allow_html=True)

# V2.0: Alert Triage Queue
with st.container(border=True):
    st.subheader("🚨 Active Alert Triage Queue")
    if not anoms.empty:
        anoms['Issue'] = "Over Capacity"
        anoms.loc[anoms['Temperature'] > 25, 'Issue'] = "HVAC / Overheat"
        st.dataframe(anoms[['Timestamp', 'Room Name', 'Issue', 'Temperature', 'Occupancy']].head(5), use_container_width=True, hide_index=True)
    else:
        st.success("No active alerts. Systems normal.")

col_a, col_b = st.columns([2, 1])
with col_a:
    with st.container(border=True):
        st.subheader("🖥️ Firmware Compliance")
        if not snap.empty:
            fw_df = snap.groupby(['Platform', 'Software Version']).size().reset_index(name='Count')
            # V2.0: Define a baseline and flag non-compliant devices
            baseline = "NFA2.20260312.1312"
            fw_df['Status'] = fw_df['Software Version'].apply(lambda x: "✅ Compliant" if x == baseline else "⚠️ Update Required")
            st.dataframe(fw_df, use_container_width=True, hide_index=True)

with col_b:
    with st.container(border=True):
        st.subheader("📥 Data Export")
        st.download_button("Download Audit CSV", df.to_csv(index=False).encode('utf-8'), "neat_audit.csv", use_container_width=True)

st.write("### 📅 Maintenance Window Heatmap")
d_ord = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
pivot = df.pivot_table(index='Day', columns='Hour', values='Occupancy', aggfunc='mean').reindex(d_ord)
fig_h = px.imshow(pivot, aspect="auto", color_continuous_scale="Tealgrn")
fig_h.update_layout(margin=dict(l=0, r=0, t=10, b=0))
st.plotly_chart(fig_h, use_container_width=True)
