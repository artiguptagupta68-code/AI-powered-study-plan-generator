# app.py
import streamlit as st
import os
import zipfile
import gdown
import fitz
from collections import defaultdict
from datetime import datetime
import json

# -----------------------------
# 1️⃣ CONFIGURATION
# -----------------------------
DRIVE_FILE_ID = "1S6fcsuq9KvICTsOBOdp6_WN9FhzruixM"
ZIP_PATH = "plan.zip"
EXTRACT_DIR = "syllabus_data"

# -----------------------------
# 2️⃣ DOWNLOAD ZIP
# -----------------------------
if not os.path.exists(ZIP_PATH):
    st.info("⬇️ Downloading syllabus ZIP...")
    gdown.download(f"https://drive.google.com/uc?id={DRIVE_FILE_ID}", ZIP_PATH, quiet=False)
else:
    st.info("ℹ️ ZIP already exists")

# -----------------------------
# 3️⃣ EXTRACT ZIP
# -----------------------------
os.makedirs(EXTRACT_DIR, exist_ok=True)
with zipfile.ZipFile(ZIP_PATH, "r") as z:
    z.extractall(EXTRACT_DIR)
st.success("✅ ZIP extracted successfully")

# -----------------------------
# 4️⃣ READ PDF
# -----------------------------
def read_pdf_lines(path):
    doc = fitz.open(path)
    lines = []
    for page in doc:
        lines += [l.strip() for l in page.get_text().split("\n") if l.strip()]
    return lines

# -----------------------------
# 5️⃣ DETECT EXAM + STAGE
# -----------------------------
def detect_exam(pdf_path, lines):
    text = " ".join(lines).upper()
    fname = os.path.basename(pdf_path).upper()

    # -------- NEET --------
    if "NEET" in text or "NEET" in fname:
        return "NEET", "UG"

    # -------- IIT JEE --------
    if "JEE" in text or "IIT" in text:
        if "ADVANCED" in text:
            return "IIT JEE", "JEE Advanced"
        return "IIT JEE", "JEE Main"

    # -------- GATE --------
    if "GATE" in text or fname.startswith("GATE"):
        branch = "General"
        for l in lines:
            if l.isupper() and len(l.split()) <= 5 and "GATE" not in l:
                branch = l
                break
        return "GATE", branch

    return None, None

# -----------------------------
# 6️⃣ PARSE ALL SYLLABUS
# -----------------------------
def parse_syllabus(root):
    syllabus = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))

    for root_dir, _, files in os.walk(root):
        for file in files:
            if not file.lower().endswith(".pdf"):
                continue

            path = os.path.join(root_dir, file)
            lines = read_pdf_lines(path)
            exam, stage = detect_exam(path, lines)

            if not exam:
                continue

            subject = topic = None

            for line in lines:
                # SUBJECT
                if line.isupper() and line.replace(" ", "").isalpha() and len(line.split()) <= 5:
                    subject = line.title()
                    continue

                # TOPIC
                if (":" in line or line[:2].isdigit()) and subject:
                    topic = line.replace(":", "").strip()
                    syllabus[exam][stage][subject][topic] = []
                    continue

                # SUBTOPIC
                if subject and topic:
                    syllabus[exam][stage][subject][topic].append(line)

    return syllabus

# -----------------------------
# 7️⃣ RUN PARSING
# -----------------------------
syllabus_json = parse_syllabus(EXTRACT_DIR)

if not syllabus_json:
    st.error("❌ No syllabus detected")
else:
    st.success(f"✅ Exams detected: {', '.join(syllabus_json.keys())}")

# -----------------------------
# 8️⃣ SYLLABUS VIEWER
# -----------------------------
st.header("📚 Syllabus Viewer")

for exam, stages in syllabus_json.items():
    st.subheader(f"📝 Exam: {exam}")
    for stage, subjects in stages.items():
        st.markdown(f"**Stage / Branch:** {stage}")
        for subject, topics in subjects.items():
            st.markdown(f"🔹 **{subject}**")
            for topic, subtopics in topics.items():
                st.markdown(f"- {topic}")
                if subtopics:
                    st.markdown(f"  - {', '.join(subtopics[:5])}")

# -----------------------------
# 9️⃣ STUDY PLANNER
# -----------------------------
st.header("🗓️ Study Planner")

start_date = st.date_input("Start date", datetime.today())

exam_list = list(syllabus_json.keys())
selected_exam = st.selectbox("Select Exam", exam_list)

if selected_exam:
    stage_list = list(syllabus_json[selected_exam].keys())
    selected_stage = st.selectbox("Select Stage / Branch", stage_list)

    subjects = list(syllabus_json[selected_exam][selected_stage].keys())
    selected_subjects = st.multiselect("Select Subjects", subjects)

    capacity = st.number_input("Daily study hours", min_value=1.0, value=6.0, step=0.5)

    if st.button("📌 Assign Topics"):
        assigned = []
        used = 0

        for subject in selected_subjects:
            for topic, subs in syllabus_json[selected_exam][selected_stage][subject].items():
                est = max(0.5, len(subs) * 0.25)
                if used + est <= capacity:
                    assigned.append((subject, topic))
                    used += est
                else:
                    break

        if assigned:
            st.success("✅ Today's Study Plan")
            for s, t in assigned:
                st.write(f"- **{s}** → {t}")
        else:
            st.warning("⚠️ Not enough capacity")

# -----------------------------
# 🔹 DEBUG (OPTIONAL)
# -----------------------------
with st.expander("🔍 Debug JSON"):
    st.json(syllabus_json)
