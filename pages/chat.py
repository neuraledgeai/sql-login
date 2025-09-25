# --- chat.py ---

# --- Import Libraries ---
from together import Together
from PyPDF2 import PdfReader
from docx import Document
import re
from os import environ
from io import BytesIO
import streamlit as st
from pymongo import MongoClient
import certifi
import time


# --- Setup MongoDB Connection ---
@st.cache_resource
def get_mongo_client():
    uri = st.secrets["URI"]
    return MongoClient(uri, tlsCAFile=certifi.where())

client = get_mongo_client()
db = client["asti"]
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
    nickname = user.get("nickname", "Learner").strip()
    recent_topic = user.get("recent_topic", "None").strip()
    topics_learned_raw = user.get("topics_learned", "").strip()
    learning_style = user.get("learning_style", "Not specified").strip()

    # Clean or normalize potential "null-like" entries
    if recent_topic.lower() in {"", "none", "null"}:
        recent_topic = "Not available"

    if topics_learned_raw.lower() in {"", "none", "null"}:
        topics_learned = "Not available"
    else:
        topics_learned = topics_learned_raw

    if learning_style.lower() in {"", "none", "null", "not specified"}:
        learning_style = "Not identified yet"

    # Final system prompt
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

# --- Update User Learning Profile Function ---
def update_user_learning_profile():
    now = time.time()
    last_update = st.session_state.get("last_profile_update_time", 0)
    if now - last_update < 300:
        return

    # --- Collect chat history ---
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
        result = client.chat.completions.create(
            model=META_MODEL,
            messages=[{"role": "system", "content": analysis_prompt}]
        )
        content = result.choices[0].message.content.strip()

        lines = content.splitlines()
        recent_topic = None
        learning_style = None

        for line in lines:
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


# --- Streamlit Page Configuration ---
st.set_page_config(
    page_title="Asti",
    layout="wide",
    page_icon="🌟",
    initial_sidebar_state="expanded"
)

# --- Sidebar Navigation ---
st.sidebar.page_link("pages/chat.py", label="Chat", icon="💬")


# --- API Key & Client Initialization ---
@st.cache_resource
def get_together_client():
    return Together(api_key=st.secrets["API_KEY"])

client = get_together_client()

# --- LLM Model Definitions ---
META_MODEL = "lgai/exaone-3-5-32b-instruct"
DEEPSEEK_MODEL = "deepseek-ai/DeepSeek-R1-Distill-Llama-70B-free"

# --- Document Text Extraction Functions ---
def read_pdf(file):
    pdf_reader = PdfReader(file)
    text = "\n\n".join(
        page.extract_text().strip()
        for page in pdf_reader.pages
        if page.extract_text()
    )
    return f"User uploaded a PDF document. Here are the contents of it:\n\n{text}"

def read_word(file):
    doc = Document(file)
    text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
    return f"User uploaded a Word document. Here are the contents of it:\n\n{text}"

# --- Session State Initialization ---
if "last_profile_update_time" not in st.session_state:
    st.session_state.last_profile_update_time = time.time()
if "messages" not in st.session_state:
    st.session_state.messages = []
if "document_content" not in st.session_state:
    st.session_state.document_content = None
if "selected_model" not in st.session_state:
    st.session_state.selected_model = META_MODEL
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


# --- Chat History Display ---
for message in st.session_state.messages:
    if message["role"] in {"user", "assistant"}:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# --- Input Placeholder ---
if st.session_state.document_content:
    placeholder = "Ask about your document or chat generally..."
else:
    placeholder = "Type your message here..."

# --- Main Chat Input & Response Generation ---
prefill_text = st.session_state.get("prefill_input", "")
user_input = st.chat_input(placeholder)
if user_input is None and prefill_text:
    user_input = prefill_text

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.session_state.prefill_input = ""

    with st.chat_message("user"):
        st.markdown(user_input)

    response_placeholder = st.empty()
    full_response = ""

    messages_with_context = [{"role": "system", "content": st.session_state.document_content}] if st.session_state.document_content else []
    messages_with_context.extend(st.session_state.messages)

    try:
        stream = client.chat.completions.create(
            model=st.session_state.selected_model,
            messages=messages_with_context,
            stream=True,
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                full_response += chunk.choices[0].delta.content

        clean_response = full_response.strip()
        response_placeholder.markdown(clean_response)
        st.session_state.messages.append({"role": "assistant", "content": clean_response})
        update_user_learning_profile()
    except Exception as e:
        error_message = str(e)
        if "Input validation error" in error_message and "tokens" in error_message:
            st.warning("⚠️ Too much text, token limit reached. Start a new chat to continue.")
