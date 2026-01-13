# app.py
import streamlit as st
import os
import zipfile
import gdown
import fitz
from collections import defaultdict
from datetime import datetime, timedelta
import json

# -----------------------------
# 1️⃣ Configuration
# -----------------------------
DRIVE_FILE_ID = "1IRP5upBPCua57WmoEfjn9t6YJQq0_yGB"  # syllabus ZIP
LOCAL_ZIP = "plan.zip"
EXTRACT_DIR = "syllabus_data"

# -----------------------------
# 2️⃣ Download ZIP from Google Drive
# -----------------------------
if not os.path.exists(LOCAL_ZIP):
    st.info("⬇️ Downloading syllabus ZIP from Google Drive...")
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
# 4️⃣ PDF reading function
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
# 5️⃣ Detect exam from PDF
# -----------------------------
def detect_exam(pdf_path, lines):
    text = " ".join(lines[:50]).upper()
    if "GATE" in text:
        # Detect branch from filename or inside PDF
        branch = os.path.splitext(os.path.basename(pdf_path))[0]
        return f"GATE ({branch})"
    if "SSC" in text or "CGL" in text:
        return "SSC"
    if "UPSC" in text or "UNION PUBLIC SERVICE COMMISSION" in text:
        return "UPSC"
    return "UNKNOWN"

# -----------------------------
# 6️⃣ Parse PDFs to JSON (recursive)
# -----------------------------
def pdfs_to_json(pdf_folder):
    syllabus = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for root, dirs, files in os.walk(pdf_folder):
        for file in files:
            if not file.lower().endswith(".pdf"):
                continue
            pdf_path = os.path.join(root, file)
            lines = read_pdf_lines(pdf_path)
            exam = detect_exam(pdf_path, lines)

            current_subject = None
            current_topic = None

            for line in lines:
                clean = line.strip()

                # Subject heuristic
                if clean.isupper() and clean.replace(" ", "").isalpha() and len(clean.split()) <= 5:
                    current_subject = clean.title()
                    current_topic = None
                    continue

                # Topic heuristic
                if (":" in clean or clean[:2].isdigit() or clean.startswith("-")) and len(clean.split()) <= 12:
                    current_topic = clean.replace(":", "").strip()
                    if current_subject:
                        syllabus[exam][current_subject][current_topic] = []
                    continue

                # Subtopic heuristic
                if current_subject and current_topic:
                    parts = [p.strip() for p in clean.split(",") if len(p.strip()) > 3]
                    syllabus[exam][current_subject][current_topic].extend(parts)

    return syllabus

# -----------------------------
# 7️⃣ Run parsing
# -----------------------------
syllabus_json = pdfs_to_json(EXTRACT_DIR)

if not syllabus_json:
    st.warning("⚠️ No syllabus detected! Check your ZIP structure or PDFs.")
else:
    st.success("✅ Syllabus parsed successfully!")

# -----------------------------
# 8️⃣ Display syllabus
# -----------------------------
st.header("📚 Syllabus Viewer")
for exam, subjects in syllabus_json.items():
    st.subheader(f"Exam: {exam}")
    for subject, topics in subjects.items():
        st.write(f"**Subject:** {subject}")
        for topic, subtopics in topics.items():
            st.write(f"- Topic: {topic}")
            st.write(f"  - Subtopics: {subtopics}")

# -----------------------------
# 9️⃣ Study Planner
# -----------------------------
st.header("📝 Study Planner")

# 9.1 Choose start date
start_date = st.date_input("Select start date:", datetime.today())

# 9.2 Select exam
exam_list = list(syllabus_json.keys())
selected_exam = st.selectbox("Select exam:", exam_list)

if selected_exam:
    subjects = list(syllabus_json[selected_exam].keys())
    selected_subjects = st.multiselect("Select subject(s) to start with:", subjects)

    # 9.3 Enter study capacity
    capacity = st.number_input("Study capacity today (hours):", min_value=1.0, value=6.0, step=0.5)

    # 9.4 Assign topics for the day
    if st.button("Assign Topics"):
        assigned_topics = []
        used_hours = 0
        for subject in selected_subjects:
            for topic, subtopics in syllabus_json[selected_exam][subject].items():
                est_time = max(len(subtopics) * 0.5, 0.5)  # simple heuristic
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

