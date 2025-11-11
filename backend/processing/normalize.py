import re

def get_field(data, possible_keys, default=None):
    """Safely return the first matching key value from the document."""
    for key in possible_keys:
        if key in data and data[key] not in [None, ""]:
            return data[key]
    return default

def normalize_textract_resume(text):
    """Final version tuned for Jason Miller-style resumes."""
    data = {}

    # --- EMAIL ---
    email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    data["email"] = email_match.group(0) if email_match else None

    # --- NAME ---
    name_match = re.search(r"^\s*([A-Z][a-z]+(?: [A-Z][a-z]+)+)", text[:150])
    data["name"] = name_match.group(1).strip() if name_match else None

    # --- EDUCATION ---
    edu_match = re.search(r"\b(MBA|B\.?Tech|M\.?Tech|BSc|MSc|PhD|Bachelor|Master)\b", text, re.IGNORECASE)
    data["education"] = edu_match.group(1).upper() if edu_match else None

    # --- EXPERIENCE (numeric years like '5+ years') ---
    exp_match = re.search(r"(\d+)\+?\s*(?:years?|yrs?)", text, re.IGNORECASE)
    data["experience"] = float(exp_match.group(1)) if exp_match else 0.0

    # --- JOB ROLE ---
    role_match = re.search(
        r"\b(Operations Analyst|Software Engineer|Data Scientist|Machine Learning Engineer|UX Designer|Developer|Analyst|Manager)\b",
        text,
        re.IGNORECASE,
    )
    data["job_role"] = role_match.group(1).title() if role_match else None

    # --- SKILLS ---
    skills = re.findall(
        r"\b(Python|Java|C\+\+|SQL|TensorFlow|AWS|Docker|React|Node\.js|Machine Learning|Leadership|Data Analytics|Communication|Design|HTML|CSS|JavaScript)\b",
        text,
        re.IGNORECASE,
    )
    data["skills"] = sorted(list(set([s.title() for s in skills])))

    # --- CERTIFICATIONS ---
    certs = re.findall(
        r"\b(AWS Certified Solutions Architect|Google Cloud Fundamentals|Azure|Deep Learning|Certified|Scrum|PMP)\b",
        text,
        re.IGNORECASE,
    )
    data["certifications"] = sorted(list(set([c.title() for c in certs])))

    # --- PROJECTS ---
    proj_match = re.search(r"Projects\s*Completed[:\-]?\s*(\d+)", text, re.IGNORECASE)
    data["projects_count"] = int(proj_match.group(1)) if proj_match else 0

    # --- GENDER ---
    gender_match = re.search(r"Gender[:\-]?\s*(Male|Female|Other)", text, re.IGNORECASE)
    data["gender"] = gender_match.group(1).capitalize() if gender_match else ""

    # --- AGE ---
    age_match = re.search(r"Age[:\-]?\s*(\d{2})", text, re.IGNORECASE)
    data["age"] = int(age_match.group(1)) if age_match else None

    # --- DEFAULTS for other fields ---
    data.setdefault("recruiter_decision", None)
    data.setdefault("salary_expectation", 0)
    data.setdefault("ai_score", 0)

    return data
