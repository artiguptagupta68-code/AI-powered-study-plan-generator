# app.py

import streamlit as st
import os
import zipfile
import gdown
import fitz  # PyMuPDF
from collections import defaultdict
from datetime import datetime, timedelta
import json

# -------------------------------
# 1️⃣ Configuration
# -------------------------------
DRIVE_FILE_ID = "1IRP5upBPCua57WmoEfjn9t6YJQq0_yGB"  # syllabus ZIP Google Drive file ID
LOCAL_ZIP = "syllabus.zip"
EXTRACT_DIR = "syllabus_data"
JSON_OUTPUT = "syllabus.json"

# -------------------------------
# 2️⃣ Download ZIP
# -------------------------------
if not os.path.exists(LOCAL_ZIP):
    st.info("⬇️ Downloading syllabus ZIP from Google Drive...")
    gdown.download(f"https://drive.google.com/uc?id={DRIVE_FILE_ID}", LOCAL_ZIP, quiet=False)
else:
    st.info("ℹ️ ZIP already exists, using local copy.")

# -------------------------------
# 3️⃣ Extract ZIP
# -------------------------------
os.makedirs(EXTRACT_DIR, exist_ok=True)
with zipfile.ZipFile(LOCAL_ZIP, 'r') as zip_ref:
    zip_ref.extractall(EXTRACT_DIR)
st.success(f"✅ ZIP extracted to {EXTRACT_DIR}")

# -------------------------------
# 4️⃣ PDF reading function
# -------------------------------
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

# -------------------------------
# 5️⃣ Detect exam
# -------------------------------
def detect_exam(lines):
    text = " ".join(lines[:50]).upper()
    if "GATE" in text:
        return "GATE"
    if "SSC" in text:
        return "SSC"
    if "UPSC" in text or "UNION PUBLIC SERVICE COMMISSION" in text:
        return "UPSC"
    return "UNKNOWN"

# -------------------------------
# 6️⃣ Parse PDFs to JSON
# -------------------------------
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

# -------------------------------
# 7️⃣ Run parsing
# -------------------------------
syllabus_json = pdfs_to_json(EXTRACT_DIR)
st.success("✅ Syllabus parsed successfully!")

# -------------------------------
# 8️⃣ Save JSON
# -------------------------------
with open(JSON_OUTPUT, "w", encoding="utf-8") as f:
    json.dump(syllabus_json, f, indent=2, ensure_ascii=False)
st.info(f"✅ Syllabus saved as {JSON_OUTPUT}")

# -------------------------------
# 9️⃣ Streamlit Study Planner
# -------------------------------
st.title("📚 Adaptive Study Planner")

# Select exam
available_exams = list(syllabus_json.keys())
exam = st.selectbox("Select exam:", ["--Select--"] + available_exams)

if exam == "--Select--" or exam not in syllabus_json:
    st.info("Select a valid exam to continue.")
    st.stop()

# Start date
start_date = st.date_input("Select start date:", datetime.today())

# Daily capacity
capacity = st.number_input("Daily study capacity (hours):", min_value=1.0, value=4.0, step=0.5)

# Subject selection
subjects = list(syllabus_json[exam].keys())
selected_subjects = st.multiselect("Select subject(s) to start with:", subjects)

if not selected_subjects:
    st.info("Select at least one subject to assign topics.")
    st.stop()

# -------------------------------
# Flatten topics & subtopics
# -------------------------------
topic_list = []
for sub in selected_subjects:
    for topic, subtopics in syllabus_json[exam][sub].items():
        topic_list.append({
            "exam": exam,
            "subject": sub,
            "topic": topic,
            "subtopics": subtopics,
            "estimated_time": max(0.5, len(subtopics)*0.3),  # 0.3h per subtopic
            "status": "pending",
            "last_studied": None,
            "next_revision": []
        })

# -------------------------------
# Assign topics based on capacity
# -------------------------------
def assign_topics(daily_capacity, topics):
    assigned = []
    used = 0
    for t in topics:
        if t["status"] != "pending":
            continue
        est_time = t["estimated_time"]
        if used + est_time <= daily_capacity:
            assigned.append(t)
            used += est_time
        else:
            break
    return assigned

# -------------------------------
# Daily Planner UI
# -------------------------------
st.subheader("📌 Today's Plan")
assigned = assign_topics(capacity, topic_list)

if assigned:
    for t in assigned:
        st.markdown(f"**{t['exam']} > {t['subject']} > {t['topic']}**")
        for sub in t["subtopics"]:
            st.write(f"- {sub}")

        completed = st.checkbox(f"Completed: {t['topic']}", key=t['topic'])
        if completed:
            t["status"] = "completed"
            t["last_studied"] = str(datetime.now())
            t["next_revision"] = [
                str(datetime.now() + timedelta(days=1)),
                str(datetime.now() + timedelta(days=3)),
                str(datetime.now() + timedelta(days=7))
            ]
else:
    st.info("No topics fit today's capacity or all topics are completed!")

# -------------------------------
# Progress
# -------------------------------
total = len(topic_list)
completed = len([t for t in topic_list if t["status"] == "completed"])
pending = total - completed

st.subheader("📊 Progress")
st.write(f"Total topics: {total} | Completed: {completed} | Pending: {pending}")

# -------------------------------
# Revisions due today
# -------------------------------
now = datetime.now()
due = []

for t in topic_list:
    if t["status"] == "completed":
        for rev in t.get("next_revision", []):
            if datetime.fromisoformat(rev) <= now:
                due.append(t)

if due:
    st.subheader("🕑 Topics due for revision today:")
    for t in due:
        st.write(f"- {t['exam']} > {t['subject']} > {t['topic']}")
