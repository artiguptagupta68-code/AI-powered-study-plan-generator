# app.py
import streamlit as st
import os, zipfile, gdown, fitz
from collections import defaultdict
from datetime import datetime, timedelta
import json

# -----------------------------
# 1️⃣ Configuration
# -----------------------------
DRIVE_FILE_ID = "1IRP5upBPCua57WmoEfjn9t6YJQq0_yGB"
LOCAL_ZIP = "plan.zip"
EXTRACT_DIR = "syllabus_data"

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
# 5️⃣ Detect Exam and Branch
# -----------------------------
def detect_exam_branch(pdf_path, lines):
    text_sample = " ".join(lines[:50]).upper()
    exam = "UNKNOWN"
    branch = None

    if "GATE" in text_sample:
        exam = "GATE"
        # Try to detect branch from first lines
        for l in lines[:20]:
            l_clean = l.strip()
            if l_clean.isupper() and len(l_clean.split()) <= 3 and "GATE" not in l_clean:
                branch = l_clean
                break
        if not branch:
            # fallback to filename
            branch = os.path.splitext(os.path.basename(pdf_path))[0].replace("gate", "").strip().upper()
        return f"{exam} ({branch})"
    elif "SSC" in text_sample or "CGL" in text_sample:
        exam = "SSC"
    elif "UPSC" in text_sample or "UNION PUBLIC SERVICE COMMISSION" in text_sample:
        exam = "UPSC"
    return exam

# -----------------------------
# 6️⃣ Parse PDFs into JSON
# -----------------------------
def parse_syllabus(pdf_folder):
    syllabus = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for root, dirs, files in os.walk(pdf_folder):
        for file in files:
            if not file.lower().endswith(".pdf"):
                continue
            pdf_path = os.path.join(root, file)
            lines = read_pdf_lines(pdf_path)
            exam_name = detect_exam_branch(pdf_path, lines)

            current_subject = None
            current_topic = None

            for line in lines:
                clean = line.strip()

                # Subject detection: uppercase, short
                if clean.isupper() and clean.replace(" ", "").isalpha() and len(clean.split()) <= 5:
                    current_subject = clean.title()
                    current_topic = None
                    continue

                # Topic detection: numbered, colon, or short
                if (":" in clean or clean[:2].isdigit() or clean.startswith("-")) and len(clean.split()) <= 12:
                    current_topic = clean.replace(":", "").strip()
                    if current_subject:
                        syllabus[exam_name][current_subject][current_topic] = []
                    continue

                # Subtopics: comma separated or line content
                if current_subject and current_topic:
                    parts = [p.strip() for p in clean.split(",") if len(p.strip()) > 3]
                    syllabus[exam_name][current_subject][current_topic].extend(parts)
    return syllabus

# -----------------------------
# 7️⃣ Run parsing
# -----------------------------
syllabus_json = parse_syllabus(EXTRACT_DIR)
if not syllabus_json:
    st.warning("⚠️ No syllabus detected! Check your PDFs.")
else:
    st.success("✅ Syllabus parsed successfully!")

# -----------------------------
# 8️⃣ Display syllabus
# -----------------------------
st.header("📚 Syllabus Viewer")
for exam, subjects in syllabus_json.items():
    st.subheader(f"Exam: {exam}")
    for subject, topics in subjects.items():
        st.write(f"**Subject:** {subject}")
        for topic, subtopics in topics.items():
            st.write(f"- Topic: {topic}")
            st.write(f"  - Subtopics: {subtopics}")

# -----------------------------
# 9️⃣ Study Planner
# -----------------------------
st.header("📝 Study Planner")
start_date = st.date_input("Select start date:", datetime.today())

exam_list = list(syllabus_json.keys())
selected_exam = st.selectbox("Select exam:", exam_list)

if selected_exam:
    subjects = list(syllabus_json[selected_exam].keys())
    selected_subjects = st.multiselect("Select subject(s) to start with:", subjects)

    capacity = st.number_input("Study capacity today (hours):", min_value=1.0, value=6.0, step=0.5)

    if st.button("Assign Topics"):
        assigned_topics = []
        used_hours = 0
        for subject in selected_subjects:
            for topic, subtopics in syllabus_json[selected_exam][subject].items():
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
