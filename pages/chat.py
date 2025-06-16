# --- chat.py ---

# --- Import Libraries ---
import streamlit as st
from pymongo import MongoClient
import certifi

# --- Setup MongoDB Connection ---
uri = st.secrets["URI"]
client = MongoClient(uri, tlsCAFile=certifi.where())
db = client["asti"]
collection = db["users"]

# --- Check Login State ---
if "current_user_email" not in st.session_state or not st.session_state.current_user_email:
    st.error("Session expired or user not logged in.")
    st.stop()

# --- Fetch User Info ---
user_info = collection.find_one({"email": st.session_state.current_user_email})

# --- Display Chat Header ---
st.title("💬 Welcome to Chat")

# --- Display Nickname ---
if user_info:
    st.subheader(f"Hello, **{user_info.get('nickname', 'User')}**!")
else:
    st.error("Unexpected error: User not found in database.")
