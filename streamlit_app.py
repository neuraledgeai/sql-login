import streamlit as st
import sqlite3
import re

# ---------- Connect to database ----------
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()

# ---------- Initialize session state ----------
if "current_user_email" not in st.session_state:
    st.session_state.current_user_email = None

# ---------- Email validation function ----------
def is_valid_email(email):
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return re.match(pattern, email)

# ---------- Register user function ----------
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

    cursor.execute("SELECT email FROM users WHERE email = ?", (email,))
    if cursor.fetchone():
        st.error("This email is already registered.")
        return

    try:
        cursor.execute("""
            INSERT INTO users (email, password, nickname, dob) 
            VALUES (?, ?, ?, ?)
        """, (email, password, nickname, dob))
        conn.commit()
        st.success("Registration successful!")
        st.session_state.current_user_email = email
    except sqlite3.Error as e:
        st.error(f"Database error: {e}")

# ---------- Main UI ----------
st.title("👤 User Registration System")

if st.session_state.current_user_email is None:
    st.header("Register")
    with st.form("register_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        nickname = st.text_input("Nickname")
        dob = st.date_input("Date of Birth")
        submitted = st.form_submit_button("Register")

        if submitted:
            register_user(email, password, nickname, str(dob))
else:
    st.success(f"Welcome, {st.session_state.current_user_email}!")

    # Show user info
    cursor.execute("SELECT nickname, dob FROM users WHERE email = ?", (st.session_state.current_user_email,))
    user_info = cursor.fetchone()
    if user_info:
        nickname, dob = user_info
        st.markdown(f"**Nickname:** {nickname}")
        st.markdown(f"**Date of Birth:** {dob}")

    # Logout button
    if st.button("Logout"):
        st.session_state.current_user_email = None
        st.experimental_rerun()
