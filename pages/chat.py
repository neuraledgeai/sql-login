# --- chat.py ---

# --- Import Libraries ---
from together import Together
from PyPDF2 import PdfReader
from docx import Document
import re
from serpapi import GoogleSearch
from os import environ
from io import BytesIO
from elevenlabs import ElevenLabs
import streamlit as st
from pymongo import MongoClient
import certifi
import time
# from datetime import datetime, timedelta
import json

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

# --- Fetch User Info (Cached) ---
@st.cache_resource
def initializing_user(email):
    user = collection.find_one({"email": email})
    if not user:
        return "You’re Asti, an expert study assistant. The user information could not be retrieved. Proceed normally."

    nickname = user.get("nickname", "Learner")
    recent_topic = user.get("recent_topic", "None")
    topics_learned = user.get("topics_learned", [])
    learning_style = user.get("learning_style", "Not specified")

    topics_list = ", ".join(topics_learned) if topics_learned else "None"

    system_prompt = f"""
You are Asti, a highly intelligent and supportive AI tutor. Your goal is to help students learn by explaining concepts in a clear, engaging, and adaptive way. Adjust your style to the student's preferred learning method.

👤 Student Name: {nickname}  
📚 Recently Learned Topic: {recent_topic}  
✅ Topics Covered So Far: {topics_list}  
🧠 Preferred Learning Style: {learning_style}  

Always be warm and encouraging. When possible, refer to past learning to scaffold new information.  
If a document is uploaded, prioritize its content unless instructed otherwise.  
Never assume unknown preferences—clarify when necessary.
"""
    return system_prompt.strip()

INITIAL_SYSTEM_PROMPT = initializing_user(st.session_state.current_user_email)

# --- Update User Learning Profile Function ---
def update_user_learning_profile():
    # Run this only once every 5 minutes
    now = time.time()
    last_update = st.session_state.get("last_profile_update_time", 0)
    if now - last_update < 300:  # 5 minutes = 300 seconds
        return

    # Step 1: Compile full chat history as a string
    full_chat = "\n".join(
        f"{msg['role'].capitalize()}: {msg['content']}" 
        for msg in st.session_state.messages 
        if msg["role"] in {"user", "assistant"}
    )

    # Step 2: Ask the model to extract the profile data
    profile_prompt = f"""
You are a system that monitors a student's learning progress from their chat history.

Here is the entire conversation:

{full_chat}

Now based on this, extract the following information in PURE JSON ONLY:
- recent_topic: The most recent topic discussed or learned.
- topics_learned: A list of all topics discussed or learned in this session.
- learning_style: The student's apparent learning style or preferences.

Reply ONLY in this format (JSON, no extra text):

{{
  "recent_topic": "string",
  "topics_learned": ["list", "of", "topics"],
  "learning_style": "string"
}}
"""

    try:
        profile_response = client.chat.completions.create(
            model=META_MODEL,
            messages=[{"role": "system", "content": profile_prompt}]
        )
        raw_output = profile_response.choices[0].message.content.strip()

        # Parse the output safely
        parsed = json.loads(raw_output)

        # Extract fields
        recent_topic = parsed.get("recent_topic")
        topics_learned = parsed.get("topics_learned")
        learning_style = parsed.get("learning_style")

        # Get the current user from DB
        user_email = st.session_state.current_user_email
        current_user = collection.find_one({"email": user_email})

        # Merge topics_learned into existing list
        if isinstance(topics_learned, list):
            existing_topics = current_user.get("topics_learned") or []
            # Ensure it's a list
            if not isinstance(existing_topics, list):
                existing_topics = []
            updated_topics = list(set(existing_topics + topics_learned))
        else:
            updated_topics = current_user.get("topics_learned")  # Leave unchanged

        # Prepare the update dictionary
        update_fields = {
            "recent_topic": recent_topic,
            "learning_style": learning_style,
            "topics_learned": updated_topics
        }

        # Update the user document in MongoDB
        collection.update_one({"email": user_email}, {"$set": update_fields})

        # Save timestamp of this update
        st.session_state.last_profile_update_time = now

    except json.JSONDecodeError as e:
        st.warning(f"⚠️ Couldn't parse model output as JSON: {e}")
    except Exception as e:
        st.error(f"❌ Failed to update learning profile: {e}")


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

@st.cache_resource
def get_elevenlabs_client():
    return ElevenLabs(api_key=st.secrets["ELEVENLABS_API_KEY"])

client = get_together_client()
serp_api_key = st.secrets["SERP_API_KEY"]
elevenlabs_api_key = st.secrets["ELEVENLABS_API_KEY"]

# --- LLM Model Definitions ---
# META_MODEL = "meta-llama/Llama-3.3-70B-Instruct-Turbo-Free"
META_MODEL = "lgai/exaone-3-5-32b-instruct"
DEEPSEEK_MODEL = "deepseek-ai/DeepSeek-R1-Distill-Llama-70B-free"

