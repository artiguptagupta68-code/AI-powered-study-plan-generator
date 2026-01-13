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
# 1️⃣ Streamlit Title
# -----------------------------
st.title("📚 Adaptive Study Planner for UPSC / GATE / SSC")

# -----------------------------
# 2️⃣ Configuration / Inputs
# -----------------------------
DRIVE_FILE_ID = st.text_input("Enter Google Drive file ID for syllabus ZIP:")
LOCAL_ZIP = "syllabus.zip"
EXTRACT_DIR = "syllabus_data"

syllabus = {}
topic_status = {}

# -----------------------------
# 3️⃣ Download & extract ZIP
# -----------------------------
if DRIVE_FILE_ID:
    if not os.path.exists(LOCAL_ZIP):
        st.info("⬇️ Downloading syllabus ZIP from Google Drive...")
        gdown.download(f"https://drive.google.com/uc?id={DRIVE_FILE_ID}", LOCAL_ZIP, quiet=False)
    else:
        st.info("ℹ️ ZIP already exists, using local copy.")

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
# 5️⃣ Detect exam and GATE branch
# -----------------------------
def detect_exam_and_branch(lines):
    text = " ".join(lines[:50]).upper()
    if "GATE" in text:
        branch = "General"
        for line in lines[:10]:
            if any(kw in line.upper() for kw in ["CSE","EE","ME","CE","EC"]):
                branch = line.strip()
                break
        return "GATE - "+branch
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
        exam = detect_exam_and_branch(lines)

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
# 7️⃣ Run parsing & save JSON
# -----------------------------
if os.path.exists(EXTRACT_DIR):
    syllabus = pdfs_to_json(EXTRACT_DIR)
    st.success("✅ Syllabus parsed successfully!")

    with open("syllabus.json","w",encoding="utf-8") as f:
        json.dump(syllabus, f, indent=2, ensure_ascii=False)

# -----------------------------
# 8️⃣ Build topic_status with estimated time
# -----------------------------
def build_topic_status(syllabus):
    topic_status = {}
    for exam, subjects in syllabus.items():
        for subject, topics in subjects.items():
            for topic, subtopics in topics.items():
                # Simple estimated time: 0.2h per subtopic
                est = max(0.2 * max(len(subtopics),1), 0.5)
                topic_status[(exam, subject, topic)] = {
                    "subtopics": subtopics,
                    "estimated_time": round(est,2),
                    "status": "pending",
                    "last_studied": None,
                    "next_revision": []
                }
    return topic_status

if syllabus:
    topic_status = build_topic_status(syllabus)

# -----------------------------
# 9️⃣ Study Planner UI
# -----------------------------
if topic_status:
    st.subheader("📌 Daily Study Planner")

    # Study capacity & start date
    capacity = st.number_input("Daily study capacity (hours):", min_value=1.0, value=6.0, step=0.5)
    start_date = st.date_input("Preparation start date:", value=datetime.today())

    # Select exam & subjects
    exams = list(syllabus.keys())
    selected_exam = st.selectbox("Select Exam:", exams)

    subjects = list(syllabus[selected_exam].keys())
    selected_subjects = st.multiselect("Select Subject(s):", subjects)

    # Assign topics automatically
    if st.button("Assign Topics"):
        assigned = []
        used = 0
        for (exam, subject, topic), info in topic_status.items():
            if exam != selected_exam or subject not in selected_subjects:
                continue
            if info["status"] != "pending":
                continue
            if used + info["estimated_time"] <= capacity:
                assigned.append((subject, topic, info))
                used += info["estimated_time"]
            else:
                break

        if assigned:
            st.write(f"📌 Topics assigned for {selected_exam} today:")
            for subject, topic, info in assigned:
                st.write(f"**{subject} → {topic}** (Est: {info['estimated_time']}h)")
                for stp in info["subtopics"]:
                    st.write(f"- {stp}")
                # Complete checkbox
                key = f"{subject}_{topic}"
                completed = st.checkbox(f"Mark {subject} → {topic} as completed", key=key)
                if completed:
                    info["status"] = "completed"
                    info["last_studied"] = datetime.now()
                    info["next_revision"] = [
                        datetime.now() + timedelta(days=1),
                        datetime.now() + timedelta(days=3),
                        datetime.now() + timedelta(days=7)
                    ]
        else:
            st.info("No topics fit within the daily study capacity or all topics done!")

    # Progress
    total = len(topic_status)
    completed = len([v for v in topic_status.values() if v["status"]=="completed"])
    pending_count = len([v for v in topic_status.values() if v["status"]=="pending"])
    st.subheader("📊 Progress")
    st.write(f"Total: {total} | Completed: {completed} | Pending: {pending_count}")

    # Revision due today
    now = datetime.now()
    due = []
    for (exam, subject, topic), info in topic_status.items():
        if info["status"]=="completed":
            for rev in info["next_revision"]:
                if now >= rev:
                    due.append((subject, topic, info))
                    break
    if due:
        st.subheader("🕑 Topics due for revision today:")
        for subject, topic, info in due:
            st.write(f"**{subject} → {topic}**")
