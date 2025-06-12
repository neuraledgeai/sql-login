import streamlit as st
import sqlite3
import re

# ---------- Connect to database ----------
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()

# ---------- Email validation ----------
def is_valid_email(email):
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return re.match(pattern, email)

# ---------- Registration Logic ----------
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
        st.success("🎉 Registration successful. Please go back to the login page to sign in.")
    except sqlite3.Error as e:
        st.error(f"Database error: {e}")

# ---------- UI ----------
st.title("📋 User Registration")

with st.form("register_form"):
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    nickname = st.text_input("Nickname")
    dob = st.date_input("Date of Birth")
    submitted = st.form_submit_button("Register")

    if submitted:
        register_user(email, password, nickname, str(dob))

