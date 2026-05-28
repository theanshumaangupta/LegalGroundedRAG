import os
import json
from groq import Groq
from src.prompts import LEARNER_PROMPT_TEMPLATE

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREFERENCES_PATH = os.path.join(PROJECT_ROOT, "data", "operator_preferences.json")

def extract_and_save_rules(original_draft: str, edited_draft: str, document_type: str):
    """
    Compares the original AI output against the operator's final edits.
    Asks Groq (Llama 3) to extract actionable, reusable formatting and stylistic rules,
    and updates the persistent local preference database.
    """
    client = Groq()
    
    prompt = LEARNER_PROMPT_TEMPLATE.format(
        original_draft=original_draft,
        edited_draft=edited_draft
    )
    
    print("Analyzing operator changes to learn preferences...")
    try:
        response = client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        json_str = response.choices[0].message.content
        print(json_str.strip())
        
        parsed = json.loads(json_str)
        new_rules = parsed.get("rules", [])
        if not isinstance(new_rules, list):
            new_rules = [str(new_rules)]
    except Exception as e:
        print(f"Failed to learn preferences due to API error (e.g., rate limit): {e}")
        return [] # Gracefully skip learning this time
        
    # load old preferences or start over
    preferences = {}
    if os.path.exists(PREFERENCES_PATH):
        try:
            with open(PREFERENCES_PATH, "r", encoding="utf-8") as f:
                preferences = json.load(f)
        except Exception:
            preferences = {}
            
    # init doc type cluster if missing
    if document_type not in preferences:
        preferences[document_type] = []
        
    # add new rules without duplicating
    for rule in new_rules:
        if rule not in preferences[document_type]:
            preferences[document_type].append(rule)
            
    # save updated preferences to file
    with open(PREFERENCES_PATH, "w", encoding="utf-8") as f:
        json.dump(preferences, f, indent=4)
        
    print(f"[Learning Loop] Successfully updated '{document_type}' stylistic preferences with {len(new_rules)} new rules.")
    return new_rules

def load_document_preferences(document_type: str) -> str:
    """
    Reads the operator_preferences.json file and returns a formatted string instruction
    block to append directly to generation system prompts.
    """
    if not os.path.exists(PREFERENCES_PATH):
        return ""
        
    try:
        with open(PREFERENCES_PATH, "r", encoding="utf-8") as f:
            preferences = json.load(f)
            
        rules = preferences.get(document_type, [])
        if not rules:
            return ""
            
        instruction_block = "\nADHERE STRICTLY TO THESE HISTORICAL OPERATOR PREFERENCES LEARNED FROM PAST EDITS:\n"
        for idx, rule in enumerate(rules):
            instruction_block += f"- {rule}\n"
        return instruction_block
    except Exception:
        return ""