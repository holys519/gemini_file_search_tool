import streamlit as st
import os
import time
import random
import string
import tempfile
from pathlib import Path
from PyPDF2 import PdfReader
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

# Initialize Gemini client
client = genai.Client(api_key=api_key)

# Language translations
TRANSLATIONS = {
    'en': {
        'page_title': 'PDF Chat with Gemini',
        'page_icon': '📄',
        'main_title': '📄 PDF Chat with Gemini',
        'subtitle': "Upload a PDF and ask questions about its content using Google's Gemini AI",
        'language': 'Language',
        'model': 'Model',
        'sidebar_header': 'PDF Upload',
        'choose_file': 'Choose a PDF file',
        'processing': 'Processing PDF...',
        'upload_success': '✅ Successfully uploaded: {}',
        'current_pdf': '📄 Current PDF: {}',
        'clear_button': '🗑️ Clear PDF and Start Over',
        'about_header': '### About',
        'about_text': "This app uses Google's Gemini AI with File Search to answer questions about your PDF documents.",
        'upload_prompt': '👈 Please upload a PDF file to start chatting',
        'chat_input': 'Ask a question about your PDF...',
        'thinking': 'Thinking...',
        'view_sources': '📚 View Sources',
        'error_response': "Sorry, I couldn't generate a response. Please try again.",
        'footer': 'Built with Streamlit and Google Gemini API',
        'error_api_key': 'GEMINI_API_KEY environment variable not set.',
        'error_pdf_extract': 'Error extracting text from PDF: {}',
        'error_save_file': 'Error saving file: {}',
        'error_create_store': 'Error creating file search store: {}',
        'error_upload_store': 'Error uploading file to store: {}',
        'error_query': 'Error querying file search: {}',
        'error_cleanup': 'Error cleaning up store: {}'
    },
    'ja': {
        'page_title': 'Gemini PDF チャット',
        'page_icon': '📄',
        'main_title': '📄 Gemini PDF チャット',
        'subtitle': 'PDFをアップロードして、Google Gemini AIを使って内容について質問できます',
        'language': '言語',
        'model': 'モデル',
        'sidebar_header': 'PDFアップロード',
        'choose_file': 'PDFファイルを選択',
        'processing': 'PDFを処理中...',
        'upload_success': '✅ アップロード成功: {}',
        'current_pdf': '📄 現在のPDF: {}',
        'clear_button': '🗑️ PDFをクリアして最初から',
        'about_header': '### 概要',
        'about_text': 'このアプリは、Google Gemini AIのFile Search機能を使用して、PDFドキュメントに関する質問に回答します。',
        'upload_prompt': '👈 チャットを開始するにはPDFファイルをアップロードしてください',
        'chat_input': 'PDFについて質問してください...',
        'thinking': '考え中...',
        'view_sources': '📚 ソースを表示',
        'error_response': '申し訳ございません。応答を生成できませんでした。もう一度お試しください。',
        'footer': 'Streamlit と Google Gemini API で構築',
        'error_api_key': 'GEMINI_API_KEY環境変数が設定されていません。',
        'error_pdf_extract': 'PDFからテキストを抽出中にエラー: {}',
        'error_save_file': 'ファイル保存中にエラー: {}',
        'error_create_store': 'ファイル検索ストア作成中にエラー: {}',
        'error_upload_store': 'ストアへのファイルアップロード中にエラー: {}',
        'error_query': 'ファイル検索クエリ中にエラー: {}',
        'error_cleanup': 'ストアのクリーンアップ中にエラー: {}'
    }
}

def get_text(key, lang='en'):
    """Get translated text for the given key and language"""
    return TRANSLATIONS.get(lang, TRANSLATIONS['en']).get(key, key)

# Helper Functions
def generate_random_id(length=8):
    """Generate a random ID for store naming"""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def wait_operation(client, op, sleep_sec=2, max_wait_sec=300):
    """Wait for Operations API to complete with timeout"""
    start = time.time()
    while not op.done:
        if time.time() - start > max_wait_sec:
            raise TimeoutError("Operation timed out.")
        time.sleep(sleep_sec)
        op = client.operations.get(op)
    return op

def extract_text_from_pdf(pdf_file, lang='en'):
    """Extract text content from uploaded PDF file"""
    try:
        pdf_reader = PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        st.error(get_text('error_pdf_extract', lang).format(e))
        return None

def save_uploaded_file(uploaded_file, lang='en'):
    """Save uploaded file to temporary location"""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            return tmp_file.name
    except Exception as e:
        st.error(get_text('error_save_file', lang).format(e))
        return None

def create_file_search_store(store_name, lang='en'):
    """Create a new File Search Store"""
    try:
        store = client.file_search_stores.create(
            config={'display_name': store_name}
        )
        return store
    except Exception as e:
        st.error(get_text('error_create_store', lang).format(e))
        return None

def upload_file_to_store(file_path, store_name, display_name, lang='en'):
    """Upload file to File Search Store"""
    try:
        upload_op = client.file_search_stores.upload_to_file_search_store(
            file=file_path,
            file_search_store_name=store_name,
            config={
                'display_name': display_name,
                'custom_metadata': [
                    {"key": "source", "string_value": "streamlit_upload"},
                    {"key": "timestamp", "numeric_value": int(time.time())}
                ]
            }
        )
        upload_op = wait_operation(client, upload_op)
        return upload_op.response
    except Exception as e:
        st.error(get_text('error_upload_store', lang).format(e))
        return None

