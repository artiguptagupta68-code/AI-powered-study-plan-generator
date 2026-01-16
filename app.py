# app.py
import streamlit as st
import os, zipfile, gdown, fitz, json, re
from collections import deque, defaultdict
from datetime import datetime, timedelta

# -------------------------------
# CONFIG
# -------------------------------
DRIVE_FILE_ID = "1S6fcsuq9KvICTsOBOdp6_WN9FhzruixM"
ZIP_PATH = "plan.zip"
EXTRACT_DIR = "syllabus_data"
STATE_FILE = "progress.json"
MAX_CONTINUOUS_DAYS = 6

st.set_page_config("📚 AI Study Planner", layout="wide")

# -------------------------------
# SESSION STATE
# -------------------------------
if "completed" not in st.session_state:
    st.session_state.completed = set()
if "calendar" not in st.session_state:
    st.session_state.calendar = []
if "practice_done" not in st.session_state:
    st.session_state.practice_done = {}

if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r") as f:
        st.session_state.completed = set(json.load(f))

# -------------------------------
# PDF / SYLLABUS FUNCTIONS
# -------------------------------
def clean_line(line):
    bad = ["annexure", "notice", "commission"]
    return line.strip() and not any(b in line.lower() for b in bad) and len(line) < 200

def read_pdf(source):
    if hasattr(source, "read"):  # UploadedFile
        doc = fitz.open(stream=source.read(), filetype="pdf")
    else:  # file path
        doc = fitz.open(source)

    lines = []
    for page in doc:
        for l in page.get_text().split("\n"):
            if clean_line(l):
                lines.append(l.strip())
    return lines

def detect_exam(lines):
    text = " ".join(lines).upper()
    if "NEET" in text:
        return "NEET"
    if "JEE" in text:
        return "IIT JEE"
    if "GATE" in text:
        return "GATE"
    return None

def parse_syllabus(root):
    data = defaultdict(lambda: defaultdict(list))
    for r, _, files in os.walk(root):
        for f in files:
            if not f.endswith(".pdf"):
                continue
            lines = read_pdf(os.path.join(r, f))
            exam = detect_exam(lines)
            if not exam:
                continue
            subject = None
            for l in lines:
                if l.isupper() and l.replace(" ", "").isalpha():
                    subject = l.title()
                elif subject:
                    data[exam][subject].append(l)
    return data

def parse_uploaded_syllabus(files):
    data = defaultdict(list)
    for f in files:
        lines = read_pdf(f)
        for l in lines:
            data["Uploaded Syllabus"].append(l)
    return data

def estimate_time_min(topic, exam=None):
    words = len(topic.split())
    complexity = len(re.findall(r"(theorem|numerical|derivation|proof)", topic.lower()))
    base = 15 + words * 3 + complexity * 10
    weight = {"NEET": 1.1, "IIT JEE": 1.3, "GATE": 1.5}.get(exam, 1)
    return int(base * weight)

# -------------------------------
# USER INPUT
# -------------------------------
st.title("📚 AI-Powered Study Planner")

custom_plan = st.checkbox("Use my own syllabus (upload PDFs)")

if custom_plan:
    exam_used = st.text_input("Enter Exam Name")
    uploaded_files = st.file_uploader(
        "Upload syllabus PDF(s)",
        type=["pdf"],
        accept_multiple_files=True
    )
    if not uploaded_files:
        st.warning("Upload at least one PDF.")
        st.stop()

    syllabus_json = parse_uploaded_syllabus(uploaded_files)
    subjects = list(syllabus_json.keys())

