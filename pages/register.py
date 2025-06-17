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

# --- Email Validation & Cleanup ---
def clean_and_validate_email(email):
    email = email.strip()
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    if not re.match(pattern, email):
        return None
    return email

# --- Register User Function ---
def register_user(email, password, confirm_password, nickname, dob):
    if not email or not password or not confirm_password or not nickname or not dob:
        st.error("All fields are required.")
        return

    email = clean_and_validate_email(email)
    if not email:
        st.error("Please enter a valid email address.")
        return

    if len(password) < 6:
        st.error("Password must be at least 6 characters long.")
        return

    if password != confirm_password:
        st.error("Passwords do not match.")
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

# --- Custom CSS Styling ---
st.markdown("""
    <style>
        .register-title {
            text-align: center;
            font-size: 2rem;
            margin-bottom: 1.5rem;
        }
    </style>
""", unsafe_allow_html=True)

# --- UI ---
st.markdown('<div class="register-title">📝 Register</div>', unsafe_allow_html=True)

with st.form("register_form"):
    email = st.text_input("📧 Email")
    password = st.text_input("🔒 Password", type="password")
    confirm_password = st.text_input("🔁 Confirm Password", type="password")
    nickname = st.text_input("👤 Name")
    dob = st.date_input(
        "🎂 Date of Birth",
        min_value=datetime.date(1900, 1, 1),
        max_value=datetime.date.today(),
        value=datetime.date(2000, 1, 1)
    )
    submitted = st.form_submit_button("✅ Register")
    st.markdown('</div>', unsafe_allow_html=True)

    if submitted:
        register_user(email, password, confirm_password, nickname, str(dob))
