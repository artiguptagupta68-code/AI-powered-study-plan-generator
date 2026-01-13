# app.py
import streamlit as st
import os, zipfile, json
import gdown
import fitz  # PyMuPDF
from collections import defaultdict
from datetime import datetime, timedelta

# -----------------------------
# 1️⃣ Configuration
# -----------------------------
DRIVE_FILE_ID = "1IRP5upBPCua57WmoEfjn9t6YJQq0_yGB"  # Google Drive ZIP file
LOCAL_ZIP = "syllabus.zip"
EXTRACT_DIR = "syllabus_data"
JSON_OUTPUT = "syllabus.json"

# -----------------------------
# 2️⃣ Download ZIP from Google Drive
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
st.success(f"📂 ZIP extracted to {EXTRACT_DIR}")

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
# 5️⃣ Detect exam name
# -----------------------------
def detect_exam(lines):
    text = " ".join(lines).upper()
    if any(k in text for k in ["GATE"]):
        return "GATE"
    elif any(k in text for k in ["SSC", "CGL"]):
        return "SSC"
    elif any(k in text for k in ["UPSC", "UNION PUBLIC SERVICE COMMISSION"]):
        return "UPSC"
    else:
        return None

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
        exam = detect_exam(lines)
        if not exam:
            continue  # skip PDFs with unknown exam

        current_subject = None
        current_topic = None

        for line in lines:
            clean = line.strip()

            # SUBJECT heuristic
            if clean.isupper() and clean.replace(" ", "").isalpha() and len(clean.split()) <= 5:
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
                parts = [p.strip() for p in clean.split(",") if len(p.strip()) > 3]
                syllabus[exam][current_subject][current_topic].extend(parts)

    return syllabus

# -----------------------------
# 7️⃣ Parse and save JSON
# -----------------------------
syllabus_json = pdfs_to_json(EXTRACT_DIR)

with open(JSON_OUTPUT, "w", encoding="utf-8") as f:
    json.dump(syllabus_json, f, indent=2, ensure_ascii=False)
st.success("✅ Syllabus parsed and saved!")

# -----------------------------
# 8️⃣ Streamlit UI: Study Planner
# -----------------------------
st.title("📚 Adaptive Study Planner")

# 8.1 Exam selection
exams = [e for e in syllabus_json.keys() if e is not None]
if not exams:
    st.warning("⚠️ No exam detected in PDFs!")
    st.stop()

exam = st.selectbox("Select Exam:", exams)

# 8.2 Subject selection
subjects = list(syllabus_json[exam].keys())
selected_subjects = st.multiselect("Select Subject(s):", subjects)

# 8.3 Study capacity and start date
study_capacity = st.number_input("Study capacity per day (hours):", min_value=1.0, value=6.0, step=0.5)
start_date = st.date_input("Start Preparation From:")

# -----------------------------
# 9️⃣ Assign Topics and Subtopics
# -----------------------------
if st.button("Assign Topics for Today"):
    assigned = []
    for subject in selected_subjects:
        for topic, subtopics in syllabus_json[exam][subject].items():
            assigned.append((subject, topic, subtopics))

    if assigned:
        st.subheader("📌 Today's Study Plan")
        for sub, topic, subtopics in assigned:
            st.write(f"**{sub} → {topic}**")
            for s in subtopics:
                st.write(f"- {s}")
    else:
        st.info("No topics found for the selected exam/subjects.")

# -----------------------------
# 10️⃣ Optional: Progress Tracking (can be extended)
# -----------------------------
st.subheader("📊 Progress Tracker")
st.write("You can extend this section to track completed topics and revisions over days.")
