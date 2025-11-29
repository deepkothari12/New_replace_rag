## Main - File ##
import os
import streamlit as st
from google import genai
from google.genai import types
from dotenv import load_dotenv
import time
import tempfile
import shutil   
# Load environment variables from .env file

load_dotenv()

try:       
    client = genai.Client()
except Exception as e:
    st.error(f"Failed to initialize Gemini client: {str(e)}")
    st.stop()

st.title("File Comparison Chatbot")
st.text("Upload two PDF documents of 40 MBs")

st.subheader("Upload PDF A")
pdf_a = st.file_uploader("Upload first PDF", type=["pdf"], key="pdf_a")

st.subheader("Upload PDF B")
pdf_b = st.file_uploader("Upload second PDF", type=["pdf"], key="pdf_b")


def upload_pdf_to_store(uploaded_file, label):
    """
    Handles saving file → creating store → uploading with error handling.
    Uses the ORIGINAL file name so Gemini doesn't see random tmp names.
    """
    if uploaded_file is None:
        return None         

    tmpdir = None
    temp_path = None
    store_name = None 

    try:
        #  size check
        file_size = uploaded_file.size
        if file_size > 50 * 1024 * 1024:  # 50MB
            st.error(f"{label}: File size exceeds 50MB limit")
            return None

        # Create a temp director y and save with ORIGINAL filename
        tmpdir = tempfile.mkdtemp()
        original_name = uploaded_file.name or f"{label}.pdf"
        temp_path = os.path.join(tmpdir, original_name)

        with open(temp_path, "wb") as f:
            # getbuffer() used for avoids re-reading multiple times
            f.write(uploaded_file.getbuffer())

        st.info(f"{label}: Temporary file created as {original_name}")
 
        # Create File Search store
        try:
            store = client.file_search_stores.create()
            store_name = store.name
            st.info(f"{label}: Storage created successfully ({store_name})")
        except Exception as e:
            st.error(f"{label}: Failed to create storage - {str(e)}")
            return None

        # Upload PDF to store   
        try:
            upload_op = client.file_search_stores.upload_to_file_search_store(
                file_search_store_name=store_name,
                file=temp_path,  # path with the REAL filename
            )
    
        except Exception as e:
            st.error(f"{label}: Failed to initiate upload - {str(e)}")
            return None
                
        # Poll for upload completion
        attempt = 1
        max_attempts = 120  # Prevent infinite loop 

        with st.spinner(f"Uploading {label}..."):
            while attempt <= max_attempts:
                try:
                    op = client.operations.get(upload_op)

                    if op.error:
                        st.error(f"{label}: Upload failed - {op.error}")
                        return None

                    if op.done:
                        st.success(f"{label}: Upload complete ")
                        return store_name

                    time.sleep(min(30, 5 * attempt))
                    attempt += 1

                except Exception as e:
                    st.error(f"{label}: Error checking upload status - {str(e)}")
                    return None

        st.error(f"{label}: Upload timeout after {max_attempts} attempts")
        return None

    except Exception as e:
        st.error(f"{label}: Unexpected error - {str(e)}")
        return None

    finally:
        # Clean up temp file + dir
        try:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
            if tmpdir and os.path.exists(tmpdir):
                shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception as e:
            st.warning(f"{label}: Could not fully delete temp files - {str(e)}")

# Initialize session state for store names
if 'store_a' not in st.session_state:
    st.session_state.store_a = None
if 'store_b' not in st.session_state:
    st.session_state.store_b = None

# Upload PDFs only if they exist and haven't been uploaded yet
if pdf_a and st.session_state.store_a is None:
    st.session_state.store_a = upload_pdf_to_store(pdf_a, "PDF A")

if pdf_b and st.session_state.store_b is None:
    st.session_state.store_b = upload_pdf_to_store(pdf_b, "PDF B") 


# Only proceed when both PDFs are uploaded successfully
if st.session_state.store_a and st.session_state.store_b:
    st.success("Both PDFs uploaded successfully! ")

    # Human-friendly names for the prompt
    doc_a_name = pdf_a.name if pdf_a else "Document A"
    doc_b_name = pdf_b.name if pdf_b else "Document B"

    st.subheader("Ask any comparison question")
    question = st.text_input(
        "Question:",
        placeholder=f"Example: 'What are the key differences between {doc_a_name} and {doc_b_name}?'"
    )

    if st.button("Get Answer") or question:
        if not question:
            st.warning("Please enter a question")
        else:
            try:
                system_prompt = f"""
                You are an expert data analyst specializing in document comparison and analysis.

                The two documents are:
                - Document A: "{doc_a_name}"
                - Document B: "{doc_b_name}"

                VERY IMPORTANT:
                - Always refer to them using these names.
                - Do NOT mention any internal filenames or temporary paths such as "tmpxxxx.pdf".

                Your task is to:
                - Carefully analyze both documents.
                - Provide detailed, accurate comparisons.
                - Highlight key differences and similarities.
                - Use specific examples from the documents when relevant.
                - Structure your response in a clear, organized manner.
                - Be objective and precise in your analysis.

                When comparing documents, focus on:
                - Content differences
                - Structural variations
                - Key themes and topics
                - Data or figures that differ
                - Any missing or additional information
                """
            
                full_prompt = f"{system_prompt}\n\nUser Question: {question}"

                with st.spinner("Analyzing documents..."):
                    response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=full_prompt,
                        config=types.GenerateContentConfig(
                            
                            tools=[
                                types.Tool(
                                    file_search=types.FileSearch(
                                            file_search_store_names=[
                                            st.session_state.store_a,
                                            st.session_state.store_b
                                        ]
                                    )
                                )
                            ],
                            temperature=0.4,
                        )
                    )

                st.subheader("Answer:")
                st.write(response.text)

            except AttributeError as e:
                st.error(
                    "API response error: The response object doesn't have "
                    f"expected attributes - {str(e)}"
                )
            except Exception as e:
                st.error(f"Error generating response: {str(e)}")
                st.info("Please try rephrasing your question or check your API configuration")

elif pdf_a or pdf_b:
    if pdf_a and not st.session_state.store_a:
        st.warning("PDF A is being processed or failed to upload")
    if pdf_b and not st.session_state.store_b:
        st.warning("PDF B is being processed or failed to upload")
else:
    st.info("Please upload both PDF files to begin")

# Add a reset button
if st.session_state.store_a or st.session_state.store_b:
    if st.button("Reset and Upload New PDFs"):
        st.session_state.store_a = None
        st.session_state.store_b = None
        st.rerun()
