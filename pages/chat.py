# --- chat.py ---

# --- Import Libraries ---
from google import genai
from PyPDF2 import PdfReader
from docx import Document
import re
import streamlit as st
from pymongo import MongoClient
import certifi
import time

# --- Setup MongoDB Connection ---
@st.cache_resource
def get_mongo_client():
    uri = st.secrets["URI"]
    return MongoClient(uri, tlsCAFile=certifi.where())

client_db = get_mongo_client()
db = client_db["asti"]
collection = db["users"]

# --- Check Login State ---
if "current_user_email" not in st.session_state or not st.session_state.current_user_email:
    st.error("Session expired or user not logged in.")
    st.stop()

# --- Fetch User Info ---
def initializing_user(email):
    user = collection.find_one({"email": email})
    if not user:
        return (
            "You’re Asti, an expert study assistant. The user information could not be retrieved. "
            "Proceed normally, and assist the user with warmth and clarity."
        )

    # Extract fields safely
    nickname = (user.get("nickname") or "Learner").strip()
    recent_topic = (user.get("recent_topic") or "").strip()
    topics_learned_raw = (user.get("topics_learned") or "").strip()
    learning_style = (user.get("learning_style") or "").strip()

    if not recent_topic or recent_topic.lower() in {"none", "null"}:
        recent_topic = "Not available"

    if not topics_learned_raw or topics_learned_raw.lower() in {"none", "null"}:
        topics_learned = "Not available"
    else:
        topics_learned = topics_learned_raw

    if not learning_style or learning_style.lower() in {"none", "null", "not specified"}:
        learning_style = "Not identified yet"

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

# --- Google GenAI Client ---
@st.cache_resource
def get_google_client():
    return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

client = get_google_client()

MODEL = "gemini-2.5-flash"

# --- Update User Learning Profile Function ---
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
        "Respond in this format:\n"
        "recent_topic: <one-line string>\n"
        "learning_style: <one-line string>"
    )

    try:
        temp_chat = client.chats.create(model=MODEL, history=[{"role": "user", "parts": [analysis_prompt]}])
        response = temp_chat.send_message("Analyze and respond in the required format.")
        content = response.text.strip()

        recent_topic, learning_style = None, None
        for line in content.splitlines():
            if line.lower().startswith("recent_topic:"):
                recent_topic = line.split(":", 1)[1].strip()
            elif line.lower().startswith("learning_style:"):
                learning_style = line.split(":", 1)[1].strip()

        if recent_topic:
            user_doc = collection.find_one({"email": st.session_state.current_user_email})
            current_topics = user_doc.get("topics_learned", "")
            if isinstance(current_topics, str):
                topic_list = [t.strip() for t in current_topics.split(",") if t.strip() and t.strip().lower() != "none"]
            else:
                topic_list = []
            if recent_topic not in topic_list:
                topic_list.append(recent_topic)
            updated_topics_string = ", ".join(topic_list)

            collection.update_one(
                {"email": st.session_state.current_user_email},
                {"$set": {
                    "recent_topic": recent_topic,
                    "topics_learned": updated_topics_string,
                    "learning_style": learning_style
                }}
            )
            st.toast("✅ Learning profile updated")
            st.session_state.last_profile_update_time = now

    except Exception as e:
        st.warning(f"⚠️ Error during learning profile update: {e}")

# --- Streamlit Page Config ---
st.set_page_config(
    page_title="Asti",
    layout="wide",
    page_icon="🌟",
    initial_sidebar_state="expanded"
)
st.sidebar.page_link("pages/chat.py", label="Chat", icon="💬")

# --- Document Text Extraction ---
def read_pdf(file):
    pdf_reader = PdfReader(file)
    text = "\n\n".join(page.extract_text().strip() for page in pdf_reader.pages if page.extract_text())
    return f"User uploaded a PDF document. Here are the contents of it:\n\n{text}"

def read_word(file):
    doc = Document(file)
    text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
    return f"User uploaded a Word document. Here are the contents of it:\n\n{text}"

# --- Session State Init ---
if "last_profile_update_time" not in st.session_state:
    st.session_state.last_profile_update_time = time.time()
if "messages" not in st.session_state:
    st.session_state.messages = []
if "document_content" not in st.session_state:
    st.session_state.document_content = None
if "init_prompt_injected" not in st.session_state:
    st.session_state.messages.insert(0, {"role": "system", "content": INITIAL_SYSTEM_PROMPT})
    st.session_state.init_prompt_injected = True

# --- File Upload Section ---
with st.expander("📄 Upload Your Study Material (Optional)", expanded=True):
    uploaded_file = st.file_uploader("Upload a PDF or Word file", type=["pdf", "docx"])
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith(".pdf"):
                st.session_state.document_content = read_pdf(uploaded_file)
            elif uploaded_file.name.endswith(".docx"):
                st.session_state.document_content = read_word(uploaded_file)
            st.success("✅ Document uploaded successfully! You can now start chatting.")

            col1, col2, col3, col4 = st.columns(4)
            if col1.button("📄 Summarize"):
                st.session_state.prefill_input = "Please provide a concise and highly readable summary of the uploaded document."
            if col2.button("🧠 Make Quiz"):
                st.session_state.prefill_input = "Create a comprehensive quiz based only on the document content."
            if col3.button("📚 Explain"):
                st.session_state.prefill_input = "Explain the key concepts and important ideas in the uploaded document."
            if col4.button("🗺️ Roadmap"):
                st.session_state.prefill_input = "Based on the uploaded content, create a structured learning roadmap."
        except Exception as e:
            st.error(f"❌ Error reading file: {e}")

# --- Chat History Display ---
for message in st.session_state.messages:
    if message["role"] in {"user", "assistant"}:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# --- Input Placeholder ---
placeholder = "Ask about your document or chat generally..." if st.session_state.document_content else "Type your message here..."
prefill_text = st.session_state.get("prefill_input", "")
user_input = st.chat_input(placeholder)
if user_input is None and prefill_text:
    user_input = prefill_text

# --- Main Chat Input & Response ---
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.session_state.prefill_input = ""
    with st.chat_message("user"):
        st.markdown(user_input)

    response_placeholder = st.empty()
    full_response = ""

    history = []
    if st.session_state.document_content:
        history.append({"role": "system", "parts": [st.session_state.document_content]})
    for msg in st.session_state.messages:
        history.append({"role": msg["role"], "parts": [msg["content"]]})

    try:
        chat = client.chats.create(model=MODEL, history=history)
        response_stream = chat.send_message_stream(user_input)
        for chunk in response_stream:
            if chunk.text:
                full_response += chunk.text
                response_placeholder.markdown(full_response)
        st.session_state.messages.append({"role": "assistant", "content": full_response.strip()})
        update_user_learning_profile()
    except Exception as e:
        st.error(f"⚠️ Error: {e}")
