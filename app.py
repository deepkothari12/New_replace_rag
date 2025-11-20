import os
import streamlit as st
from google import genai
from google.genai import types
from dotenv import load_dotenv
import time
import tempfile

load_dotenv()
client = genai.Client()

st.title("Gemini File Search Chatbot")
uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])

if uploaded_file is not None:
    # 1) Save uploaded file to a temp path
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(uploaded_file.read())
        temp_path = tmp.name

    st.write(f"Saved temp file: {temp_path}")

    store = client.file_search_stores.create()
    st.write("Store:", store.name)

    
    upload_op = client.file_search_stores.upload_to_file_search_store(
        file_search_store_name=store.name,
        file=temp_path,  #  NOT a tuple
    )   

    attempt = 1
    while True:
        op = client.operations.get(upload_op)
        if op.error:
            st.error(f"Upload failed: {op.error}")
            break
        if op.done:
            st.success("Upload complete.")
            break
        time.sleep(min(30, 5 * attempt))
        attempt += 1    

    
    question = st.text_input("Ask something about this PDF")
    if question:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=question,
            config = types.GenerateContentConfig(
                tools=[types.Tool(
                    file_search=types.FileSearch(
                        file_search_store_names=[store.name]
                    )
                )]
            )
        )
        st.write("Answer:")
        st.write(response.text)
