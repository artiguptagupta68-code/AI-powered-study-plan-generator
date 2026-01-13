# app.py
import os
import zipfile
import gdown
import fitz
from collections import defaultdict
import streamlit as st
from datetime import datetime, timedelta
import json

# -----------------------------
# 1️⃣ Configuration
# -----------------------------
DRIVE_FILE_ID = "1IRP5upBPCua57WmoEfjn9t6YJQq0_yGB"  # syllabus ZIP
LOCAL_ZIP = "syllabus.zip"
EXTRACT_DIR = "syllabus_data"

st.set_page_config(page_title="Adaptive Study Planner", layout="wide")
st.title("📚 Adaptive Study Planner for UPSC / GATE / SSC")

# -----------------------------
# 2️⃣ Download ZIP from Google Drive
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
# 5️⃣ Detect exam (with GATE branch)
# -----------------------------
def detect_exam(pdf_path, lines):
    fname = os.path.basename(pdf_path).lower()
    # GATE branch detection
    if "gate" in fname:
        branch = None
        for l in lines[:20]:
            l = l.strip()
            if l.isupper() and len(l.split()) <= 5:
                branch = l.title()
                break
        return f"GATE - {branch}" if branch else "GATE"
    if "ssc" in fname or "cgl" in fname:
        return "SSC"
    if "upsc" in fname:
        return "UPSC"
    # fallback
    text = " ".join(lines[:50]).upper()
    if "GATE" in text:
        return "GATE"
    if "SSC" in text or "CGL" in text:
        return "SSC"
    if "UPSC" in text or "UNION PUBLIC SERVICE COMMISSION" in text:
        return "UPSC"
    return "UNKNOWN"

# -----------------------------
# 6️⃣ Parse PDFs into JSON
# -----------------------------
def pdfs_to_json(pdf_folder):
    syllabus = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for file in os.listdir(pdf_folder):
        if not file.lower().endswith(".pdf"):
            continue
        pdf_path = os.path.join(pdf_folder, file)
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
# 7️⃣ Load syllabus JSON
# -----------------------------
syllabus = pdfs_to_json(EXTRACT_DIR)
st.success("✅ Syllabus parsed successfully!")

# -----------------------------
# 8️⃣ Streamlit UI: Study Plan
# -----------------------------
if not syllabus:
    st.warning("No syllabus detected!")
else:
    # --- Select exam
    exams = list(syllabus.keys())
    selected_exam = st.selectbox("Select Exam:", exams)

    # --- Select subjects
    if selected_exam:
        subjects = list(syllabus[selected_exam].keys())
        selected_subjects = st.multiselect("Select Subject(s):", subjects)

        # --- Select study start date
        start_date = st.date_input("Select start date:", datetime.today())

        # --- Select daily study capacity
        study_capacity = st.number_input("Enter daily study capacity (hours):", min_value=1.0, value=4.0, step=0.5)

        # --- Assign topics & subtopics
        if selected_subjects and st.button("Show Study Plan"):
            st.subheader("📌 Study Plan")
            plan = []
            for subj in selected_subjects:
                for topic, subtopics in syllabus[selected_exam][subj].items():
                    plan.append({
                        "subject": subj,
                        "topic": topic,
                        "subtopics": subtopics
                    })

            # Display plan
            for idx, item in enumerate(plan, start=1):
                st.markdown(f"**{idx}. Subject:** {item['subject']}")
                st.markdown(f"   - **Topic:** {item['topic']}")
                st.markdown(f"   - **Subtopics:** {', '.join(item['subtopics'])}")
