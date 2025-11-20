import time
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
client = genai.Client()

# Create store (new mini vector DB)
store = client.file_search_stores.create()
print("Store:", store.name)

# Upload PDF
upload_op = client.file_search_stores.upload_to_file_search_store(
    file_search_store_name=store.name,
    file='D:\\VsCode\\New_repalce_rag\\Data\\Medtronic_VLOC-product-catalogue.pdf',
)

# Safe polling loop
print("TYPE:", type(upload_op))
print("NAME:", upload_op.name)

attempt = 1
while True:
    #So you must give Google the string ID, not the object bc it chack with that 
    print("Polling name:", upload_op.name)
    op = client.operations.get(upload_op)
    # print()
    # check for upload failure
    if op.error:
        print("Operation error:", op.error)
        raise RuntimeError(f"Upload failed: {op.error}")

    # upload finished?
    if op.done:
        print("Upload complete.")
        break

    # wait with exponential backoff
    time.sleep(min(30, 5 * attempt))
    attempt += 1
    print(attempt)

# Use File Search Store
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents='Can you tell me about Absorbable Wound Closure Devices in the document?',
    config=types.GenerateContentConfig(
        tools=[
            types.Tool(
                file_search=types.FileSearch(
                    file_search_store_names=[store.name]
                )
            )
        ]
    )
)

print("Summary:\n", response.text)

# Grounding sources
grounding = response.candidates[0].grounding_metadata
if not grounding:
    print("No grounding sources found")
else:
    sources = {c.retrieved_context.title for c in grounding.grounding_chunks}
    print("Sources:", *sources)
