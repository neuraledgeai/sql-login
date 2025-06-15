import streamlit as st
import pymongo
from pymongo import MongoClient

st.title("MongoDB Test: Create a Sample User")

try:
    # Read MongoDB URI from Streamlit secrets
    uri = st.secrets["URI"] 
    
    # Connect to MongoDB
    client = MongoClient(uri)

    # Access your database and collection
    db = client["asti"]           
    users = db["users"]   me

    # Create a sample user
    sample_user = {
        "name": "John Doe",
        "email": "john@example.com",
        "created_at": st.session_state.get("timestamp", "2025-06-14")
    }

    # Insert the user
    insert_result = users.insert_one(sample_user)
    st.success(f"Inserted user with ID: {insert_result.inserted_id}")

    # Display all users
    st.subheader("Current Users in Database:")
    for user in users.find():
        st.json(user)

    # Close connection
    client.close()

except Exception as e:
    st.error(f"Error: {e}")
