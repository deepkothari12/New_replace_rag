import os
import streamlit as st
from google import genai
from google.genai import types
from dotenv import load_dotenv
import time
import tempfile

load_dotenv()
client = genai.Client()

st.title("Gemini File Comparison Chatbot")

st.subheader("Upload PDF A")
pdf_a = st.file_uploader("Upload first PDF", type=["pdf"], key="pdf_a")

st.subheader("Upload PDF B")
pdf_b = st.file_uploader("Upload second PDF", type=["pdf"], key="pdf_b")

def upload_pdf_to_store(uploaded_file, label):
    """Handles saving file → creating store → uploading."""
    if uploaded_file is None:
        return None

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(uploaded_file.read())
        temp_path = tmp.name

    st.write(f"{label} temp file saved:", temp_path)

    # Create File Search store
    store = client.file_search_stores.create()
    st.write(f"{label} store created:", store.name)

    # Upload PDF to store
    upload_op = client.file_search_stores.upload_to_file_search_store(
        file_search_store_name=store.name,
        file=temp_path,
    )

    attempt = 1
    while True:
        op = client.operations.get(upload_op)
        if op.error:
            st.error(f"{label} upload failed: {op.error}")
            return None
        if op.done:
            st.success(f"{label} upload complete.")
            return store.name
        time.sleep(min(30, 5 * attempt))
        attempt += 1


# we upload the both PDF which we tru to compared
store_a = upload_pdf_to_store(pdf_a, "PDF A") if pdf_a else None
store_b = upload_pdf_to_store(pdf_b, "PDF B") if pdf_b else None

# Only proceed when both are uploaded
if store_a and store_b:
    print("The both PDF is already uploaded" ,)
    st.subheader("Ask any comparison question")
    question = st.text_input("Example: 'What are the key differences between the two documents?'")

    if question:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=question,
            config=types.GenerateContentConfig(
                tools=[
                    types.Tool(
                        file_search=types.FileSearch(
                            file_search_store_names=[store_a, store_b]
                        )
                    )
                ]
            )
        )
        st.write("Answer:")
        st.write(response.text)
