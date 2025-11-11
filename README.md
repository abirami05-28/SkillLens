
# SkillLens: AI-Powered Resume Decoder

## Overview

**SkillLens** is a cloud-enabled, AI-powered recruitment intelligence platform designed to automate and optimize the hiring process. It leverages **Natural Language Processing (NLP)**, **Machine Learning (ML)**, and **Cloud Computing** to analyze resumes, rank candidates, and provide data-driven hiring analytics through an interactive web interface.

By combining semantic analysis, bias evaluation, and automation, SkillLens enables recruiters to make faster, fairer, and more informed hiring decisions.

---

## Key Features

* **AI-Based Resume Parsing** using AWS Textract and SpaCy
* **Semantic Role Matching** using Sentence-BERT embeddings
* **Hybrid Suitability Scoring** (Cosine, Jaccard, and LightGBM)
* **Bias and Fairness Evaluation** via IBM AIF360
* **Interactive Analytics Dashboard** with skill clusters and hiring trends
* **Interview Scheduling Assistant** integrated with Google Calendar API
* **JWT Authentication** for secure recruiter access
* **Cloud-Native Design** using AWS Lambda, MongoDB Atlas, and FastAPI

---

## System Architecture

The SkillLens architecture consists of:

1. **Frontend** – HTML, CSS, and JavaScript for visualization and interaction.
2. **Backend** – FastAPI for API orchestration and ML integration.
3. **Database** – MongoDB Atlas for scalable and flexible data storage.
4. **Cloud Services** – AWS Textract for resume extraction and S3 for file storage.
5. **External APIs** – Google Calendar API for automated scheduling.

---

## Modules

| Module                                  | Description                                                                                                           |
| --------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| **Resume Preprocessing & Extraction**   | Extracts structured data such as skills, education, and experience from resumes using AWS Textract and NLP pipelines. |
| **Candidate Profiling & Matching**      | Computes semantic similarity between candidates and job roles using SBERT embeddings and hybrid scoring.              |
| **Suitability Scoring Engine**          | Combines Cosine, Jaccard, and LightGBM model scores to produce a final suitability score.                             |
| **Bias & Fairness Evaluation**          | Uses IBM AIF360 toolkit to detect and mitigate bias in model outcomes.                                                |
| **Analytics & Visualization Dashboard** | Displays skill trends, clusters, and hiring funnel data using Plotly and chart libraries.                             |
| **Recruiter Interface**                 | Provides recruiters with secure login, candidate management, and profile updates.                                     |
| **Interview Scheduler**                 | Automates scheduling through Google Calendar API integration.                                                         |

---

## Technologies Used

### **Frontend**

* HTML5, CSS3, JavaScript (Vanilla)
* Plotly.js and Chart.js for data visualization

### **Backend**

* FastAPI (Python)
* Motor (Async MongoDB driver)
* Sentence-BERT (SBERT)
* LightGBM (ML model for ranking)
* IBM AIF360 (Fairness analysis)
* Google Calendar API
* AWS Textract & S3
* JWT Authentication (PyJWT)
* Bcrypt for password hashing

### **Database**

* MongoDB Atlas (Cloud-hosted NoSQL)

### **Cloud & API Services**
* AWS Textract – Resume text extraction
* AWS S3 – Resume file storage
* Google Calendar API – Interview scheduling
* MongoDB Atlas – Cloud-hosted NoSQL database


---

## Project Setup Guide

### 1. Prerequisites

Before running the project, ensure you have the following installed:

* Python 3.10 or above
* Node.js (optional for frontend live server)
* MongoDB Atlas account
* AWS account with Textract and S3 configured
* Google Cloud credentials for Calendar API
* GitHub account (for code deployment)

---

### 2. Clone the Repository

```bash
git clone https://github.com/yourusername/SkillLens.git
cd SkillLens
```

---

### 3. Backend Setup

#### Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
```

#### Install dependencies:

```bash
pip install -r requirements.txt
```

#### Environment Variables:

Create a `.env` file inside the backend root directory with the following content:

```bash
MONGO_URI="your_mongodb_connection_string"
MONGO_DB="skilllens"
JWT_SECRET="your_jwt_secret"

HF_API_KEY="your_huggingface_api_key"

