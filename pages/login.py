# --- Import Libraries ---
import streamlit as st
from pymongo import MongoClient
import certifi

# --- Setup MongoDB Connection ---
uri = st.secrets["URI"]
client = MongoClient(uri, tlsCAFile=certifi.where())
db = client["asti"]
collection = db["users"]

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
    st.success(f"Welcome back, {st.session_state.current_user_email}!")
    user_info = collection.find_one({"email": st.session_state.current_user_email})
    if user_info:
        st.write(f"**Nickname:** {user_info.get('nickname')}")
        st.write(f"**Date of Birth:** {user_info.get('dob')}")

    if st.button("🚪 Logout"):
        st.session_state.current_user_email = None
        st.rerun()
else:
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

        if submitted:
            login_user(email, password)

    if st.button("📝 Register"):
        st.switch_page("pages/register.py")
