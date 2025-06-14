import streamlit as st
import re
import datetime
import firebase_admin
from firebase_admin import credentials, firestore

# ---------- Firebase Setup ----------
cred = credentials.Certificate("db_key.json")  # Your Firebase service account key
try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app(cred)

db = firestore.client()

# ---------- Email validation ----------
def is_valid_email(email):
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return re.match(pattern, email)

# ---------- Register User ----------
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

    doc_ref = db.collection("users").document(email)
    if doc_ref.get().exists:
        st.error("This email is already registered.")
        return

    try:
        doc_ref.set({
            "email": email,
            "password": password,  # You should hash this in production!
            "nickname": nickname,
            "dob": dob
        })
        st.success("🎉 Registration successful. Please log in.")
    except Exception as e:
        st.error(f"Database error: {e}")

# ---------- Login User ----------
def login_user(email, password):
    doc_ref = db.collection("users").document(email)
    doc = doc_ref.get()
    if doc.exists:
        user_data = doc.to_dict()
        if user_data.get("password") == password:
            st.session_state.current_user_email = email
            st.success("✅ Logged in successfully!")
            st.rerun()
        else:
            st.error("❌ Invalid email or password.")
    else:
        st.error("❌ Invalid email or password.")

# ---------- Init session state ----------
if "current_user_email" not in st.session_state:
    st.session_state.current_user_email = None
if "show_register" not in st.session_state:
    st.session_state.show_register = False

# ---------- App ----------
st.title("🔐 User Login & Registration (Firebase Version)")

# ---------- User logged in ----------
if st.session_state.current_user_email:
    st.success(f"Welcome, {st.session_state.current_user_email}!")

    doc = db.collection("users").document(st.session_state.current_user_email).get()
    if doc.exists:
        user_info = doc.to_dict()
        st.write(f"**Nickname:** {user_info.get('nickname')}")
        st.write(f"**Date of Birth:** {user_info.get('dob')}")

    if st.button("🚪 Logout"):
        st.session_state.current_user_email = None
        st.rerun()

# ---------- Registration Form ----------
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

# ---------- Login Form ----------
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
