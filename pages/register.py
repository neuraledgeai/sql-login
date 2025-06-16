# --- Import Libraries ---
import streamlit as st
from pymongo import MongoClient
import certifi
import datetime
import re

# --- Setup MongoDB Connection ---
uri = st.secrets["URI"]
client = MongoClient(uri, tlsCAFile=certifi.where())
db = client["asti"]
collection = db["users"]

# --- Email Validation ---
def is_valid_email(email):
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return re.match(pattern, email)

# --- Register User Function ---
def register_user(email, password, nickname, dob):
    if not email or not password or not nickname or not dob:
        st.error("All fields are required.")
        return

    if not is_valid_email(email):
        st.error("Please enter a valid email address.")
        return

    if len(password) < 6:
        st.error("Password must be at least 6 characters long.")
        return

    if collection.find_one({"email": email}):
        st.error("This email is already registered.")
        return

    try:
        collection.insert_one({
            "email": email,
            "password": password,
            "nickname": nickname,
            "dob": dob
        })
        st.success("🎉 Registration successful. Please log in.")
    except Exception as e:
        st.error(f"Database error: {e}")

# --- UI ---
st.title("📝 Register")

with st.form("register_form"):
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    nickname = st.text_input("Nickname")
    dob = st.date_input(
        "Date of Birth",
        min_value=datetime.date(1900, 1, 1),
        max_value=datetime.date.today(),
        value=datetime.date(2000, 1, 1)
    )
    submitted = st.form_submit_button("Register")

    if submitted:
        register_user(email, password, nickname, str(dob))

if st.button("⬅️ Back to Login"):
    st.switch_page("pages/Login.py")
