import streamlit as st

st.title("🔐 Welcome to ASTI")

st.write("Choose an option to proceed:")

if st.button("🔑 Login"):
    st.switch_page("pages/login.py")

if st.button("📝 Register"):
    st.switch_page("pages/register.py")