else:
    exam_used = st.selectbox("Select Exam", ["NEET", "IIT JEE", "GATE"])
    syllabus_source = st.radio(
        "Syllabus Source",
        ["Use default syllabus", "Upload syllabus PDF(s)"]
    )

    if syllabus_source == "Upload syllabus PDF(s)":
        uploaded_files = st.file_uploader(
            "Upload syllabus PDF(s)",
            type=["pdf"],
            accept_multiple_files=True
        )
        if not uploaded_files:
            st.warning("Upload at least one PDF.")
            st.stop()
        syllabus_json = parse_uploaded_syllabus(uploaded_files)

    else:
        if not os.path.exists(EXTRACT_DIR):
            if not os.path.exists(ZIP_PATH):
                gdown.download(
                    f"https://drive.google.com/uc?id={DRIVE_FILE_ID}",
                    ZIP_PATH,
                    quiet=True
                )
            with zipfile.ZipFile(ZIP_PATH) as z:
                z.extractall(EXTRACT_DIR)

        syllabus = parse_syllabus(EXTRACT_DIR)
        if exam_used not in syllabus:
            st.error(f"No syllabus found for {exam_used}.")
            st.stop()
        syllabus_json = syllabus[exam_used]

    subjects = list(syllabus_json.keys())

selected_subjects = st.multiselect("Select Subjects", subjects, default=subjects)

start_date = st.date_input("Start Date", datetime.today())
daily_hours = st.number_input("Daily study hours", 1.0, 12.0, 6.0)
questions_per_topic = st.number_input("Questions per topic per day", 10, 200, 30)
revision_every_n_days = st.number_input("Revision every N days", 5, 30, 7)
test_every_n_days = st.number_input("Test every N days", 7, 30, 14)

# -------------------------------
# BUILD QUEUE
# -------------------------------
def build_queue():
    q = deque()
    for s in selected_subjects:
        for t in syllabus_json[s]:
            q.append({
                "subject": s,
                "topic": t,
                "time_min": estimate_time_min(t, exam_used)
            })
    return q

# -------------------------------
# DAILY ASSIGNMENT
# -------------------------------
def assign_daily_plan(queue, daily_min):
    plan = []
    while queue and daily_min > 0:
        item = queue[0]
        alloc = min(item["time_min"], daily_min)
        plan.append({
            "subject": item["subject"],
            "topic": item["topic"],
            "time_min": alloc
        })
        item["time_min"] -= alloc
        daily_min -= alloc
        if item["time_min"] <= 0:
            queue.popleft()
    return plan

# -------------------------------
# CALENDAR
# -------------------------------
def generate_calendar(queue):
    calendar = []
    streak = 0
    day_count = 0
    cur_date = datetime.combine(start_date, datetime.min.time())

    while queue:
        daily_min = int(daily_hours * 60)
        day_type = "STUDY"
        plan = assign_daily_plan(queue, daily_min)

        if streak >= MAX_CONTINUOUS_DAYS:
            day_type = "FREE"
            plan = [{"subject": "FREE", "topic": "Rest", "time_min": 0}]
            streak = 0
        elif day_count and day_count % revision_every_n_days == 0:
            day_type = "REVISION"
            plan = [{"subject": "REVISION", "topic": "Revision", "time_min": daily_min}]
        elif day_count and day_count % test_every_n_days == 0:
            day_type = "TEST"
            plan = [{"subject": "TEST", "topic": "Test", "time_min": daily_min}]

        calendar.append({
            "date": cur_date,
            "plan": plan,
            "questions": questions_per_topic,
            "type": day_type
        })

        streak += 1 if day_type == "STUDY" else 0
        day_count += 1
        cur_date += timedelta(days=1)

    return calendar

if selected_subjects and not st.session_state.calendar:
    st.session_state.calendar = generate_calendar(build_queue())

# -------------------------------
# DISPLAY
# -------------------------------
st.header("📆 Study Plan")

for day in st.session_state.calendar:
    st.subheader(day["date"].strftime("%A, %d %b %Y"))
    for p in day["plan"]:
        st.write(f"- {p['subject']} → {p['topic']} ({p['time_min']} min)")

# -------------------------------
# SAVE STATE
# -------------------------------
with open(STATE_FILE, "w") as f:
    json.dump(list(st.session_state.completed), f)
