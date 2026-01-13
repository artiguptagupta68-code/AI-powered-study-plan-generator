# app.py
import streamlit as st
import os, zipfile
import gdown
import fitz  # PyMuPDF
from collections import defaultdict
import json
from datetime import datetime, timedelta

# -----------------------------
# 1️⃣ Configuration
# -----------------------------
DRIVE_FILE_ID = "1IRP5upBPCua57WmoEfjn9t6YJQq0_yGB"  # syllabus.zip
LOCAL_ZIP = "syllabus.zip"
EXTRACT_DIR = "syllabus_data"

# -----------------------------
# 2️⃣ Streamlit title
# -----------------------------
st.title("📚 Adaptive Study Planner for UPSC / GATE / SSC")

# -----------------------------
# 3️⃣ Download ZIP
# -----------------------------
if not os.path.exists(LOCAL_ZIP):
    st.info("⬇️ Downloading syllabus ZIP from Google Drive...")
    gdown.download(f"https://drive.google.com/uc?id={DRIVE_FILE_ID}", LOCAL_ZIP, quiet=False)
else:
    st.info("ℹ️ ZIP already exists, using local copy.")

# -----------------------------
# 4️⃣ Extract ZIP
# -----------------------------
os.makedirs(EXTRACT_DIR, exist_ok=True)
with zipfile.ZipFile(LOCAL_ZIP, 'r') as zip_ref:
    zip_ref.extractall(EXTRACT_DIR)
st.success(f"✅ ZIP extracted to {EXTRACT_DIR}")

# -----------------------------
# 5️⃣ PDF reading function
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
# 6️⃣ Detect exam
# -----------------------------
def detect_exam(lines):
    text = " ".join(lines[:50]).upper()
    if "GATE" in text:
        # Read branch name from first few lines if available
        for line in lines[:20]:
            if any(w in line.upper() for w in ["CIVIL","MECH","ECE","EEE","CS","CHEM","BIOTECH"]):
                return f"GATE ({line.strip()})"
        return "GATE"
    if "SSC" in text or "CGL" in text:
        return "SSC/CGL"
    if "UPSC" in text or "UNION PUBLIC SERVICE COMMISSION" in text:
        return "UPSC"
    return "UNKNOWN"

# -----------------------------
# 7️⃣ Parse PDFs to JSON
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

            # ---- SUBJECT heuristic ----
            if clean.isupper() and clean.replace(" ", "").isalpha() and len(clean.split()) <= 5:
                current_subject = clean.title()
                current_topic = None
                continue

            # ---- TOPIC heuristic ----
            if (":" in clean or clean[:2].isdigit() or clean.startswith("-")) and len(clean.split()) <= 12:
                current_topic = clean.replace(":", "").strip()
                if current_subject:
                    syllabus[exam][current_subject][current_topic] = []
                continue

            # ---- SUBTOPIC heuristic ----
            if current_subject and current_topic:
                parts = [p.strip() for p in clean.split(",") if len(p.strip()) > 3]
                syllabus[exam][current_subject][current_topic].extend(parts)

    return syllabus

syllabus_json = pdfs_to_json(EXTRACT_DIR)
st.success("📚 Syllabus parsed successfully!")

# -----------------------------
# 8️⃣ Show syllabus on screen
# -----------------------------
st.subheader("📝 Full Syllabus")
for exam, subjects in syllabus_json.items():
    st.write(f"### Exam: {exam}")
    for subject, topics in subjects.items():
        st.write(f"**Subject:** {subject}")
        for topic, subtopics in topics.items():
            st.write(f"- Topic: {topic}")
            st.write(f"  - Subtopics: {subtopics}")

# -----------------------------
# 9️⃣ Daily Planner Inputs
# -----------------------------
st.subheader("📌 Daily Planner")
# 9.1 Choose study capacity
capacity = st.number_input("Enter study capacity today (hours):", min_value=1.0, value=4.0, step=0.5)
# 9.2 Choose exam
exams_list = list(syllabus_json.keys())
selected_exam = st.selectbox("Select Exam:", exams_list)
if selected_exam and selected_exam in syllabus_json:
    # 9.3 Choose subjects
    subjects = list(syllabus_json[selected_exam].keys())
    selected_subjects = st.multiselect("Select subject(s) to start with:", subjects)

    # 9.4 Assign topics
    if st.button("Assign Topics"):
        assigned_topics = []
        used_hours = 0
        for subj in selected_subjects:
            for topic, subtopics in syllabus_json[selected_exam][subj].items():
                est_time = max(len(subtopics) * 0.3, 0.3)  # 0.3h per subtopic, min 0.3h
                if used_hours >= capacity:
                    break
                if used_hours + est_time > capacity:
                    remaining = capacity - used_hours
                    if remaining > 0:
                        n_sub = max(1, int(remaining/0.3))
                        assigned_topics.append((subj, topic, subtopics[:n_sub]))
                        used_hours += remaining
                    break
                else:
                    assigned_topics.append((subj, topic, subtopics))
                    used_hours += est_time

        if assigned_topics:
            st.success("✅ Topics assigned today:")
            for subj, topic, subtopics in assigned_topics:
                st.write(f"- Subject: {subj} | Topic: {topic}")
                st.write(f"  - Subtopics: {subtopics}")
        else:
            st.warning("⚠️ No topics fit within your study capacity today!")
