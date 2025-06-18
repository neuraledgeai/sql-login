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

# --- Setup MongoDB Connection ---
@st.cache_resource
def get_mongo_client():
    uri = st.secrets["URI"]
    return MongoClient(uri, tlsCAFile=certifi.where())

client = get_mongo_client()
db = client["asti"]
collection = db["users"]

@st.cache_data
def get_user_info(email: str):
    return collection.find_one({"email": email})

# --- Check Login State ---
if "current_user_email" not in st.session_state or not st.session_state.current_user_email:
    st.error("Session expired or user not logged in.")
    st.stop()

user_info = get_user_info(st.session_state.current_user_email)

# --- Streamlit Page Configuration ---
st.set_page_config(
    page_title="Asti",
    layout="wide",
    page_icon="🌟",
    initial_sidebar_state="expanded"
)

# --- Sidebar Navigation ---
st.sidebar.page_link("pages/chat.py", label="Chat", icon="💬")

# --- API Client Initialization ---
@st.cache_resource
def get_together_client():
    return Together(api_key=st.secrets["API_KEY"])

@st.cache_resource
def get_elevenlabs_client():
    return ElevenLabs(api_key=st.secrets["ELEVENLABS_API_KEY"])

client = get_together_client()
serp_api_key = st.secrets["SERP_API_KEY"]
elevenlabs = get_elevenlabs_client()

# --- LLM Models ---
META_MODEL = "meta-llama/Llama-3.3-70B-Instruct-Turbo-Free"
DEEPSEEK_MODEL = "deepseek-ai/DeepSeek-R1-Distill-Llama-70B-free"

# --- Web Search Function ---
@st.cache_data(ttl=3600)
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

# --- Document Parsing ---
@st.cache_data
def read_pdf(file_bytes):
    pdf_reader = PdfReader(BytesIO(file_bytes))
    return "\n\n".join(
        page.extract_text().strip() for page in pdf_reader.pages if page.extract_text()
    )

@st.cache_data
def read_word(file_bytes):
    doc = Document(BytesIO(file_bytes))
    return "\n".join(paragraph.text for paragraph in doc.paragraphs)

# --- Session State Init ---
st.session_state.setdefault("messages", [])
st.session_state.setdefault("document_content", None)
st.session_state.setdefault("selected_model", META_MODEL)
st.session_state.setdefault("prefill_input", "")

# --- File Upload ---
with st.expander("📄 Upload Your Study Material (Optional)", expanded=True):
    uploaded_file = st.file_uploader("Upload a PDF or Word file", type=["pdf", "docx"])
    if uploaded_file is not None:
        try:
            file_bytes = uploaded_file.read()
            if uploaded_file.name.endswith(".pdf"):
                content = read_pdf(file_bytes)
            else:
                content = read_word(file_bytes)
            st.session_state.document_content = f"User uploaded a document. Contents:\n\n{content}"
            st.success("✅ Document uploaded successfully!")

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                if st.button("📄 Summarize"):
                    st.session_state.prefill_input = "Please summarize the uploaded document."
            with col2:
                if st.button("🧠 Make Quiz"):
                    st.session_state.prefill_input = "Create a quiz from the uploaded document."
            with col3:
                if st.button("📚 Explain"):
                    st.session_state.prefill_input = "Explain the key ideas in the uploaded document."
            with col4:
                if st.button("🗜️ Roadmap"):
                    st.session_state.prefill_input = "Create a learning roadmap from this document."
        except Exception as e:
            st.error(f"❌ Error reading file: {e}")

# --- Model Choice ---
model_choice = st.segmented_control(
    "",
    options=["Default", "Reason", "Web Search"],
    format_func=lambda x: "Turbo Chat" if x == "Default" else x,
    default="Default"
)

st.session_state.selected_model = (
    DEEPSEEK_MODEL if model_choice == "Reason" else META_MODEL
)

# --- Display Chat History ---
if "chat_displayed" not in st.session_state:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    st.session_state.chat_displayed = True

# --- Input Placeholder Logic ---
placeholder = {
    "Web Search": "Search the web for information or a topic...",
    "Reason": "Ask a question requiring deeper thought..." if not st.session_state.document_content else "Ask about your document...",
    "Default": "Type your message here..." if not st.session_state.document_content else "Ask about your document or chat generally..."
}[model_choice]

user_input = st.chat_input(placeholder)
if user_input is None and st.session_state.prefill_input:
    user_input = st.session_state.prefill_input

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.session_state.prefill_input = ""
    with st.chat_message("user"):
        st.markdown(user_input)
    response_placeholder = st.empty()
    full_response = ""

    if model_choice == "Web Search":
        decision_prompt = (
            f"User asked: '{user_input}'. Should we search the web? Reply YES or NO."
        )
        decision = client.chat.completions.create(
            model=META_MODEL,
            messages=[{"role": "system", "content": decision_prompt}]
        ).choices[0].message.content.strip().upper()

        if decision == "YES":
            query_prompt = f"Generate a Google search query from: {user_input}"
            search_query = client.chat.completions.create(
                model=META_MODEL,
                messages=[{"role": "system", "content": query_prompt}]
            ).choices[0].message.content.strip()

            search_results = fetch_snippets(search_query, serp_api_key)
            final_prompt = f"Query: {user_input}. Search Results: {search_results}"
        else:
            final_prompt = f"User: {user_input}. Respond naturally."

        stream = client.chat.completions.create(
            model=META_MODEL,
            messages=[{"role": "system", "content": final_prompt}],
            stream=True
        )
    else:
        context = st.session_state.document_content or ""
        messages = ([{"role": "system", "content": context}] if context else []) + st.session_state.messages
        stream = client.chat.completions.create(
            model=st.session_state.selected_model,
            messages=messages,
            stream=True
        )

    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            full_response += chunk.choices[0].delta.content
            response_placeholder.markdown(full_response)

    clean_response = re.sub(r"<think>.*?</think>", "", full_response, flags=re.DOTALL).strip()
    st.session_state.messages.append({"role": "assistant", "content": clean_response})

# --- Voice Overview ---
if st.session_state.get("document_content"):
    with st.sidebar:
        st.markdown("Voice Overview")
        language = st.radio("Select output language:", ["English", "Hindi"], index=1)
        if st.button("Generate Voice Overview"):
            prompt = (
                f"Summarize this in a short, engaging narrative in {language}:\n\n"
                f"{st.session_state.document_content}"
            )
            try:
                response = client.chat.completions.create(
                    model=META_MODEL,
                    messages=[{"role": "system", "content": prompt}]
                )
                script = response.choices[0].message.content.strip()
                st.session_state.voice_script = script
            except Exception as e:
                st.error(f"Error generating script: {e}")

            audio_gen = elevenlabs.text_to_speech.convert(
                text=st.session_state.voice_script,
                voice_id="nPczCjzI2devNBz1zQrb",
                model_id="eleven_flash_v2_5",
                output_format="mp3_44100_128"
            )
            audio_bytes = b"".join(audio_gen)
            st.audio(BytesIO(audio_bytes), format="audio/mp3")
