# app.py
import streamlit as st
import os
import zipfile
import gdown
import fitz
import re
from collections import defaultdict, deque
from datetime import datetime, timedelta

# -----------------------------
# CONFIGURATION
# -----------------------------
DRIVE_FILE_ID = "1S6fcsuq9KvICTsOBOdp6_WN9FhzruixM"
ZIP_PATH = "plan.zip"
EXTRACT_DIR = "syllabus_data"

st.set_page_config(page_title="📚 Study Planner Calendar", layout="wide")

# -----------------------------
# DOWNLOAD & EXTRACT ZIP
# -----------------------------
if not os.path.exists(ZIP_PATH):
    with st.spinner("⬇️ Downloading syllabus ZIP..."):
        gdown.download(f"https://drive.google.com/uc?id={DRIVE_FILE_ID}", ZIP_PATH, quiet=False)

if not os.path.exists(EXTRACT_DIR):
    os.makedirs(EXTRACT_DIR, exist_ok=True)
    with zipfile.ZipFile(ZIP_PATH, "r") as zip_ref:
        zip_ref.extractall(EXTRACT_DIR)

# -----------------------------
# CLEAN PDF LINES
# -----------------------------
def is_garbage_line(line):
    l = line.lower()
    garbage_keywords = ["annexure", "government of india", "national medical commission",
                        "medical education", "ugmeb", "neet (ug exam)", "date:", "sector",
                        "dwarka", "new delhi", "pocket-", "phase-", "board)", "exam)"]
    if any(k in l for k in garbage_keywords): return True
    if re.match(r"[a-z]-\d+/\d+", l): return True
    if re.search(r"\d{1,2}(st|nd|rd|th)?\s+[a-z]+\s+\d{4}", l): return True
    if len(line) > 120: return True
    return False

def read_pdf_lines(pdf_path):
    doc = fitz.open(pdf_path)
    lines = []
    for page in doc:
        text = page.get_text()
        for line in text.split("\n"):
            line = line.strip()
            if line and not is_garbage_line(line):
                lines.append(line)
    return lines

# -----------------------------
# DETECT EXAM & STAGE/BRANCH
# -----------------------------
def detect_exam(pdf_path, lines):
    text = " ".join(lines).upper()
    filename = os.path.basename(pdf_path).upper()
    folder = os.path.basename(os.path.dirname(pdf_path)).upper()
    if "NEET" in text or "NEET" in filename or "NEET" in folder:
        return "NEET", "UG"
    if "JEE" in text or "IIT" in text:
        return "IIT JEE", "JEE Advanced" if "ADVANCED" in text else "JEE Main"
    if "GATE" in text or "GRADUATE APTITUDE TEST" in text:
        branch = "General"
        for l in lines:
            if l.upper().strip() in ["ME","IN","CE"]:
                branch = l.upper().strip()
                break
        return "GATE", branch
    return None, None

# -----------------------------
# PARSE SYLLABUS TO JSON
# -----------------------------
def parse_syllabus(root_dir):
    syllabus = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))
    remove_subjects = ["SECRETARY", "PUBLIC NOTICE"]
    for root, _, files in os.walk(root_dir):
        for file in files:
            if not file.lower().endswith(".pdf"): continue
            pdf_path = os.path.join(root, file)
            lines = read_pdf_lines(pdf_path)
            exam, stage = detect_exam(pdf_path, lines)
            if not exam: continue
            current_subject = None
            current_topic = None
            for line in lines:
                if line.isupper() and line.replace(" ","").isalpha() and len(line.split())<=5:
                    if line.upper() in remove_subjects:
                        current_subject = None
                        current_topic = None
                        continue
                    current_subject = line.title()
                    current_topic = None
                    continue
                if (":" in line or line[:2].isdigit() or line.startswith("-")) and len(line.split())<=12:
                    current_topic = line.replace(":", "").strip()
                    if current_subject:
                        syllabus[exam][stage][current_subject][current_topic] = []
                    continue
                if current_subject and current_topic:
                    parts = [p.strip() for p in line.split(",") if len(p.strip())>3]
                    syllabus[exam][stage][current_subject][current_topic].extend(parts)
    return syllabus

syllabus_json = parse_syllabus(EXTRACT_DIR)
if not syllabus_json:
    st.error("⚠️ No syllabus detected!")
    st.stop()

# -----------------------------
# UI: Select Exam & Subjects
# -----------------------------
st.title("📅 Competitive Exam Study Planner Calendar")

selected_exam = st.selectbox("Select Exam", list(syllabus_json.keys()))

available_stages = list(syllabus_json[selected_exam].keys())
selected_stage = st.selectbox("Select Stage / Branch", available_stages)

available_subjects = list(syllabus_json[selected_exam][selected_stage].keys())
selected_subjects = st.multiselect("Select Subjects (priority order)", available_subjects)

capacity = st.number_input("Enter your daily study capacity (hours)", min_value=1.0, value=6.0, step=0.5)

# -----------------------------
# BUILD SUBTOPIC QUEUE
# -----------------------------
def build_subtopic_queue(exam, stage, subjects):
    queue = deque()
    for subj in subjects:
        for topic, subs in syllabus_json[exam][stage][subj].items():
            for sub in subs:
                # Time estimation: 0.3h base + 0.2h per word in subtopic
                est_time = 0.3 + 0.05 * len(sub.split())
                queue.append({"subject":subj, "subtopic":sub, "time":est_time})
    return queue

# -----------------------------
# GENERATE CALENDAR
# -----------------------------
if selected_subjects:
    subtopic_queue = build_subtopic_queue(selected_exam, selected_stage, selected_subjects)
    calendar = []
    current_date = datetime.today()

    while subtopic_queue:
        day_plan = []
        remaining_time = capacity
        temp_queue = deque()

        while subtopic_queue:
            item = subtopic_queue.popleft()
            if item["time"] <= remaining_time:
                day_plan.append(item)
                remaining_time -= item["time"]
            else:
                temp_queue.appendleft(item)
                break

        subtopic_queue = temp_queue + subtopic_queue
        calendar.append({"date": current_date, "plan": day_plan})
        current_date += timedelta(days=1)

    # -----------------------------
    # DISPLAY CALENDAR
    # -----------------------------
    st.header("📆 Study Calendar")
    for day in calendar:
        st.subheader(f"📌 {day['date'].strftime('%A, %d %b %Y')}")
        if day['plan']:
            for s in day['plan']:
                st.checkbox(f"{s['subject']} → {s['subtopic']} ({s['time']:.1f}h)")
        else:
            st.info("Rest day / No subtopics assigned")
