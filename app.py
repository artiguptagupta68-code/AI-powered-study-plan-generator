# -----------------------------
# app.py: Adaptive Study Planner with Daily Schedule
# -----------------------------

import streamlit as st
import os, zipfile, gdown, fitz, json
from collections import defaultdict
from datetime import datetime, timedelta

# -----------------------------
# 1️⃣ Configuration
# -----------------------------
DRIVE_FILE_ID = "1IRP5upBPCua57WmoEfjn9t6YJQq0_yGB"  # Google Drive syllabus ZIP
LOCAL_ZIP = "syllabus.zip"
EXTRACT_DIR = "syllabus_data"
JSON_OUTPUT = "syllabus.json"

# -----------------------------
# 2️⃣ Download ZIP
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
# 5️⃣ Detect exam and branch
# -----------------------------
def detect_exam_and_branch(pdf_path, lines):
    fname = os.path.basename(pdf_path).lower()
    if "ssc" in fname or "cgl" in fname:
        exam = "SSC CGL"
        branch = None
    elif "upsc" in fname:
        exam = "UPSC"
        branch = None
    elif "gate" in fname:
        exam = "GATE"
        branch = None
        for line in lines[:30]:
            l = line.lower()
            if "branch" in l or "engineering" in l:
                branch = line.strip().title()
                break
        if not branch:
            branch = f"GATE Branch ({fname.replace('.pdf','').upper()})"
    else:
        text = " ".join(lines[:50]).upper()
        if "SSC" in text:
            exam = "SSC CGL"
            branch = None
        elif "UPSC" in text:
            exam = "UPSC"
            branch = None
        elif "GATE" in text:
            exam = "GATE"
            branch = None
        else:
            exam = "UNKNOWN"
            branch = None
    return exam, branch

# -----------------------------
# 6️⃣ Parse PDFs → JSON
# -----------------------------
def pdfs_to_json(pdf_folder):
    syllabus = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for file in os.listdir(pdf_folder):
        if not file.lower().endswith(".pdf"):
            continue
        pdf_path = os.path.join(pdf_folder, file)
        lines = read_pdf_lines(pdf_path)
        exam, branch = detect_exam_and_branch(pdf_path, lines)
        current_subject = None
        current_topic = None
        for line in lines:
            clean = line.strip()
            if clean.isupper() and clean.replace(" ", "").isalpha() and len(clean.split()) <= 5:
                current_subject = clean.title()
                current_topic = None
                continue
            if (":" in clean or clean[:2].isdigit() or clean.startswith("-")) and len(clean.split()) <= 12:
                current_topic = clean.replace(":", "").strip()
                if current_subject:
                    syllabus[exam][current_subject][current_topic] = []
                continue
            if current_subject and current_topic:
                parts = [p.strip() for p in clean.split(",") if len(p.strip()) > 3]
                syllabus[exam][current_subject][current_topic].extend(parts)
    return syllabus

# -----------------------------
# 7️⃣ Parse syllabus
# -----------------------------
syllabus = pdfs_to_json(EXTRACT_DIR)
with open(JSON_OUTPUT, "w", encoding="utf-8") as f:
    json.dump(syllabus, f, indent=2, ensure_ascii=False)
st.success("✅ Syllabus parsed and saved!")

# -----------------------------
# 8️⃣ Streamlit Study Planner UI
# -----------------------------
st.title("📚 Adaptive Study Planner with Daily Schedule")

# 8.1 Select exam
exams = list(syllabus.keys())
selected_exam = st.selectbox("Select Exam:", exams)

# 8.2 Select start date
start_date = st.date_input("Start preparation from:")

# 8.3 Enter study capacity
study_hours = st.number_input("Study capacity per day (hours):", min_value=1.0, value=4.0, step=0.5)

# 8.4 Select subjects
subjects = list(syllabus[selected_exam].keys())
selected_subjects = st.multiselect("Select subject(s) to start with:", subjects)

# -----------------------------
# 8.5 Flatten topics into list with subtopics
# -----------------------------
tasks = []
for subject in selected_subjects:
    for topic, subtopics in syllabus[selected_exam][subject].items():
        # Include topic as first task
        tasks.append({
            "subject": subject,
            "topic": topic,
            "subtopic": None,
            "est_time": max(0.5, len(topic.split())*0.05)
        })
        # Include subtopics
        for stp in subtopics:
            tasks.append({
                "subject": subject,
                "topic": topic,
                "subtopic": stp,
                "est_time": max(0.2, len(stp.split())*0.05)
            })

# -----------------------------
# 8.6 Generate daily schedule
# -----------------------------
schedule = defaultdict(list)
current_day = datetime.combine(start_date, datetime.min.time())
day_hours_used = 0
for task in tasks:
    if day_hours_used + task["est_time"] > study_hours:
        current_day += timedelta(days=1)
        day_hours_used = 0
    schedule[current_day.date()].append(task)
    day_hours_used += task["est_time"]

# -----------------------------
# 8.7 Display schedule
# -----------------------------
st.subheader("📅 Daily Study Plan")
for day, tasks_day in schedule.items():
    st.markdown(f"### {day.strftime('%A, %d %b %Y')}")
    for t in tasks_day:
        if t["subtopic"]:
            st.write(f"- {t['subject']} > {t['topic']} > {t['subtopic']} | Est: {t['est_time']}h")
        else:
            st.write(f"- {t['subject']} > {t['topic']} | Est: {t['est_time']}h")
