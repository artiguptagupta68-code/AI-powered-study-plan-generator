# app.py

import streamlit as st
import os
import zipfile
import gdown
import fitz  # PyMuPDF
from collections import defaultdict
from datetime import datetime, timedelta
import json

# -----------------------------
# 1️⃣ Configuration
# -----------------------------
DRIVE_FILE_ID = "1IRP5upBPCua57WmoEfjn9t6YJQq0_yGB"  # Google Drive file ID for syllabus ZIP
LOCAL_ZIP = "syllabus.zip"
EXTRACT_DIR = "syllabus_data"
JSON_OUTPUT = "syllabus.json"

# -----------------------------
# 2️⃣ Download ZIP from Google Drive
# -----------------------------
if not os.path.exists(LOCAL_ZIP):
    gdown.download(f"https://drive.google.com/uc?id={DRIVE_FILE_ID}", LOCAL_ZIP, quiet=False)

os.makedirs(EXTRACT_DIR, exist_ok=True)
with zipfile.ZipFile(LOCAL_ZIP, 'r') as zip_ref:
    zip_ref.extractall(EXTRACT_DIR)

# -----------------------------
# 3️⃣ PDF reading function
# -----------------------------
def read_pdf_lines(pdf_path):
    doc = fitz.open(pdf_path)
    lines = []
    for page in doc:
        text = page.get_text("text")
        for line in text.split("\n"):
            line = line.strip()
            if line:
                lines.append(line)
    return lines

# -----------------------------
# 4️⃣ Detect exam and GATE branch
# -----------------------------
def detect_exam_and_branch(lines):
    text = " ".join(lines[:300]).upper()
    if "GATE" in text:
        exam = "GATE"
        branch = None
        for line in lines[:100]:
            clean = line.strip()
            if clean.isupper() and len(clean.split()) <= 5 and "GATE" not in clean:
                branch = clean.title()
                break
        if not branch:
            branch = "Unknown Branch"
        return exam, branch
    elif any(k in text for k in ["SSC", "CGL"]):
        return "SSC", "General"
    elif any(k in text for k in ["UPSC", "UNION PUBLIC SERVICE COMMISSION"]):
        return "UPSC", "General"
    else:
        return None, None

# -----------------------------
# 5️⃣ Parse PDFs into JSON
# -----------------------------
def pdfs_to_json(pdf_folder):
    syllabus = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for file in os.listdir(pdf_folder):
        if not file.lower().endswith(".pdf"):
            continue

        pdf_path = os.path.join(pdf_folder, file)
        lines = read_pdf_lines(pdf_path)
        exam, branch = detect_exam_and_branch(lines)
        if not exam:
            continue

        current_subject = None
        current_topic = None

        for line in lines:
            clean = line.strip()
            # SUBJECT heuristic
            if clean.isupper() and clean.replace(" ", "").isalpha() and len(clean.split()) <= 5:
                current_subject = clean.title()
                current_topic = None
                continue

            # TOPIC heuristic
            if (":" in clean or clean[:2].isdigit() or clean.startswith("-")) and len(clean.split()) <= 12:
                current_topic = clean.replace(":", "").strip()
                if current_subject:
                    syllabus[exam][branch if exam=="GATE" else current_subject][current_topic] = []
                continue

            # SUBTOPIC heuristic
            if current_subject and current_topic:
                parts = [p.strip() for p in clean.split(",") if len(p.strip()) > 3]
                syllabus[exam][branch if exam=="GATE" else current_subject][current_topic].extend(parts)
    return syllabus

# -----------------------------
# 6️⃣ Load syllabus JSON
# -----------------------------
syllabus = pdfs_to_json(EXTRACT_DIR)
with open(JSON_OUTPUT, "w", encoding="utf-8") as f:
    json.dump(syllabus, f, indent=2, ensure_ascii=False)

# -----------------------------
# 7️⃣ Streamlit UI
# -----------------------------
st.title("📚 Adaptive Study Planner for UPSC / GATE / SSC")

# Study capacity & start date
capacity = st.number_input("Study capacity today (hours):", min_value=1.0, value=6.0, step=0.5)
start_date = st.date_input("Start date:")

# Select exam
exams = list(syllabus.keys())
exam = st.selectbox("Select Exam:", exams)
if not exam:
    st.stop()

# Select branch/subject
branches_subjects = list(syllabus[exam].keys())
branch_subject = st.selectbox("Select Branch / Subject:", branches_subjects)
if not branch_subject:
    st.stop()

# Select topic
topics = list(syllabus[exam][branch_subject].keys())
selected_topic = st.selectbox("Select Topic:", topics)
if selected_topic:
    subtopics = syllabus[exam][branch_subject][selected_topic]
    st.write("Subtopics:", subtopics)

# -----------------------------
# 8️⃣ Daily Planner Assignment
# -----------------------------
st.subheader("📌 Assign Topics for Today")
assigned = []

for topic in topics:
    if len(assigned) >= capacity:
        break
    assigned.append(topic)
st.write("✅ Topics assigned today:", assigned)

# -----------------------------
# 9️⃣ Save selected plan (optional)
# -----------------------------
plan_file = f"plan_{exam}_{branch_subject}.json"
daily_plan = {exam: {branch_subject: {t: syllabus[exam][branch_subject][t] for t in assigned}}}
with open(plan_file, "w", encoding="utf-8") as f:
    json.dump(daily_plan, f, indent=2, ensure_ascii=False)
st.success(f"✅ Daily plan saved: {plan_file}")
