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
# 1️⃣ Configuration
# -----------------------------
DRIVE_FILE_ID = "1IRP5upBPCua57WmoEfjn9t6YJQq0_yGB"  # syllabus ZIP
LOCAL_ZIP = "plan.zip"
EXTRACT_DIR = "syllabus_data"

# -----------------------------
# 2️⃣ Download ZIP
# -----------------------------
if not os.path.exists(LOCAL_ZIP):
    st.info("⬇️ Downloading syllabus ZIP from Google Drive...")
    gdown.download(f"https://drive.google.com/uc?id={DRIVE_FILE_ID}", LOCAL_ZIP, quiet=False)
else:
    st.info("ℹ️ ZIP already exists.")

# -----------------------------
# 3️⃣ Extract ZIP
# -----------------------------
os.makedirs(EXTRACT_DIR, exist_ok=True)
with zipfile.ZipFile(LOCAL_ZIP, 'r') as zip_ref:
    zip_ref.extractall(EXTRACT_DIR)
st.success(f"✅ ZIP extracted to {EXTRACT_DIR}")

# -----------------------------
# 4️⃣ Read PDF lines
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
# 5️⃣ Detect exam and stage/tier
# -----------------------------
# -----------------------------
# 5️⃣ Detect exam and stage/tier (updated)
# -----------------------------
def detect_exam_stage(pdf_path, lines):
    text_sample = " ".join(lines[:50]).upper()

    # ---------------- UPSC ----------------
    if any("UNION PUBLIC SERVICE COMMISSION" in l.upper() for l in lines[:5]):
        stage = None
        # Detect Stage-1 / Stage-2 from syllabus headings
        for l in lines:
            if "PRELIMINARY" in l.upper() or "STAGE-1" in l.upper():
                stage = "Stage-1"
                break
            elif "MAIN" in l.upper() or "STAGE-2" in l.upper():
                stage = "Stage-2"
                break
        if stage is None:
            stage = "Stage-1"
        return "UPSC", stage

    # ---------------- SSC CGL ----------------
    if "COMBINED GRADUATE LEVEL EXAMINATION" in text_sample:
        tier = None
        for l in lines:
            l_upper = l.upper()
            if "INDICATIVE SYLLABUS (TIER-I)" in l_upper or "TIER-I" in l_upper:
                tier = "Tier-1"
                break
            elif "INDICATIVE SYLLABUS (TIER-II)" in l_upper or "TIER-II" in l_upper:
                tier = "Tier-2"
                break
        if not tier:
            tier = "Tier-1"  # default to Tier-1 if not found
        return "SSC (CGL)", tier

    # ---------------- GATE ----------------
    if "GATE" in text_sample:
        branch = None
        exam = "GATE"
        for l in lines[:20]:
            l_clean = l.strip()
            if l_clean.isupper() and len(l_clean.split()) <= 3 and "GATE" not in l_clean:
                branch = l_clean
                break
        if not branch:
            branch = os.path.splitext(os.path.basename(pdf_path))[0].replace("gate", "").strip().upper()
        return f"{exam} ({branch})", None

    return "UNKNOWN", None


# -----------------------------
# 7️⃣ Run parsing
# -----------------------------
syllabus_json = pdfs_to_json(EXTRACT_DIR)

if not syllabus_json:
    st.warning("⚠️ No syllabus detected!")
else:
    st.success("✅ Syllabus parsed successfully!")

# -----------------------------
# 8️⃣ Display syllabus
# -----------------------------
st.header("📚 Syllabus Viewer")
for exam, stages in syllabus_json.items():
    st.subheader(f"Exam: {exam}")
    for stage, subjects in stages.items():
        st.write(f"**Stage/Tier:** {stage}")
        for subject, topics in subjects.items():
            st.write(f"  **Subject:** {subject}")
            for topic, subtopics in topics.items():
                st.write(f"    - Topic: {topic}")
                st.write(f"      - Subtopics: {subtopics}")

# -----------------------------
# 9️⃣ Study Planner
# -----------------------------
st.header("📝 Study Planner")

# Start date
start_date = st.date_input("Select start date:", datetime.today())

# Exam & stage select
exam_list = list(syllabus_json.keys())
selected_exam = st.selectbox("Select exam:", exam_list)

if selected_exam:
    stage_list = list(syllabus_json[selected_exam].keys())
    selected_stage = st.selectbox("Select stage/tier:", stage_list)

    subjects = list(syllabus_json[selected_exam][selected_stage].keys())
    selected_subjects = st.multiselect("Select subject(s) to start with:", subjects)

    # Study capacity
    capacity = st.number_input("Study capacity today (hours):", min_value=1.0, value=6.0, step=0.5)

    # Assign topics
    if st.button("Assign Topics"):
        assigned_topics = []
        used_hours = 0
        for subject in selected_subjects:
            for topic, subtopics in syllabus_json[selected_exam][selected_stage][subject].items():
                est_time = max(len(subtopics) * 0.5, 0.5)
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
