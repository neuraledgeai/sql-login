# --- Import Libraries ---
import streamlit as st
from pymongo import MongoClient
import certifi
import re
import datetime

# --- Setup MongoDB Connection ---
uri = st.secrets["URI"]  # Store your MongoDB URI in .streamlit/secrets.toml
client = MongoClient(uri, tlsCAFile=certifi.where())
db = client["asti"]
collection = db["users"]

# --- Email Validation ---
def is_valid_email(email):
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return re.match(pattern, email)

# --- Register User ---
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

# --- Login User ---
def login_user(email, password):
    user = collection.find_one({"email": email})
    if user and user.get("password") == password:
        st.session_state.current_user_email = email
        # st.success("✅ Logged in successfully!")
        st.rerun()
    else:
        st.error("❌ Invalid email or password.")

# --- Initialize Session State ---
if "current_user_email" not in st.session_state:
    st.session_state.current_user_email = None
if "show_register" not in st.session_state:
    st.session_state.show_register = False

# --- App Title ---
st.title("🔐 User Login & Registration")
st.sidebar.page_link("pages/Contact_us.py", label="Chat", icon="💬")

# --- User Logged In View ---
if st.session_state.current_user_email:
    st.success(f"Welcome, {st.session_state.current_user_email}!")

    user_info = collection.find_one({"email": st.session_state.current_user_email})
    if user_info:
        st.write(f"**Nickname:** {user_info.get('nickname')}")
        st.write(f"**Date of Birth:** {user_info.get('dob')}")

    if st.button("🚪 Logout"):
        st.session_state.current_user_email = None
        st.rerun()

# --- Registration Form View ---
elif st.session_state.show_register:
    st.subheader("📝 Register")

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
        st.session_state.show_register = False
        st.rerun()

# --- Login Form View ---
else:
    st.subheader("🔑 Login")

    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

        if submitted:
            login_user(email, password)

    if st.button("📝 Register"):
        st.session_state.show_register = True
        st.rerun()
