import os
import shutil
import uuid
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment credentials 
load_dotenv()

# Import our custom architecture pipeline modules
from src.parser import extract_text_from_pdf, structure_extracted_text
from src.retriever import store_document_chunks
from src.generator import generate_grounded_draft
from src.learner import extract_and_save_rules
from src.prompts import (
    PARSER_PROMPT_TEMPLATE,
    GENERATOR_SYSTEM_PROMPT_TEMPLATE,
    GENERATOR_USER_PROMPT_TEMPLATE,
    LEARNER_PROMPT_TEMPLATE
)

app = FastAPI()

DEFAULT_TASK_PROMPT = "Generate a detailed case study draft of this legal document, dont leave any point."

class PreferenceFeedback(BaseModel):
    document_id: str
    document_type: str
    initial_draft: str
    operator_edit: str
    task_prompt: str

class QueryRequest(BaseModel):
    document_id: str
    document_type: str
    task_prompt: str

@app.get("/default-prompt")
async def get_default_prompt():
    return JSONResponse({
        "default_prompt": DEFAULT_TASK_PROMPT
    })

@app.post("/query")
async def query_document(req: QueryRequest):
    draft = generate_grounded_draft(req.document_id, req.document_type, req.task_prompt)
    return JSONResponse({
        "draft": draft
    })

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    raw_dir = os.path.join("data", "raw")
    os.makedirs(raw_dir, exist_ok=True)
    
    file_path = os.path.join(raw_dir, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    document_id = f"doc_{uuid.uuid4().hex[:8]}"
    
    try:
        if file.filename.lower().endswith('.pdf'):
            content_string = extract_text_from_pdf(file_path)
        else:
            with open(file_path, "r", encoding="utf-8") as f:
                content_string = f.read()
                
        structured_doc = structure_extracted_text(content_string)
    except ValueError as ve:
        return JSONResponse({"error": str(ve)}, status_code=400)
    
    store_document_chunks(
        doc_id=document_id,
        chunks=structured_doc.raw_content_chunks,
        document_type=structured_doc.document_type
    )
    
    return JSONResponse({
        "document_id": document_id,
        "document_type": structured_doc.document_type,
        "chunks": structured_doc.raw_content_chunks
    })

@app.post("/improve")
async def improve_draft(feedback: PreferenceFeedback):
    learned_rules = extract_and_save_rules(feedback.initial_draft, feedback.operator_edit, feedback.document_type)
    
    optimized_draft = generate_grounded_draft(
        feedback.document_id, 
        feedback.document_type, 
        feedback.task_prompt
    )
    
    return JSONResponse({
        "optimized_draft": optimized_draft,
        "learned_rules": learned_rules
    })

@app.get("/prompts")
async def get_prompts():
    return JSONResponse({
        "parser_prompt": PARSER_PROMPT_TEMPLATE,
        "generator_system_prompt": GENERATOR_SYSTEM_PROMPT_TEMPLATE,
        "generator_user_prompt": GENERATOR_USER_PROMPT_TEMPLATE,
        "learner_prompt": LEARNER_PROMPT_TEMPLATE
    })

# Serve the frontend directory
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
