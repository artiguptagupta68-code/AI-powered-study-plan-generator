# app.py
import streamlit as st
import os, zipfile
import gdown
import fitz
from collections import defaultdict
from datetime import datetime, timedelta
import json

# -----------------------------
# 1️⃣ Configuration
# -----------------------------
DRIVE_FILE_ID = "1IRP5upBPCua57WmoEfjn9t6YJQq0_yGB"  # Google Drive file ID for syllabus ZIP
LOCAL_ZIP = "plan.zip"
EXTRACT_DIR = "plan_data"
JSON_OUTPUT = "syllabus.json"

st.title("📚 Adaptive Study Planner for UPSC / GATE / SSC")

# -----------------------------
# 2️⃣ Download ZIP
# -----------------------------
if not os.path.exists(LOCAL_ZIP):
    st.info("⬇️ Downloading syllabus ZIP from Google Drive...")
    gdown.download(f"https://drive.google.com/uc?id={DRIVE_FILE_ID}", LOCAL_ZIP, quiet=False)
else:
    st.info("ℹ️ Using existing ZIP file.")

# -----------------------------
# 3️⃣ Extract ZIP
# -----------------------------
os.makedirs(EXTRACT_DIR, exist_ok=True)
with zipfile.ZipFile(LOCAL_ZIP, 'r') as zip_ref:
    zip_ref.extractall(EXTRACT_DIR)
st.success(f"✅ ZIP extracted to {EXTRACT_DIR}")

# -----------------------------
# 4️⃣ PDF parsing functions
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

def detect_exam(lines):
    text = " ".join(lines[:50]).upper()
    if "GATE" in text:
        return "GATE"
    if "SSC" in text:
        return "SSC"
    if "UPSC" in text or "UNION PUBLIC SERVICE COMMISSION" in text:
        return "UPSC"
    return "UNKNOWN"

def parse_pdfs(folder):
    syllabus = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for file in os.listdir(folder):
        if not file.lower().endswith(".pdf"):
            continue
        pdf_path = os.path.join(folder, file)
        lines = read_pdf_lines(pdf_path)
        exam = detect_exam(lines)

        current_subject = None
        current_topic = None

        for line in lines:
            clean = line.strip()

            # SUBJECT heuristic
            if clean.isupper() and clean.replace(" ","").isalpha() and len(clean.split()) <= 5:
                current_subject = clean.title()
                current_topic = None
                continue

            # TOPIC heuristic
            if (":" in clean or clean[:2].isdigit() or clean.startswith("-")) and len(clean.split()) <= 12:
                current_topic = clean.replace(":", "").strip()
                if current_subject:
                    syllabus[exam][current_subject][current_topic] = []
                continue

            # SUBTOPIC heuristic
            if current_subject and current_topic:
                parts = [p.strip() for p in clean.split(",") if len(p.strip())>3]
                syllabus[exam][current_subject][current_topic].extend(parts)
    return syllabus

# -----------------------------
# 5️⃣ Parse and save JSON
# -----------------------------
syllabus = parse_pdfs(EXTRACT_DIR)

with open(JSON_OUTPUT, "w", encoding="utf-8") as f:
    json.dump(syllabus, f, indent=2, ensure_ascii=False)
st.success("✅ Syllabus parsed and saved!")

# -----------------------------
# 6️⃣ Show full syllabus
# -----------------------------
st.subheader("📖 Full Syllabus")
for exam, subjects in syllabus.items():
    st.markdown(f"### Exam: {exam}")
    for subject, topics in subjects.items():
        st.markdown(f"**Subject:** {subject}")
        for topic, subtopics in topics.items():
            st.markdown(f"- Topic: {topic}")
            for stp in subtopics:
                st.markdown(f"    - Subtopic: {stp}")

# -----------------------------
# 7️⃣ Study Planner UI
# -----------------------------
st.subheader("🗓 Study Planner")

# Study start date
start_date = st.date_input("Select start date:", value=datetime.today())

# Daily study capacity in hours
capacity = st.number_input("Daily study capacity (hours):", min_value=1.0, value=4.0, step=0.5)

# Select exam
exam_list = list(syllabus.keys())
selected_exam = st.selectbox("Select exam:", exam_list)

if selected_exam:
    # Select subjects
    subjects = list(syllabus[selected_exam].keys())
    selected_subjects = st.multiselect("Select subject(s) to start with:", subjects)

    # Assign topics/subtopics
    if st.button("Generate Daily Plan"):
        st.markdown("### 📌 Assigned Topics for Today")
        for subject in selected_subjects:
            for topic, subtopics in syllabus[selected_exam][subject].items():
                st.markdown(f"- **{subject} > {topic}**")
                for stp in subtopics:
                    st.markdown(f"    - {stp}")
        st.success(f"✅ Plan generated for {selected_exam} starting {start_date} with {capacity}h/day study.")