def query_file_search(question, store_name, model, lang='en'):
    """Query the File Search Store with a question"""
    try:
        response = client.models.generate_content(
            model=model,
            contents=question,
            config=types.GenerateContentConfig(
                tools=[
                    types.Tool(
                        file_search=types.FileSearch(
                            file_search_store_names=[store_name]
                        )
                    )
                ]
            )
        )
        return response
    except Exception as e:
        st.error(get_text('error_query', lang).format(e))
        return None

def cleanup_store(store_name, lang='en'):
    """Delete the File Search Store"""
    try:
        client.file_search_stores.delete(
            name=store_name,
            config={'force': True}
        )
        return True
    except Exception as e:
        st.error(get_text('error_cleanup', lang).format(e))
        return False

# Streamlit UI
st.set_page_config(
    page_title="PDF Chat with Gemini",
    page_icon="📄",
    layout="wide"
)

# Initialize session state
if 'store_name' not in st.session_state:
    st.session_state.store_name = None
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'pdf_uploaded' not in st.session_state:
    st.session_state.pdf_uploaded = False
if 'pdf_name' not in st.session_state:
    st.session_state.pdf_name = None
if 'language' not in st.session_state:
    st.session_state.language = 'en'
if 'model' not in st.session_state:
    st.session_state.model = 'gemini-2.5-flash'

# Get current language
lang = st.session_state.language

# Check API key
if not api_key:
    st.error(get_text('error_api_key', lang))
    st.stop()

st.title(get_text('main_title', lang))
st.markdown(get_text('subtitle', lang))

# Sidebar for PDF upload
with st.sidebar:
    # Language selector
    lang_options = {'English': 'en', '日本語': 'ja'}
    selected_lang = st.selectbox(
        get_text('language', lang),
        options=list(lang_options.keys()),
        index=0 if lang == 'en' else 1
    )

    # Update language if changed
    new_lang = lang_options[selected_lang]
    if new_lang != st.session_state.language:
        st.session_state.language = new_lang
        st.rerun()

    lang = st.session_state.language

    # Model selector
    model_options = [
        'gemini-2.5-flash',
        'gemini-2.5-pro'
    ]
    selected_model = st.selectbox(
        get_text('model', lang),
        options=model_options,
        index=model_options.index(st.session_state.model)
    )
    st.session_state.model = selected_model

    st.markdown("---")
    st.header(get_text('sidebar_header', lang))

    uploaded_file = st.file_uploader(get_text('choose_file', lang), type=['pdf'])

    if uploaded_file is not None and not st.session_state.pdf_uploaded:
        with st.spinner(get_text('processing', lang)):
            # Save uploaded file
            temp_file_path = save_uploaded_file(uploaded_file, lang)

            if temp_file_path:
                # Create unique store name
                unique_id = generate_random_id()
                store_display_name = f'pdf-chat-store-{unique_id}'

                # Create file search store
                store = create_file_search_store(store_display_name, lang)

                if store:
                    # Upload file to store
                    file_display_name = Path(uploaded_file.name).stem
                    uploaded = upload_file_to_store(
                        temp_file_path,
                        store.name,
                        file_display_name,
                        lang
                    )

                    if uploaded:
                        st.session_state.store_name = store.name
                        st.session_state.pdf_uploaded = True
                        st.session_state.pdf_name = uploaded_file.name
                        st.success(get_text('upload_success', lang).format(uploaded_file.name))

                    # Clean up temporary file
                    try:
                        os.unlink(temp_file_path)
                    except:
                        pass

    if st.session_state.pdf_uploaded:
        st.info(get_text('current_pdf', lang).format(st.session_state.pdf_name))

        if st.button(get_text('clear_button', lang)):
            # Cleanup store
            if st.session_state.store_name:
                cleanup_store(st.session_state.store_name, lang)

            # Reset session state
            st.session_state.store_name = None
            st.session_state.chat_history = []
            st.session_state.pdf_uploaded = False
            st.session_state.pdf_name = None
            st.rerun()

    st.markdown("---")
    st.markdown(get_text('about_header', lang))
    st.markdown(get_text('about_text', lang))

# Main chat interface
if not st.session_state.pdf_uploaded:
    st.info(get_text('upload_prompt', lang))
else:
    # Display chat history
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat input
    if prompt := st.chat_input(get_text('chat_input', lang)):
        # Add user message to chat history
        st.session_state.chat_history.append({"role": "user", "content": prompt})

        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generate response
        with st.chat_message("assistant"):
            with st.spinner(get_text('thinking', lang)):
                response = query_file_search(prompt, st.session_state.store_name, st.session_state.model, lang)

                if response and response.text:
                    st.markdown(response.text)
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": response.text
                    })

                    # Show grounding metadata if available
                    try:
                        gm = response.candidates[0].grounding_metadata
                        if gm:
                            with st.expander(get_text('view_sources', lang)):
                                st.write(gm)
                    except:
                        pass
                else:
                    error_msg = get_text('error_response', lang)
                    st.error(error_msg)
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": error_msg
                    })

# Footer
st.markdown("---")
st.markdown(get_text('footer', lang))
