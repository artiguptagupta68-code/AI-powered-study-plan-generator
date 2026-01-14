# app.py
import streamlit as st
import os
import zipfile
import gdown
import fitz
from collections import defaultdict
from datetime import datetime
import json
import re

# -----------------------------
# 1️⃣ Configuration
# -----------------------------
DRIVE_FILE_ID = "1S6fcsuq9KvICTsOBOdp6_WN9FhzruixM"  # syllabus ZIP
LOCAL_ZIP = "plan.zip"
EXTRACT_DIR = "syllabus_data"

# -----------------------------
# 2️⃣ Download ZIP
# -----------------------------
if not os.path.exists(LOCAL_ZIP):
    st.info("⬇️ Downloading syllabus ZIP from Google Drive...")
    gdown.download(f"https://drive.google.com/uc?id={DRIVE_FILE_ID}", LOCAL_ZIP, quiet=False)
else:
    st.info("ℹ️ ZIP already exists.")

# -----------------------------
# 3️⃣ Extract ZIP
# -----------------------------
os.makedirs(EXTRACT_DIR, exist_ok=True)
with zipfile.ZipFile(LOCAL_ZIP, 'r') as zip_ref:
    zip_ref.extractall(EXTRACT_DIR)
st.success(f"✅ ZIP extracted to {EXTRACT_DIR}")

# -----------------------------
# 4️⃣ Read PDF lines
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
# 5️⃣ Clean NEET lines
# -----------------------------
def clean_neet_lines(lines):
    clean_lines = []
    for line in lines:
        line_upper = line.upper()
        # Remove garbage lines
        if any(word in line_upper for word in ["ANNEXURE", "SECRETARY", "PUBLIC", "GOVERNMENT", "DATE", "NATIONAL MEDICAL COMMISSION"]):
            continue
        clean_lines.append(line.strip())
    return clean_lines

# -----------------------------
# 6️⃣ Detect Exam and Stage/Branch
# -----------------------------
def detect_exam_stage(pdf_path, lines):
    text = " ".join(lines).upper()
    filename = os.path.basename(pdf_path).upper()
    folder = os.path.basename(os.path.dirname(pdf_path)).upper()

    # -------- NEET --------
    if "NEET" in folder or "NEET" in text or "NEET" in filename:
        lines_clean = clean_neet_lines(lines)
        return "NEET", "UG", lines_clean

    # -------- IIT JEE --------
    if "JEE" in folder or "JEE" in filename or "IIT" in text:
        stage = "General"
        if "MAIN" in text:
            stage = "JEE Main"
        elif "ADVANCED" in text:
            stage = "JEE Advanced"
        return "IIT JEE", stage, lines

    # -------- GATE --------
    if "GATE" in folder or "GATE" in filename or "GRADUATE APTITUDE TEST" in text:
        # Detect branch from filename or content
        branch = None
        if "ME" in filename:
            branch = "ME"
        elif "IN" in filename:
            branch = "IN"
        elif "CE" in filename:
            branch = "CE"
        else:
            # fallback: check first 50 lines for branch
            for l in lines[:50]:
                l_clean = l.strip().upper()
                if l_clean in ["ME", "IN", "CE"]:
                    branch = l_clean
                    break
        if not branch:
            branch = "General"
        return "GATE", branch, lines

    return "UNKNOWN", "General", lines

# -----------------------------
# 7️⃣ Parse PDFs → JSON
# -----------------------------
def pdfs_to_json(pdf_folder):
    syllabus = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))

    for root, dirs, files in os.walk(pdf_folder):
        for file in files:
            if not file.lower().endswith(".pdf"):
                continue

            pdf_path = os.path.join(root, file)
            lines = read_pdf_lines(pdf_path)
            exam, stage, lines = detect_exam_stage(pdf_path, lines)

            if exam == "UNKNOWN":
                continue

            current_subject = None
            current_topic = None

            for line in lines:
                clean = line.strip()

                # SUBJECT: uppercase, <=5 words
                if clean.isupper() and clean.replace(" ", "").isalpha() and len(clean.split()) <= 5:
                    current_subject = clean.title()
                    current_topic = None
                    continue

                # TOPIC: contains ":" or starts with number or "-"
                if (":" in clean or clean[:2].isdigit() or clean.startswith("-")) and len(clean.split()) <= 12:
                    current_topic = clean.replace(":", "").strip()
                    if current_subject:
                        syllabus[exam][stage][current_subject][current_topic] = []
                    continue

                # SUBTOPIC: comma-separated, >3 chars
                if current_subject and current_topic:
                    parts = [p.strip() for p in clean.split(",") if len(p.strip()) > 3]
                    syllabus[exam][stage][current_subject][current_topic].extend(parts)

    return syllabus

# -----------------------------
# 8️⃣ Run parsing
# -----------------------------
syllabus_json = pdfs_to_json(EXTRACT_DIR)

if not syllabus_json:
    st.warning("⚠️ No syllabus detected!")
else:
    st.success("✅ Syllabus parsed successfully!")

# -----------------------------
# 9️⃣ Display syllabus
# -----------------------------
st.header("📚 Syllabus Viewer")
for exam, stages in syllabus_json.items():
    st.subheader(f"Exam: {exam}")
    for stage, subjects in stages.items():
        st.write(f"**Stage/Tier:** {stage}")
        for subject, topics in subjects.items():
            st.write(f"  **Subject:** {subject}")
            for topic, subtopics in topics.items():
                st.write(f"    - Topic: {topic}")
                st.write(f"      - Subtopics: {subtopics}")

# -----------------------------
# 🔟 Study Planner
# -----------------------------
st.header("📝 Study Planner")

# Start date
start_date = st.date_input("Select start date:", datetime.today())

# Exam & stage select
exam_list = list(syllabus_json.keys())
selected_exam = st.selectbox("Select exam:", exam_list)

if selected_exam:
    stage_list = list(syllabus_json[selected_exam].keys())
    selected_stage = st.selectbox("Select stage/tier:", stage_list)

    subjects = list(syllabus_json[selected_exam][selected_stage].keys())
    selected_subjects = st.multiselect("Select subject(s) to start with:", subjects)

    # Study capacity
    capacity = st.number_input("Study capacity today (hours):", min_value=1.0, value=6.0, step=0.5)

    # Assign topics
    if st.button("Assign Topics"):
        assigned_topics = []
        used_hours = 0
        for subject in selected_subjects:
            for topic, subtopics in syllabus_json[selected_exam][selected_stage][subject].items():
                est_time = max(len(subtopics) * 0.5, 0.5)
                if used_hours + est_time <= capacity:
                    assigned_topics.append((subject, topic, subtopics))
                    used_hours += est_time
                else:
                    break
            if used_hours >= capacity:
                break

        if assigned_topics:
            st.subheader("📌 Topics assigned today:")
            for subj, topic, subtopics in assigned_topics:
                st.write(f"- Subject: {subj} | Topic: {topic}")
                st.write(f"  - Subtopics: {subtopics}")
        else:
            st.info("No topics fit within your study capacity today!")
