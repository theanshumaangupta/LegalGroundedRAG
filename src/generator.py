from groq import Groq
from src.retriever import retrieve_relevant_evidence
from src.learner import load_document_preferences
from src.prompts import GENERATOR_SYSTEM_PROMPT_TEMPLATE, GENERATOR_USER_PROMPT_TEMPLATE

def generate_grounded_draft(document_id: str, document_type: str, task_instruction: str) -> str:
    """
    Retrieves background evidence from ChromaDB, constructs a grounded system prompt,
    and asks Groq (Llama 3) to output a structured draft complete with text source citations.
    """
    # 1. get relevant chunks from db
    print(f"Retrieving background evidence from vector index for task: '{task_instruction}'")
    matched_chunks = retrieve_relevant_evidence(task_instruction, n_results=7, document_id=document_id)
    
    if not matched_chunks:
        return "Error: No relevant source document chunks found in database to ground this draft."
        
    # 2. format evidence into prompt context
    context_str = ""
    for chunk in matched_chunks:
        context_str += f"--- START EVIDENCE BACKGROUND CHUNK [{chunk['id']}] ---\n"
        context_str += f"{chunk['text']}\n"
        context_str += f"--- END EVIDENCE BACKGROUND CHUNK [{chunk['id']}] ---\n\n"
        
    # load user preferences
    user_style_rules = load_document_preferences(document_type)
        
    # 3. setup system rules for llama
    system_instruction = GENERATOR_SYSTEM_PROMPT_TEMPLATE
    
    prompt = GENERATOR_USER_PROMPT_TEMPLATE.format(
        task_instruction=task_instruction,
        context_str=context_str,
        user_style_rules=user_style_rules
    )
    
    # 4. init groq and run it
    client = Groq()
    
    print("Generating grounded draft via Groq cloud services...")
    try:
        response = client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1
        )
        return response.choices[0].message.content
    except Exception as e:
        if "429" in str(e) or "rate_limit" in str(e).lower():
            return "ERROR: Groq API rate limit exceeded (429). Please wait about 15-30 seconds before submitting another request."
        return f"ERROR: Failed to generate draft due to API error: {e}"