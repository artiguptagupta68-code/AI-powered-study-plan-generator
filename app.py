# -----------------------------
# app.py
# -----------------------------
import streamlit as st
import os
import zipfile
import gdown
import fitz  # PyMuPDF
from collections import defaultdict
from datetime import datetime, timedelta
import json

# -----------------------------
# 1️⃣ Config
# -----------------------------
DRIVE_FILE_ID = "1IRP5upBPCua57WmoEfjn9t6YJQq0_yGB"  # syllabus ZIP
LOCAL_ZIP = "syllabus.zip"
EXTRACT_DIR = "syllabus_data"
JSON_OUTPUT = "syllabus.json"

# -----------------------------
# 2️⃣ Download ZIP
# -----------------------------
if not os.path.exists(LOCAL_ZIP):
    st.info("⬇️ Downloading syllabus ZIP...")
    gdown.download(f"https://drive.google.com/uc?id={DRIVE_FILE_ID}", LOCAL_ZIP, quiet=False)
else:
    st.info("ℹ️ ZIP already exists, using local copy.")

# -----------------------------
# 3️⃣ Extract ZIP
# -----------------------------
os.makedirs(EXTRACT_DIR, exist_ok=True)
with zipfile.ZipFile(LOCAL_ZIP, 'r') as zip_ref:
    zip_ref.extractall(EXTRACT_DIR)
st.success(f"✅ ZIP extracted to {EXTRACT_DIR}")

# -----------------------------
# 4️⃣ PDF reading
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
# 5️⃣ Detect exam
# -----------------------------
def detect_exam(lines):
    text = " ".join(lines).upper()
    if "GATE" in text:
        return "GATE"
    elif "SSC" in text or "CGL" in text:
        return "SSC"
    elif "UPSC" in text or "UNION PUBLIC SERVICE COMMISSION" in text:
        return "UPSC"
    else:
        return "UNKNOWN"

# -----------------------------
# 6️⃣ Parse PDFs to JSON
# -----------------------------
def pdfs_to_json(pdf_folder):
    syllabus = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for file in os.listdir(pdf_folder):
        if not file.lower().endswith(".pdf"):
            continue
        pdf_path = os.path.join(pdf_folder, file)
        lines = read_pdf_lines(pdf_path)
        exam = detect_exam(lines)

        current_subject = None
        current_topic = None

        for line in lines:
            clean = line.strip()
            # SUBJECT: UPPER, <=5 words, alphabetic
            if clean.isupper() and clean.replace(" ", "").isalpha() and len(clean.split()) <= 5:
                current_subject = clean.title()
                current_topic = None
                continue
            # TOPIC: contains ":" or starts with digit or "-" and <=12 words
            if (":" in clean or clean[:2].isdigit() or clean.startswith("-")) and len(clean.split()) <= 12:
                current_topic = clean.replace(":", "").strip()
                if current_subject:
                    syllabus[exam][current_subject][current_topic] = []
                continue
            # SUBTOPIC: comma separated
            if current_subject and current_topic:
                parts = [p.strip() for p in clean.split(",") if len(p.strip()) > 3]
                syllabus[exam][current_subject][current_topic].extend(parts)
    return syllabus

syllabus = pdfs_to_json(EXTRACT_DIR)

# Save JSON
with open(JSON_OUTPUT, "w", encoding="utf-8") as f:
    json.dump(syllabus, f, indent=2, ensure_ascii=False)

st.success("✅ Syllabus parsed successfully!")

# -----------------------------
# 7️⃣ Streamlit: Study Planner
# -----------------------------
st.title("📚 Adaptive Study Planner")

# 7.1 Select exam
exams = sorted(list(syllabus.keys()))
exam = st.selectbox("Select Exam:", exams)

if exam:
    # 7.2 Select subjects
    subjects = list(syllabus[exam].keys())
    selected_subjects = st.multiselect("Select subject(s) to start with:", subjects)

    # 7.3 Select start date
    start_date = st.date_input("Select preparation start date:", datetime.today())

    # 7.4 Daily study capacity
    capacity = st.number_input("Enter daily study capacity (hours):", min_value=1.0, value=6.0, step=0.5)

    # -----------------------------
    # 8️⃣ Assign topics per day
    # -----------------------------
    if st.button("Generate Study Plan"):
        plan = []
        for subject in selected_subjects:
            for topic, subtopics in syllabus[exam][subject].items():
                est_time_topic = max(0.1, 0.05 * sum(len(st.split()) for st in subtopics))  # simple estimate
                plan.append({
                    "exam": exam,
                    "subject": subject,
                    "topic": topic,
                    "subtopics": subtopics,
                    "estimated_time_h": round(est_time_topic, 2),
                    "status": "pending"
                })
        # Assign sequential days
        current_date = start_date
        for item in plan:
            item["date"] = current_date.strftime("%Y-%m-%d")
            current_date += timedelta(days=1)

        # Show plan
        st.subheader("📌 Study Plan")
        for item in plan:
            st.write(f"- {item['date']} | {item['subject']} > {item['topic']} | Subtopics: {item['subtopics']} | Est: {item['estimated_time_h']}h")

        # Save plan
        plan_file = f"{exam}_study_plan.json"
        with open(plan_file, "w", encoding="utf-8") as f:
            json.dump(plan, f, indent=2, ensure_ascii=False)
        st.success(f"✅ Study plan saved as {plan_file}")
