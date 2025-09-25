# chat.py - Asti app optimized for Gemini 2.5 Flash
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

# ---------------------------
# Google GenAI (Gemini 2.5 Flash) client
# ---------------------------
@st.cache_resource
def get_genai_client():
    return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

genai_client = get_genai_client()
MODEL = "gemini-2.5-flash"

# ---------------------------
# Update learning profile
# ---------------------------
def update_user_learning_profile():
    now = time.time()
    last_update = st.session_state.get("last_profile_update_time", 0)
    if now - last_update < 300:
        return

    chat_history = ""
    for msg in st.session_state.messages:
        if msg["role"] in {"user", "assistant"}:
            chat_history += f"{msg['role'].capitalize()}: {msg['content']}\n"
    if not chat_history.strip():
        return

    analysis_prompt = (
        "You are an expert learning assistant analyzing the following conversation between a student and their AI tutor.\n\n"
        f"{chat_history}\n\n"
        "Based on this entire conversation, provide the following:\n"
        "1. What is the main topic or subject the user is learning about? (Summarize in 1 concise line.)\n"
        "2. Describe the user's learning style briefly.\n\n"
        "Respond in this format exactly:\n"
        "recent_topic: <one-line string>\n"
        "learning_style: <one-line string>"
    )

    try:
        chat = genai_client.chats.create(model=MODEL, history=[{"role": "system", "parts": [INITIAL_SYSTEM_PROMPT]}])
        full_response = ""
        stream = chat.send_message_stream(analysis_prompt)
        for chunk in stream:
            if getattr(chunk, "text", None):
                full_response += chunk.text
        content = full_response.strip()

        recent_topic = None
        learning_style = None
        for line in content.splitlines():
            if line.lower().startswith("recent_topic:"):
                recent_topic = line.split(":", 1)[1].strip()
            elif line.lower().startswith("learning_style:"):
                learning_style = line.split(":", 1)[1].strip()

        if recent_topic:
            user_doc = collection.find_one({"email": st.session_state.current_user_email}) or {}
            current_topics = user_doc.get("topics_learned", "")
            topic_list = [t.strip() for t in current_topics.split(",") if t.strip() and t.strip().lower() != "none"] if isinstance(current_topics, str) else []
            if recent_topic not in topic_list:
                topic_list.append(recent_topic)
            updated_topics_string = ", ".join(topic_list)

            collection.update_one(
                {"email": st.session_state.current_user_email},
                {"$set": {
                    "recent_topic": recent_topic,
                    "topics_learned": updated_topics_string,
                    "learning_style": learning_style or ""
                }}
            )
            st.toast("✅ Learning profile updated")
            st.session_state.last_profile_update_time = now
    except Exception as e:
        st.warning(f"⚠️ Error during learning profile update: {e}")

# ---------------------------
# Streamlit setup
# ---------------------------
st.set_page_config(page_title="Asti", layout="wide", page_icon="🌟", initial_sidebar_state="expanded")
st.sidebar.page_link("pages/chat.py", label="Chat", icon="💬")

# ---------------------------
# Document parsing
# ---------------------------
def read_pdf(file):
    reader = PdfReader(file)
    text_pages = [page.extract_text().strip() for page in reader.pages if page.extract_text()]
    return f"User uploaded a PDF document. Here are the contents of it:\n\n" + "\n\n".join(text_pages)

def read_word(file):
    doc = Document(file)
    return f"User uploaded a Word document. Here are the contents of it:\n\n" + "\n".join(p.text for p in doc.paragraphs)

# ---------------------------
# Session state
# ---------------------------
if "last_profile_update_time" not in st.session_state:
    st.session_state.last_profile_update_time = time.time()
if "messages" not in st.session_state:
    st.session_state.messages = []
if "document_content" not in st.session_state:
    st.session_state.document_content = None
if "prefill_input" not in st.session_state:
    st.session_state.prefill_input = ""

# ---------------------------
# File uploader UI
# ---------------------------
with st.expander("📄 Upload Your Study Material (Optional)", expanded=True):
    uploaded_file = st.file_uploader("Upload a PDF or Word file", type=["pdf", "docx"])
    if uploaded_file:
        try:
            if uploaded_file.name.endswith(".pdf"):
                st.session_state.document_content = read_pdf(uploaded_file)
            elif uploaded_file.name.endswith(".docx"):
                st.session_state.document_content = read_word(uploaded_file)
            st.success("✅ Document uploaded successfully!")

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                if st.button("📄 Summarize"):
                    st.session_state.prefill_input = "Please provide a concise and *highly readable* summary of the entire contents of the uploaded document."
            with col2:
                if st.button("🧠 Make Quiz"):
                    st.session_state.prefill_input = "Create a comprehensive quiz based *only* on the content of the uploaded document."
            with col3:
                if st.button("📚 Explain"):
                    st.session_state.prefill_input = "Identify and explain *comprehensively* the key concepts and important ideas present in the uploaded document."
            with col4:
                if st.button("🗺️ Roadmap"):
                    st.session_state.prefill_input = "Based on the content of the uploaded document, create a structured learning roadmap..."
        except Exception as e:
            st.error(f"❌ Error reading file: {e}")

# ---------------------------
# Show chat history
# ---------------------------
for msg in st.session_state.messages:
    if msg["role"] in {"user", "assistant"}:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# ---------------------------
# Chat input
# ---------------------------
placeholder = "Ask about your document or chat generally..." if st.session_state.document_content else "Type your message here..."
prefill_text = st.session_state.get("prefill_input", "")
user_input = st.chat_input(placeholder)
if user_input is None and prefill_text:
    user_input = prefill_text

# ---------------------------
# Main chat loop
# ---------------------------
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.session_state.prefill_input = ""

    with st.chat_message("user"):
        st.markdown(user_input)

    response_placeholder = st.empty()
    full_response = ""

    # Build history (system prompt + document + previous messages)
    history = [{"role": "system", "parts": [INITIAL_SYSTEM_PROMPT]}]
    if st.session_state.document_content:
        history.append({"role": "user", "parts": [st.session_state.document_content]})
    for msg in st.session_state.messages[:-1]:
        if msg["role"] in {"user", "assistant"}:
            history.append({"role": msg["role"], "parts": [msg["content"]]})

    try:
        chat = genai_client.chats.create(model=MODEL, history=history)
        stream = chat.send_message_stream(user_input)
        for chunk in stream:
            if getattr(chunk, "text", None):
                full_response += chunk.text
                response_placeholder.markdown(full_response)

        st.session_state.messages.append({"role": "assistant", "content": full_response.strip()})
        update_user_learning_profile()

    except Exception as e:
        error_message = str(e)
        if "Input validation error" in error_message and "tokens" in error_message:
            st.warning("⚠️ Too much text, token limit reached. Start a new chat to continue.")
        else:
            st.error(f"⚠️ Error: {error_message}")
