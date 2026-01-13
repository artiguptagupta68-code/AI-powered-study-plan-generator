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
DRIVE_FILE_ID = "1IRP5upBPCua57WmoEfjn9t6YJQq0_yGB"  # Google Drive ZIP file
LOCAL_ZIP = "syllabus.zip"
EXTRACT_DIR = "syllabus_data"
JSON_OUTPUT = "syllabus.json"

# -----------------------------
# 2️⃣ Download ZIP if not exists
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
st.success(f"📂 ZIP extracted to {EXTRACT_DIR}")

# -----------------------------
# 4️⃣ PDF reading function (unchanged)
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
# 5️⃣ Detect exam (improved)
# -----------------------------
def detect_exam(lines, filename=""):
    text = " ".join(lines[:50]).upper()
    if "GATE" in text:
        return "GATE"
    if "SSC" in text:
        return "SSC"
    if "UPSC" in text or "UNION PUBLIC SERVICE COMMISSION" in text:
        return "UPSC"
    # fallback using filename
    fname = filename.upper()
    if "GATE" in fname:
        return "GATE"
    if "SSC" in fname:
        return "SSC"
    if "UPSC" in fname:
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
        exam = detect_exam(lines, file)

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
# 7️⃣ Parse and save JSON
# -----------------------------
syllabus_json = pdfs_to_json(EXTRACT_DIR)
with open(JSON_OUTPUT, "w", encoding="utf-8") as f:
    json.dump(syllabus_json, f, indent=2, ensure_ascii=False)
st.success(f"✅ Syllabus parsed and saved as {JSON_OUTPUT}")

# -----------------------------
# 8️⃣ Streamlit Study Planner
# -----------------------------
st.title("📚 Adaptive Study Planner")

# Select start date
start_date = st.date_input("Select start date for preparation", datetime.today())

# Select study capacity
study_hours = st.number_input("Study capacity per day (hours)", min_value=1.0, value=6.0, step=0.5)

# Select exam
available_exams = [e for e in syllabus_json.keys() if e != "UNKNOWN"]
exam = st.selectbox("Select exam:", ["--Select--"] + available_exams)

topic_status = {}

if exam != "--Select--":
    # Select subjects
    subjects = list(syllabus_json[exam].keys())
    selected_subjects = st.multiselect("Select subject(s) to start with:", subjects)

    # -----------------------------
    # Assign topics and subtopics
    # -----------------------------
    if st.button("Assign Topics for Today"):
        topic_status = {}
        for sub in selected_subjects:
            topics = syllabus_json[exam][sub]
            for topic, subtopics in topics.items():
                # estimate time: 0.1h per subtopic line
                est_time = max(0.1 * len(subtopics), 0.1)
                practice_time = round(est_time * 0.3, 2)
                topic_status[(exam, sub, topic)] = {
                    "estimated_time": est_time,
                    "practice_time": practice_time,
                    "subtopics": subtopics,
                    "status": "pending",
                    "last_studied": None,
                    "next_revision": []
                }

        # Display assigned topics
        st.subheader("📌 Topics assigned today:")
        for k, v in topic_status.items():
            st.write(f"- {k[1]} > {k[2]} | Est: {v['estimated_time']}h, Practice: {v['practice_time']}h")
            for stopic in v['subtopics']:
                st.write(f"    - {stopic}")

        # Complete checkboxes
        st.subheader("✅ Mark topics as completed:")
        for k in topic_status:
            completed = st.checkbox(f"{k[1]} > {k[2]}", key=str(k))
            if completed:
                topic_status[k]['status'] = 'completed'
                topic_status[k]['last_studied'] = datetime.now()
                topic_status[k]['next_revision'] = [
                    datetime.now() + timedelta(days=1),
                    datetime.now() + timedelta(days=3),
                    datetime.now() + timedelta(days=7)
                ]

        # Progress
        total = len(topic_status)
        completed = len([v for v in topic_status.values() if v['status'] == 'completed'])
        pending = len([v for v in topic_status.values() if v['status'] == 'pending'])
        st.subheader("📊 Progress")
        st.write(f"Total: {total} | Completed: {completed} | Pending: {pending}")

        # Topics due for revision today
        now = datetime.now()
        due = []
        for k, info in topic_status.items():
            if info['status'] == 'completed':
                for rev in info['next_revision']:
                    if now >= rev:
                        due.append(k)
                        break
        if due:
            st.subheader("🕑 Topics due for revision today:")
            for k in due:
                st.write(f"- {k[1]} > {k[2]}")
