import streamlit as st
import re
import datetime
import firebase_admin
from firebase_admin import credentials, firestore

# ---------- Firebase Initialization ----------
if not firebase_admin._apps:
    cred = credentials.Certificate(st.secrets["firebase"])
    firebase_admin.initialize_app(cred)

db = firestore.client()

# ---------- Helper Functions ----------
def login_user(email, password):
    doc_ref = db.collection("users").document(email)
    doc = doc_ref.get()
    if doc.exists:
        user_data = doc.to_dict()
        if user_data.get("password") == password:
            st.success(f"Welcome back, {user_data.get('name')}!")
        else:
            st.error("Incorrect password.")
    else:
        st.error("User not found.")

def show_registration_form():
    st.subheader("Register New Account")
    with st.form("register_form"):
        name = st.text_input("Name")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        dob = st.date_input("Date of Birth")

        submitted = st.form_submit_button("Register")
        if submitted:
            if password != confirm_password:
                st.error("Passwords do not match.")
                return
            if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
                st.error("Invalid email address.")
                return

            doc_ref = db.collection("users").document(email)
            if doc_ref.get().exists:
                st.warning("Email already registered.")
                return

            doc_ref.set({
                "name": name,
                "email": email,
                "password": password,
                "dob": dob.strftime("%Y-%m-%d"),
                "created_at": datetime.datetime.now().isoformat()
            })
            st.success("Registration successful! You can now login.")

# ---------- Streamlit App ----------
st.set_page_config(page_title="Login App", page_icon="🔐")

st.title("🔐 Firebase Login System")

if "show_register" not in st.session_state:
    st.session_state.show_register = False

if st.session_state.show_register:
    show_registration_form()
    if st.button("🔙 Back to Login"):
        st.session_state.show_register = False
else:
    st.subheader("Login")
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

        if submitted:
            login_user(email, password)

    if st.button("📝 Register"):
        st.session_state.show_register = True
