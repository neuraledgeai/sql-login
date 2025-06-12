import streamlit as st
import sqlite3
import re

# ---------- Setup DB ----------
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    email TEXT PRIMARY KEY NOT NULL,
    password TEXT NOT NULL,
    nickname TEXT NOT NULL,
    dob TEXT NOT NULL
)
""")
conn.commit()

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
        st.success("🎉 Registration successful. Please log in.")
    except sqlite3.Error as e:
        st.error(f"Database error: {e}")

# ---------- Login User ----------
def login_user(email, password):
    cursor.execute("SELECT password FROM users WHERE email = ?", (email,))
    result = cursor.fetchone()
    if result and result[0] == password:
        st.session_state.current_user_email = email
        st.success("✅ Logged in successfully!")
        st.experimental_rerun()
    else:
        st.error("❌ Invalid email or password.")

# ---------- Init session state ----------
if "current_user_email" not in st.session_state:
    st.session_state.current_user_email = None
if "show_register" not in st.session_state:
    st.session_state.show_register = False

# ---------- App ----------
st.title("🔐 User Login & Registration")

# ---------- User logged in ----------
if st.session_state.current_user_email:
    st.success(f"Welcome, {st.session_state.current_user_email}!")

    cursor.execute("SELECT nickname, dob FROM users WHERE email = ?", (st.session_state.current_user_email,))
    user_info = cursor.fetchone()
    if user_info:
        st.write(f"**Nickname:** {user_info[0]}")
        st.write(f"**Date of Birth:** {user_info[1]}")

    if st.button("🚪 Logout"):
        st.session_state.current_user_email = None
        st.experimental_rerun()

# ---------- Registration Form ----------
elif st.session_state.show_register:
    st.subheader("📝 Register")

    with st.form("register_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        nickname = st.text_input("Nickname")
        dob = st.date_input("Date of Birth")
        submitted = st.form_submit_button("Register")

        if submitted:
            register_user(email, password, nickname, str(dob))

    if st.button("⬅️ Back to Login"):
        st.session_state.show_register = False

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
