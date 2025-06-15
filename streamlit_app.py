import streamlit as st
from pymongo import MongoClient
import certifi

st.title("MongoDB Atlas Connection Test")

try:
    # Load MongoDB URI from secrets
    uri = st.secrets["URI"]

    # Connect to MongoDB securely using CA file
    client = MongoClient(uri, tlsCAFile=certifi.where())

    db = client["test_db"]
    collection = db["users"]

    # Insert a test document
    result = collection.insert_one({"name": "Anoop", "email": "anoop@example.com"})
    st.success(f"User inserted with ID: {result.inserted_id}")

    # Show all users
    st.write("📄 Existing Users:")
    for doc in collection.find():
        st.json(doc)

except Exception as e:
    st.error(f"❌ Connection failed: {e}")
