import streamlit as st
import sqlite3
import os

# Print the current working directory
st.write("📁 Current Working Directory:", os.getcwd())

# Check if the file exists
register_path = os.path.join("pages", "register_user.py")
if os.path.exists(register_path):
    st.success(f"✅ File found: {register_path}")
else:
    st.error(f"❌ File NOT found: {register_path}")

# ---------- Connect to database ----------
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()

# ---------- Initialize session state ----------
if "current_user_email" not in st.session_state:
    st.session_state.current_user_email = None

# ---------- Title ----------
st.title("🔐 Login")

# ---------- Login form or dashboard ----------
if st.session_state.current_user_email is None:
    st.subheader("Please log in")

    # Simple login form
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        login_button = st.form_submit_button("Login")

        if login_button:
            cursor.execute("SELECT password FROM users WHERE email = ?", (email,))
            result = cursor.fetchone()
            if result and result[0] == password:
                st.session_state.current_user_email = email
                st.success("✅ Logged in successfully!")
                st.experimental_rerun()
            else:
                st.error("❌ Invalid email or password.")

    # Registration link
    st.info("New here?")
    st.page_link("register_user.py", label="📝 Register", icon="➡️")
else:
    st.success(f"Welcome, {st.session_state.current_user_email}!")

    # Fetch and show user info
    cursor.execute("SELECT nickname, dob FROM users WHERE email = ?", (st.session_state.current_user_email,))
    user_info = cursor.fetchone()
    if user_info:
        nickname, dob = user_info
        st.markdown(f"**Nickname:** {nickname}")
        st.markdown(f"**Date of Birth:** {dob}")

    if st.button("Logout"):
        st.session_state.current_user_email = None
        st.experimental_rerun()