GOOGLE_CLIENT_ID="your_google_calendar_client_id"
GOOGLE_CLIENT_SECRET="your_google_calendar_client_secret"
GOOGLE_REDIRECT_URI="http://127.0.0.1:8000/calendar/oauth2callback"

AWS_ACCESS_KEY_ID="your_aws_key"
AWS_SECRET_ACCESS_KEY="your_aws_secret"
AWS_REGION="ap-south-1"
S3_BUCKET="your_s3_bucket_name"
```
# (Optional) Test MongoDB connection
curl http://127.0.0.1:8000/test_mongo

#### Start the backend server:

```bash
uvicorn main:app --reload
```

Your backend should now be running at:

```
http://127.0.0.1:8000
```

---

### 4. Frontend Setup

#### Run the frontend locally:

Open the `frontend` folder in VS Code and start a local server (you can use the Live Server extension or Python’s built-in one):

```bash
python -m http.server 5500
```

Then open:

```
http://127.0.0.1:5500/frontend/
```

The default entry page is `signin.html`.

---

### 5. Connecting Backend and Frontend

In the file `frontend/js/config.js`, ensure the API base URL matches your backend address:

```js
const API_BASE = "http://127.0.0.1:8000";
```

---

### 6. Running the Application

1. Start the backend using:

   ```bash
   uvicorn main:app --reload
   ```
2. Start the frontend (e.g., using Live Server).
3. Sign up as a new user or log in via the **Sign In** page.
4. Navigate to the dashboard (`userdash.html`) to access modules such as:

   * Resume Parsing
   * Hiring Analysis
   * Candidate Ranking
   * Interview Scheduler
   * My Account
> Note: The backend (FastAPI) and frontend (local server) must both be running simultaneously for the web app to function correctly.


---

## Usage Flow

1. **Recruiter logs in** via JWT-secured authentication.
2. **Resumes are uploaded** and parsed automatically through AWS Textract.
3. **Candidates are ranked** using hybrid ML scoring (SBERT + LightGBM).
4. **Bias evaluation** ensures fairness using AIF360 metrics.
5. **Results and analytics** are visualized on the Hiring Dashboard.
6. **Interviews are scheduled** through Google Calendar API integration.

---

## File Structure

```
SkillLens/
├── backend/
│   ├── main.py
│   ├── db/
│   │   └── mongo.py
│   ├── auth/
│   │   └── routes.py
│   ├── calendar_api/
│   │   └── routes.py
│   ├── analytics/
│   │   ├── skill_rules.py
│   │   ├── cluster_candidates.py
│   │   ├── fairness_eval.py
│   │   ├── bias_summary.py
│   │   └── lightgbm_model.py
│   ├── resume/
│   │   └── routes.py
│   └── processing/
│       ├── hf_router.py
│       ├── similarity.py
│       └── normalize.py
│
├── frontend/
│   ├── index2.html
│   ├── signin.html
│   ├── signup.html
│   ├── userdash.html
│   ├── my_acc.html
│   ├── hiring_analysis.html
│   ├── candidate_ranking.html
│   ├── interview_schedule.html
│   └── js/
│       ├── config.js
│       └── auth.js
│
└── requirements.txt
```

---

## Future Enhancements

* Deploy the entire system using **AWS Lambda + API Gateway**.
* Integrate **real-time notifications** through Gmail API.
* Enhance ML pipeline with **transformer-based fairness auditing**.
* Add **role-based access control (RBAC)** for multi-user organizations.
* Enable **CSV job uploads** directly from the dashboard.

---

## Contributors

| Name                      | Registration No. | Role                           |
| ------------------------- | ---------------- | ------------------------------ |
| Abirami Manoj             | 23MID0048        | Backend & Frontend Integration |
| Vaishnavi Vijay Balkawade | 23MID0074        | Data & Model Design            |
| Divya Chandrasekaran      | 23MID0099        | Cloud Infrastructure & UI      |

---

## Supervisor

**Prof. Krishnaraj N**
Course: Business Intelligence
Vellore Institute of Technology, Vellore

---

## License

This project is for **academic and educational purposes only** under the VIT Business Intelligence course.

External use, deployment, or reproduction requires permission from the authors.

---


