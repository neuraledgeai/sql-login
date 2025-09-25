# chat.py - Asti app optimized for Gemini
from google import genai
from PyPDF2 import PdfReader
from docx import Document
import streamlit as st
from pymongo import MongoClient
import certifi
import time

# ---------------------------
# MongoDB connection
# ---------------------------
@st.cache_resource
def get_mongo_client():
    uri = st.secrets["URI"]
    return MongoClient(uri, tlsCAFile=certifi.where())

mongo_client = get_mongo_client()
db = mongo_client["asti"]
collection = db["users"]

# ---------------------------
# Auth guard
# ---------------------------
if "current_user_email" not in st.session_state or not st.session_state.current_user_email:
    st.error("Session expired or user not logged in.")
    st.stop()

# ---------------------------
# Safe user initialization
# ---------------------------
def initializing_user(email):
    user = collection.find_one({"email": email})
    if not user:
        return (
            "You’re Asti, an expert study assistant. The user information could not be retrieved. "
            "Proceed normally, and assist the user with warmth and clarity."
        )

    nickname = (user.get("nickname") or "Learner").strip()
    recent_topic_raw = (user.get("recent_topic") or "").strip()
    topics_learned_raw = (user.get("topics_learned") or "").strip()
    learning_style_raw = (user.get("learning_style") or "").strip()

    recent_topic = recent_topic_raw if recent_topic_raw.lower() not in {"", "none", "null"} else "Not available"
    topics_learned = topics_learned_raw if topics_learned_raw.lower() not in {"", "none", "null"} else "Not available"
    learning_style = learning_style_raw if learning_style_raw.lower() not in {"", "none", "null", "not specified"} else "Not identified yet"

    system_prompt = f"""
You are Asti, an intelligent, helpful, and personalized learning co-pilot.

Your goal is to help students learn by explaining concepts in a clear, engaging, and adaptive way. Adjust your style to the student's preferred learning method.

Student Profile:
👤 Name: {nickname}
📚 Most Recent Topic: {recent_topic}
✅ Topics Learned So Far: {topics_learned}
🧠 Preferred Learning Style: {learning_style}

Instructions:
- Always adapt your tone and explanations to the student’s style.
- Reinforce current learning by referencing related past topics when appropriate.
- If the user uploads a document, prioritize its content unless told otherwise.
- Be friendly, and educational at all times. You can use emojis for a good understanding 🥳.
"""
    return system_prompt.strip()

INITIAL_SYSTEM_PROMPT = initializing_user(st.session_state.current_user_email)

# --- CORRECTED API SETUP ---
# This line sets the API key for all subsequent calls in your app.
# It requires the LATEST version of the library.
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
MODEL_NAME = "gemini-1.5-flash"
# ---------------------------


# ---------------------------
# Update learning profile
# ---------------------------
def update_user_learning_profile():
    now = time.time()
    last_update = st.session_state.get("last_profile_update_time", 0)
    if now - last_update < 300: # 5 minutes cooldown
        return

    chat_history = ""
    for msg in st.session_state.messages:
        if msg["role"] in {"user", "assistant"}:
            chat_history += f"{msg['role'].capitalize()}: {msg['content']}\n"
    if not chat_history.strip():
        return

    analysis_prompt = (
        "You are an expert learning assistant analyzing the following conversation..."
        # (rest of the prompt is unchanged)
    )

    try:
        model = genai.GenerativeModel(MODEL_NAME)
        response = model.generate_content(analysis_prompt)
        content = response.text.strip()
        # (rest of the function is unchanged)

    except Exception as e:
        st.warning(f"⚠️ Error during learning profile update: {e}")

# ... (The rest of your Streamlit code remains the same) ...
# ... I am omitting it for brevity, but the main chat loop logic is now correct ...

# ---------------------------
# Main chat loop
# ---------------------------
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.session_state.prefill_input = ""

    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        
        try:
            # Create the model instance with the system prompt
            model = genai.GenerativeModel(
                model_name=MODEL_NAME,
                system_instruction=INITIAL_SYSTEM_PROMPT
            )
            
            final_prompt = user_input
            if st.session_state.document_content:
                final_prompt = (
                    "Here is content from a document the user uploaded:\n\n"
                    f"{st.session_state.document_content}\n\n"
                    f"Now, based on that document, please answer the user's request: {user_input}"
                )

            response = model.generate_content(final_prompt)
            full_response = response.text.strip()
            
            response_placeholder.markdown(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            # update_user_learning_profile() # You can call this here if needed

        except Exception as e:
            error_message = str(e)
            if "tokens" in error_message.lower():
                st.warning("⚠️ Token limit reached. Please clear the document or start a new chat.")
            else:
                st.error(f"⚠️ An error occurred: {error_message}")