# --- Web Search Function ---
def fetch_snippets(query, api_key):
    params = {"engine": "google", "q": query, "api_key": api_key}
    search = GoogleSearch(params)
    results = search.get_dict()
    organic_results = results.get("organic_results", [])
    snippets_with_sources = []

    for i in organic_results:
        snippet = i.get("snippet", "")
        source = i.get("source", "Unknown Source")
        link = i.get("link", "#")
        if snippet:
            linked_source = f"[{source}]({link})"
            snippets_with_sources.append(f"{snippet} ({linked_source})")

    return " ".join(snippets_with_sources) if snippets_with_sources else "No relevant information found."

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
if "messages" not in st.session_state:
    st.session_state.messages = []
if "document_content" not in st.session_state:
    st.session_state.document_content = None
if "selected_model" not in st.session_state:
    st.session_state.selected_model = META_MODEL
    # --- Inject Initial System Prompt Once ---
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

# --- AI Mode Selection (Reason removed) ---
model_choice = st.segmented_control(
    "",
    options=["Default", "Web Search"],
    format_func=lambda x: "Web Search" if x == "Web Search" else "Turbo Chat",
    default="Default"
)
st.session_state.selected_model = META_MODEL

# --- Chat History Display ---
for message in st.session_state.messages:
    if message["role"] in {"user", "assistant"}:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# --- Input Placeholder ---
if model_choice == "Web Search":
    placeholder = "Search the web for information or a topic..."
elif st.session_state.document_content:
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

    if model_choice == "Web Search":
        decision_prompt = (
            "You must decide if this query requires a web search: "
            f"'{user_input}'. Reply only with 'YES' or 'NO'."
        )
        decision_response = client.chat.completions.create(
            model=META_MODEL,
            messages=[{"role": "system", "content": decision_prompt}]
        )
        decision_text = decision_response.choices[0].message.content.strip().upper()

        if decision_text == "YES":
            refine_prompt = f"User's request: {user_input}. Generate a single concise search query."
            refine_response = client.chat.completions.create(
                model=META_MODEL,
                messages=[{"role": "system", "content": refine_prompt}]
            )
            search_query = refine_response.choices[0].message.content.strip()
            search_results = fetch_snippets(search_query, serp_api_key)

            final_prompt = f"Query: {user_input}. Search Results: {search_results}. Respond informatively."
            stream = client.chat.completions.create(
                model=META_MODEL,
                messages=[{"role": "system", "content": final_prompt}],
                stream=True,
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    full_response += chunk.choices[0].delta.content
                    response_placeholder.markdown(full_response)
        else:
            fallback_prompt = f"User: {user_input}. Respond naturally."
            fallback_response = client.chat.completions.create(
                model=META_MODEL,
                messages=[{"role": "system", "content": fallback_prompt}],
                stream=True,
            )
            for chunk in fallback_response:
                if chunk.choices and chunk.choices[0].delta.content:
                    full_response += chunk.choices[0].delta.content
                    response_placeholder.markdown(full_response)

        st.session_state.messages.append({"role": "assistant", "content": full_response})

    else:
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

# --- Voice Overview Feature ---
if st.session_state.get("document_content"):
    with st.sidebar:
        st.markdown("Voice Overview")
        language = st.radio("Select output language:", ["English", "Hindi"], index=1)

        if st.button("Generate Voice Overview"):
            elevenlabs = get_elevenlabs_client()
            with st.spinner("Generating voice script..."):
                prompt = (
                    f"User uploaded a document. Summarize it in a short, powerful, narrative tone in **{language}**.\n\n"
                    f"Document:\n{st.session_state.document_content}"
                )
                try:
                    voice_response = client.chat.completions.create(
                        model=META_MODEL,
                        messages=[{"role": "system", "content": prompt}]
                    )
                    voice_script = voice_response.choices[0].message.content.strip()
                    st.session_state.voice_script = voice_script
                except Exception as e:
                    error_message = str(e)
                    if "Input validation error" in error_message and "tokens" in error_message:
                        st.warning("⚠️ Token limit reached. Use smaller document.")
                    else:
                        st.error(f"❌ Error generating script: {error_message}")

            with st.spinner("Generating audio..."):
                audio_gen = elevenlabs.text_to_speech.convert(
                    text=st.session_state.voice_script,
                    voice_id="nPczCjzI2devNBz1zQrb",
                    model_id="eleven_flash_v2_5",
                    output_format="mp3_44100_128"
                )
                audio_bytes = b''.join(audio_gen)
                audio_buffer = BytesIO(audio_bytes)
                st.audio(audio_buffer, format="audio/mp3")
