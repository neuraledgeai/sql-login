# --- Import Libraries ---
import streamlit as st
from pymongo import MongoClient
import certifi
import re

# --- Setup MongoDB Connection ---
uri = st.secrets["URI"]
client = MongoClient(uri, tlsCAFile=certifi.where())
db = client["asti"]
collection = db["users"]

# --- Email Validation & Cleanup ---
def clean_and_validate_email(email):
    email = email.strip()  # Remove leading/trailing whitespaces
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    if not re.match(pattern, email):
        return None
    return email

# --- Login User Function ---
def login_user(email, password):
    user = collection.find_one({"email": email})
    if user and user.get("password") == password:
        st.session_state.current_user_email = email
        st.rerun()
    else:
        st.error("❌ Invalid email or password.")

# --- Initialize Session State ---
if "current_user_email" not in st.session_state:
    st.session_state.current_user_email = None

# --- UI ---
st.title("🔑 Login")

if st.session_state.current_user_email:
    st.switch_page("pages/chat.py")
else:
    with st.form("login_form"):
        raw_email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

        if submitted:
            email = clean_and_validate_email(raw_email)
            if not email:
                st.error("Please enter a valid email address.")
            else:
                login_user(email, password)

    # Add Register and Forgot Password Links
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("📝 Register"):
            st.switch_page("pages/register.py")
    with col2:
        # Replace this with your actual form URL
        reset_form_url = "https://forms.gle/YOUR_FORM_LINK_HERE"
        st.markdown(
            f'<div style="text-align:right"><a href="{reset_form_url}" target="_blank">🔒 Forgot Password?</a></div>',
            unsafe_allow_html=True
        )
