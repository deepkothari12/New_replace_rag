import os
import time
import tempfile
import shutil
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai
from google.genai import types


load_dotenv()
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # dev only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    client = genai.Client()
except Exception as e:
    print("Gemini init failed:", e)
    client = None


class DualChatRequest(BaseModel):
    message: str
    storeIdA: str
    storeIdB: str
    filenameA: str
    filenameB: str


async def upload_single_pdf(file: UploadFile, label: str):
    if not client:
        raise HTTPException(500, "Gemini client not initialized")

    if not file.filename:
        raise HTTPException(400, "Invalid file")

    # size check
    contents = await file.read()
    if len(contents) > 50 * 1024 * 1024:
        raise HTTPException(400, f"{label} exceeds 50MB")

    await file.seek(0)

    tmpdir = tempfile.mkdtemp()
    temp_path = os.path.join(tmpdir, file.filename)

    try:
        with open(temp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        store = client.file_search_stores.create()

        upload_op = client.file_search_stores.upload_to_file_search_store(
            file_search_store_name=store.name,
            file=temp_path,
        )

        # Poll upload
        for _ in range(60):
            op = client.operations.get(upload_op)
            if op.error:
                raise HTTPException(500, op.error)
            if op.done:
                return store.name, file.filename
            time.sleep(1)

        raise HTTPException(504, "Upload timeout")

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        
@app.get("/")
def home():
    return {
        "Api" : "Bhagg Rahi hai"
    }
@app.post("/upload-dual")
async def upload_dual(fileA: UploadFile = File(...), fileB: UploadFile = File(...)):
    storeA, nameA = await upload_single_pdf(fileA, "PDF A")
    storeB, nameB = await upload_single_pdf(fileB, "PDF B")

    return {
        "storeIdA": storeA,
        "storeIdB": storeB,
        "filenameA": nameA,
        "filenameB": nameB,
    }



@app.post("/chat-dual")
async def chat_dual(req: DualChatRequest):
    if not client:
        raise HTTPException(500, "Gemini client not initialized")

    def stream_generator():
        system_prompt = f"""
            You are an expert data analyst specializing in document comparison.

            Document A: "{req.filenameA}"
            Document B: "{req.filenameB}"

            RULES:
            - Use only these names
            - Never mention tmp files
            - Be structured, precise, factual
            - used plain and deceent text not used mardown as well as any symbols

            Compare content, structure, themes, and differences.
        """

        full_prompt = f"{system_prompt}\n\nUser question: {req.message}"

        try:
            stream = client.models.generate_content_stream(
                model="gemini-2.5-flash",
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    tools=[
                        types.Tool(
                            file_search=types.FileSearch(
                                file_search_store_names=[req.storeIdA, req.storeIdB]
                            )
                        )
                    ],
                    temperature=0.6,
                ),
            )

            for chunk in stream:
                if chunk.text:
                    yield chunk.text

        except Exception as e:
            yield f"\n[ERROR] {str(e)}"

    return StreamingResponse(stream_generator(), media_type="text/plain")



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=4000)
