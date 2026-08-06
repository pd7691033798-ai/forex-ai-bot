import streamlit as st
import datetime

# Page Configuration
st.set_page_config(page_title="My Forex AI Trading Bot", page_icon="📈", layout="centered")

# App Header
st.title("🤖 My Forex AI Trading App")
st.caption("Automated Forex Analysis & Execution Dashboard")

st.divider()

# Status Indicator
st.subheader("⚡ Bot Status")
col1, col2 = st.columns(2)
with col1:
    st.metric(label="Server Status", value="Online 🟢")
with col2:
    st.metric(label="Uptime Monitoring", value="Active 24/7 ⏰")

st.divider()

# Control Panel
st.subheader("⚙️ Control Panel")
bot_active = st.toggle("Enable Auto Trading Signals", value=True)

if bot_active:
    st.success("Bot is running and actively scanning markets!")
else:
    st.warning("Bot is currently paused.")

st.divider()

# Market Signals Preview
st.subheader("📊 Live Market Signals")

col_a, col_b, col_c = st.columns(3)
with col_a:
    st.markdown("### EUR/USD")
    st.info("Signal: HOLD ⏸️")
    
with col_b:
    st.markdown("### XAU/USD (GOLD)")
    st.success("Signal: BUY 📈")
    st.caption("SL: 2380 | TP: 2410")

with col_c:
    st.markdown("### GBP/USD")
    st.info("Signal: HOLD ⏸️")

st.divider()

# Last Updated Time
st.caption(f"Last updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

