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
def read_pdf_lines(pdf_path, start_page=3):  # page 4 = index 3
    doc = fitz.open(pdf_path)
    lines = []
    for page_num in range(start_page, len(doc)):
        page = doc[page_num]
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
    fname = os.path.splitext(os.path.basename(pdf_path))[0].upper()
    if "GATE" in text:
        return f"GATE ({fname})"
    if "UPSC" in text or "UNION PUBLIC SERVICE COMMISSION" in text:
        return "UPSC"
    if "SSC" in text or "CGL" in text or "COMBINED GRADUATE LEVEL EXAMINATION" in text:
        return "SSC"
    return "UNKNOWN"

# -----------------------------
# 6️⃣ Parse UPSC syllabus separately (Stage 1 / Stage 2)
# -----------------------------
def parse_upsc(lines):
    upsc = {"Stage-1": defaultdict(lambda: defaultdict(list)),
            "Stage-2": defaultdict(lambda: defaultdict(list))}
    current_stage = None
    current_subject = None

    for line in lines:
        clean = line.strip()
        if not clean:
            continue
        if "STAGE-1" in clean.upper():
            current_stage = "Stage-1"
            current_subject = None
            continue
        elif "STAGE-2" in clean.upper():
            current_stage = "Stage-2"
            current_subject = None
            continue
        # Subject detection: uppercase short words
        if clean.isupper() and len(clean.split()) <= 5:
            current_subject = clean.title()
            continue
        # Subtopic collection
        if current_stage and current_subject:
            parts = [p.strip() for p in clean.split(",") if len(p.strip()) > 3]
            upsc[current_stage][current_subject][clean] = parts
    return upsc

# -----------------------------
# 7️⃣ Parse SSC syllabus separately (Tier 1 / Tier 2)
# -----------------------------
def parse_ssc(lines):
    ssc = {"Tier-1": defaultdict(lambda: defaultdict(list)),
           "Tier-2": defaultdict(lambda: defaultdict(list))}
    current_tier = None
    current_subject = None

    for line in lines:
        clean = line.strip()
        if not clean:
            continue
        if "TIER-I" in clean.upper():
            current_tier = "Tier-1"
            current_subject = None
            continue
        elif "TIER-II" in clean.upper():
            current_tier = "Tier-2"
            current_subject = None
            continue
        # Subject detection: uppercase short words
        if clean.isupper() and len(clean.split()) <= 5:
            current_subject = clean.title()
            continue
        # Subtopic collection
        if current_tier and current_subject:
            parts = [p.strip() for p in clean.split(",") if len(p.strip()) > 3]
            ssc[current_tier][current_subject][clean] = parts
    return ssc

# -----------------------------
# 8️⃣ Parse PDFs into JSON
# -----------------------------
syllabus_json = defaultdict(dict)

for root, dirs, files in os.walk(EXTRACT_DIR):
    for file in files:
        if not file.lower().endswith(".pdf"):
            continue
        pdf_path = os.path.join(root, file)
        lines = read_pdf_lines(pdf_path)
        exam = detect_exam(pdf_path, lines)

        if exam.startswith("UPSC"):
            syllabus_json[exam] = parse_upsc(lines)
        elif exam.startswith("SSC"):
            syllabus_json[exam] = parse_ssc(lines)
        else:
            syllabus_json[exam] = {}  # Can add GATE later

# -----------------------------
# 9️⃣ Display syllabus on app
# -----------------------------
st.header("📚 Syllabus Viewer")
if not syllabus_json:
    st.warning("⚠️ No syllabus detected!")
else:
    for exam, stages in syllabus_json.items():
        st.subheader(f"Exam: {exam}")
        for stage, subjects in stages.items():
            st.markdown(f"**{stage}**")
            for subject, topics in subjects.items():
                st.write(f"- Subject: {subject}")
                for topic, subtopics in topics.items():
                    st.write(f"  - Topic: {topic}")
                    st.write(f"    - Subtopics: {subtopics}")

# -----------------------------
# 10️⃣ Study Planner
# -----------------------------
st.header("📝 Study Planner")

start_date = st.date_input("Select start date:", datetime.today())
exam_list = list(syllabus_json.keys())
selected_exam = st.selectbox("Select exam:", exam_list)

if selected_exam:
    stages = list(syllabus_json[selected_exam].keys())
    selected_stage = st.selectbox("Select stage/tier:", stages)
    subjects = list(syllabus_json[selected_exam][selected_stage].keys())
    selected_subjects = st.multiselect("Select subject(s) to start with:", subjects)

    capacity = st.number_input("Study capacity today (hours):", min_value=1.0, value=6.0, step=0.5)

    if st.button("Assign Topics"):
        assigned_topics = []
        used_hours = 0
        for subject in selected_subjects:
            for topic, subtopics in syllabus_json[selected_exam][selected_stage][subject].items():
                est_time = max(len(subtopics) * 0.5, 0.5)  # heuristic: 0.5h per subtopic
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
