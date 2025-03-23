import os
import sqlite3
import fitz  # PyMuPDF for PDF extraction
import json  # Add this import to parse JSON skill lists
import pytesseract  # OCR for images
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from PIL import Image
import docx
import spacy
from spacy.matcher import PhraseMatcher
from flask import Flask, render_template

# Load NLP model
nlp = spacy.load("en_core_web_sm")

# Initialize Flask app
app = Flask(__name__,  template_folder="templates")
app.config['UPLOAD_FOLDER'] = "uploads"
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Allowed file extensions
ALLOWED_EXTENSIONS = {"pdf", "docx", "png", "jpg", "jpeg"}

# Path to SQLite3 database
DATABASE_PATH = r"D:\upload_resume\backend\database.db"  # Use raw string format

# Comprehensive list of skills
SKILLS = [
    "Python", "Java", "JavaScript", "C++", "C#", "Ruby", "Go", "Swift", "Kotlin", "TypeScript", "PHP", "Linux",
    "Windows", "MATLAB", "Power Systems", "HTML", "CSS", "React", "Angular", "Vue.js", "Node.js", "Django", 
    "Flask", "Spring Boot", "Machine Learning", "Deep Learning", "Data Science", "TensorFlow", "PyTorch", "Keras",
    "Pandas", "NumPy", "Scikit-Learn", "R", "Matplotlib", "Seaborn", "OpenAI API", "Natural Language Processing", 
    "Big Data", "SQL", "PostgreSQL", "MongoDB", "Firebase", "AWS", "Azure", "Google Cloud", "Docker", "Kubernetes",
    "Ethical Hacking", "Penetration Testing", "Cryptography", "Network Security", "SOC Analyst", "Malware Analysis",
    "CI/CD", "Jenkins", "Terraform", "Ansible", "Git", "GitHub Actions", "Bash Scripting", "Agile", "Scrum", 
    "Kanban", "JIRA", "Trello", "Confluence", "PCB"
]

# Initialize PhraseMatcher for skill extraction
phrase_matcher = PhraseMatcher(nlp.vocab)
patterns = [nlp(skill) for skill in SKILLS]
phrase_matcher.add("SKILLS", None, *patterns)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(filepath):
    text = ""
    doc = fitz.open(filepath)
    for page in doc:
        text += page.get_text("text")
    return text

def extract_text_from_docx(filepath):
    doc = docx.Document(filepath)
    return "\n".join([para.text for para in doc.paragraphs])

def extract_text_from_image(filepath):
    image = Image.open(filepath)
    return pytesseract.image_to_string(image)

def extract_resume_text(filepath, ext):
    if ext == "pdf":
        return extract_text_from_pdf(filepath)
    elif ext == "docx":
        return extract_text_from_docx(filepath)
    elif ext in {"png", "jpg", "jpeg"}:
        return extract_text_from_image(filepath)
    return ""

def extract_skills(text):
    doc = nlp(text)
    skills = set()
    
    # Use PhraseMatcher to find skills
    matches = phrase_matcher(doc)
    for match_id, start, end in matches:
        skill = doc[start:end].text
        skills.add(skill)
    
    return list(skills)


def find_jobs_from_database(skills):
    if not skills:
        print("No skills extracted, skipping job search.")
        return []

    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # Fetch jobs from the database
        cursor.execute("SELECT id, title, company, location, description, required_skills, salary, date_posted FROM job")
        jobs = cursor.fetchall()
        conn.close()

        print("\n📌 All Jobs in Database:")
        for job in jobs:
            print(f"ID: {job[0]}, Title: {job[1]}, Required Skills: {job[5]}")

        # Convert extracted skills to lowercase for case-insensitive matching
        skills = [skill.lower().strip() for skill in skills]
        print("\nExtracted Skills (Cleaned):", skills)  # Debugging skills list

        matched_jobs = []
        for job in jobs:
            try:
                #  Properly parse JSON skill list
                job_skills = json.loads(job[5])  # Convert string to list
                job_skills = [skill.lower().strip() for skill in job_skills]  # Normalize
            except json.JSONDecodeError:
                print(f"Warning: Job skills format issue for job ID {job[0]}")
                continue  # Skip this job if parsing fails

            print(f"\n Checking Job: {job[1]}")
            print(f" - Job Skills (DB): {job_skills}")
            print(f" - Candidate Skills: {skills}")

            # Check if at least one skill matches
            if any(skill in job_skills for skill in skills):
                print(" Match Found!")
                matched_jobs.append({
                    "id": job[0],
                    "title": job[1],
                    "company": job[2],
                    "location": job[3],
                    "description": job[4],
                    "required_skills": job_skills,  #  Show as a proper list
                    "salary": job[6],
                    "date_posted": job[7]
                })
            else:
                print(" No Match - Check Formatting in DB")

        print("\n Final Matched Jobs:", matched_jobs)  # Debugging output
        return matched_jobs
    
    except Exception as e:
        print("Database Error:", e)
        return []
    
@app.route("/")
def home():
    return render_template("index.html")  # This serves index.html from 'templates' folder

@app.route("/search", methods=["GET"])
def search_jobs():
    skills = request.args.get("skills", "")  # Get skills from query parameters
    
    
    skills_list = [skill.strip() for skill in skills.split(",")]  # Convert to list
    jobs = find_jobs_from_database(skills_list)  # Find matching jobs from DB

    # Ensure DATABASE_PATH contains job data (replace with actual dataset)
    return jsonify({"job_recommendations": jobs})  # Return JSON response



@app.route("/upload", methods=["POST"])
def upload_resume():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "" or not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type"}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    ext = filename.rsplit('.', 1)[1].lower()
    text = extract_resume_text(filepath, ext)
    skills = extract_skills(text)
    jobs = find_jobs_from_database(skills)

    return jsonify({
        "extracted_skills": skills,
        "job_recommendations": jobs
    })

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)

