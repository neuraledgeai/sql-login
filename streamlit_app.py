import os
import streamlit as st

cwd = os.getcwd()
st.write(f"📂 Current Working Directory: `{cwd}`")

files = os.listdir(cwd)
st.write("📄 Files and Folders:")
for file in files:
    st.write(f"- {file}")
