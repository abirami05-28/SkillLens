import re
import spacy

# Load English NER model (small one is fine for now)
nlp = spacy.load("en_core_web_sm")

def extract_text_fields(doc: dict) -> str:
    """
    Combine candidate fields into one text blob for NLP processing.
    """
    fields = []
    for key in ["name", "skills", "education", "certifications", "job_role"]:
        val = doc.get(key)
        if val:
            if isinstance(val, list):
                fields.extend(val)
            else:
                fields.append(str(val))
    return " ".join(fields)
# Extract named entities using SpaCy
def extract_entities(text: str):
    doc = nlp(text)
    entities = []
    for ent in doc.ents:
        entities.append({"text": ent.text, "label": ent.label_})
    return entities

# Extract years of experience using regex (looks for "X years")
def parse_years_of_experience(text: str):
    match = re.search(r"(\d+)\s+years", text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return 0

# Extract email addresses using regex
def extract_emails(text: str):
    emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}", text)
    return emails

# Extract phone numbers using regex
def extract_phone_numbers(text: str):
    phones = re.findall(r"\+?\d[\d -]{8,}\d", text)
    return phones
