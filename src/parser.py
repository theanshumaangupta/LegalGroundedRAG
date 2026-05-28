import os
from typing import List, Optional
from pypdf import PdfReader
from pydantic import BaseModel, Field
from groq import Groq
from src.prompts import PARSER_PROMPT_TEMPLATE

# 1. define json output layout
class ExtractedDocument(BaseModel):
    document_type: str = Field(description="e.g., NDA, Lease Agreement, Case Memo, Title Deed")
    parties: List[str] = Field(description="List of organizations, entities, or individuals involved")
    effective_date: Optional[str] = Field(description="Date of the document in standard format, if found")
    governing_law: Optional[str] = Field(description="The jurisdiction or state governing law mentioned")
    raw_content_chunks: List[str] = Field(default=[], description="Cleaned, paragraph-sized text chunks for downstream vector database use")

# 2. simple chunking to break long texts
def chunk_text(text: str, chunk_size: int = 100) -> List[str]:
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
    return chunks

# 3. main func for pdf text extraction
def extract_text_from_pdf(pdf_path: str) -> str:
    print(f"--- Starting extraction for: {os.path.basename(pdf_path)} ---")
    
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"The file path {pdf_path} does not exist.")
        
    reader = PdfReader(pdf_path)
    full_text = ""
    
    for page_num, page in enumerate(reader.pages):
        page_text = page.extract_text()
        
        # use readable text if it exists
        if page_text and len(page_text.strip()) > 50:
            full_text += page_text + "\n"
            
    # Check if we were able to extract meaningful text
    if not full_text or len(full_text.strip()) < 50:
        raise ValueError("The uploaded PDF does not contain extractable text (it appears to be a scanned image). Due to 48 hours time constraint, OCR is not supported. Please upload a standard text-based PDF.")
                
    return full_text

# 4. turn raw text into json using groq
def structure_extracted_text(raw_text: str) -> ExtractedDocument:
    """
    Sends the extracted raw text to the Groq API (Llama 3).
    Forces the model to accurately return a JSON object matching the Pydantic schema.
    """
    client = Groq()
    chunks = chunk_text(raw_text)
    
    prompt = PARSER_PROMPT_TEMPLATE.format(raw_text=raw_text[:8000])
    
    try:
        response = client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        
        json_str = response.choices[0].message.content
        structured_data = ExtractedDocument.model_validate_json(json_str)
        structured_data.raw_content_chunks = chunks
        
        return structured_data

    except Exception as e:
        print(f"Failed to structure document via Groq API: {e}")
        return ExtractedDocument(
            document_type="Unknown / Parsing Error",
            parties=[],
            effective_date=None,
            governing_law=None,
            raw_content_chunks=chunks
        )