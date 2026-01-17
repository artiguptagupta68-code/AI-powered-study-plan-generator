# app.py
import streamlit as st
import os, zipfile, gdown, fitz, json, re
from collections import defaultdict, deque
from datetime import datetime, timedelta

# ----------------------------------
# CONFIG
# ----------------------------------
DRIVE_FILE_ID = "1S6fcsuq9KvICTsOBOdp6_WN9FhzruixM"
ZIP_PATH = "default_syllabus.zip"
EXTRACT_DIR = "default_syllabus"
STATE_FILE = "progress.json"
MAX_CONTINUOUS_DAYS = 6

st.set_page_config("📚 AI Study Planner", layout="wide")

# ----------------------------------
# SESSION STATE
# ----------------------------------
if "calendar" not in st.session_state:
    st.session_state.calendar = []
if "completed" not in st.session_state:
    st.session_state.completed = set()

if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r") as f:
        st.session_state.completed = set(json.load(f))

# ----------------------------------
# PDF READER
# ----------------------------------
def read_pdf(path):
    doc = fitz.open(path)
    lines = []
    for p in doc:
        for l in p.get_text().split("\n"):
            l = l.strip()
            if 3 < len(l) < 150:
                lines.append(l)
    return lines

# ----------------------------------
# HIERARCHY DETECTION
# ----------------------------------
def is_subject(line):
    return len(line.split()) <= 5 and line.replace(" ", "").isalpha()

def is_topic(line):
    return 5 < len(line.split()) <= 12

def is_subtopic(line):
    return (
        len(line.split()) > 12
        or any(x in line.lower() for x in ["-", ":", "(", "1.", "2.", "i.", "ii."])
    )

# ----------------------------------
# UNIFIED SYLLABUS PARSER
# ----------------------------------
def parse_pdf_hierarchy(pdf_paths):
    data = defaultdict(lambda: defaultdict(list))

    for path in pdf_paths:
        lines = read_pdf(path)
        subject = "General"
        topic = "Overview"

        for l in lines:
            if is_subject(l):
                subject = l.title()
                topic = "Overview"
            elif is_topic(l):
                topic = l.title()
            elif is_subtopic(l):
                data[subject][topic].append(l)

    return dict(data)

# ----------------------------------
# TIME ESTIMATION
# ----------------------------------
def estimate_time(subtopic):
    words = len(subtopic.split())
    complexity = len(re.findall(r"(numerical|derivation|proof|theorem)", subtopic.lower()))
    return 15 + words * 2 + complexity * 10

# ----------------------------------
# UI
# ----------------------------------
st.title("📚 AI-Powered Study Planner")

mode = st.radio(
    "Choose syllabus source",
    ["Available syllabus", "Upload syllabus"],
    horizontal=True
)

# ----------------------------------
# AVAILABLE SYLLABUS
# ----------------------------------
if mode == "Available syllabus":
    exam = st.selectbox("Select Exam", ["NEET", "GATE", "IIT JEE"])

    if not os.path.exists(EXTRACT_DIR):
        if not os.path.exists(ZIP_PATH):
            gdown.download(f"https://drive.google.com/uc?id={DRIVE_FILE_ID}", ZIP_PATH, quiet=True)
        with zipfile.ZipFile(ZIP_PATH) as z:
            z.extractall(EXTRACT_DIR)

    pdf_files = []
    exam_dir = os.path.join(EXTRACT_DIR, exam)

    for r, _, files in os.walk(exam_dir):
        for f in files:
            if f.endswith(".pdf"):
                pdf_files.append(os.path.join(r, f))

    syllabus_json = parse_pdf_hierarchy(pdf_files)

# ----------------------------------
# UPLOADED SYLLABUS
# ----------------------------------
else:
    exam = st.text_input("Enter Exam Name")
    uploads = st.file_uploader(
        "Upload syllabus PDFs",
        type=["pdf"],
        accept_multiple_files=True
    )

    if not uploads:
        st.warning("Please upload at least one syllabus PDF")
        st.stop()

    temp_paths = []
    for f in uploads:
        path = f"_tmp_{f.name}"
        with open(path, "wb") as out:
            out.write(f.read())
        temp_paths.append(path)

    syllabus_json = parse_pdf_hierarchy(temp_paths)

    for p in temp_paths:
        os.remove(p)

# ----------------------------------
# VALIDATION
# ----------------------------------
if not syllabus_json:
    st.error("No valid syllabus detected")
    st.stop()

# ----------------------------------
# SUBJECT SELECTION (USER DEPENDENT)
# ----------------------------------
subjects = sorted(syllabus_json.keys())
selected_subjects = st.multiselect(
    "Select subjects to include in your plan",
    subjects,
    default=subjects
)

if not selected_subjects:
    st.warning("Please select at least one subject")
    st.stop()

# ----------------------------------
# STUDY SETTINGS
# ----------------------------------
start_date = st.date_input("Start Date", datetime.today())
daily_hours = st.number_input("Daily Study Hours", 1, 12, 6)
revision_every = st.number_input("Revision every N days", 5, 30, 7)

# ----------------------------------
# BUILD QUEUE
# ----------------------------------
def build_queue():
    q = deque()
    for s in selected_subjects:
        for t, subs in syllabus_json[s].items():
            for sub in subs:
                q.append({
                    "subject": s,
                    "topic": t,
                    "subtopic": sub,
                    "time": estimate_time(sub)
                })
    return q

# ----------------------------------
# CALENDAR GENERATOR
# ----------------------------------
def generate_calendar(queue):
    cal = []
    date = datetime.combine(start_date, datetime.min.time())
    streak = 0
    day = 0

    while queue:
        if streak >= MAX_CONTINUOUS_DAYS:
            cal.append({"date": date, "type": "FREE", "plan": []})
            date += timedelta(days=1)
            streak = 0
            continue

        minutes = daily_hours * 60
        plan = []

        while queue and minutes > 0:
            item = queue.popleft()
            plan.append(item)
            minutes -= item["time"]

        day_type = "REVISION" if day and day % revision_every == 0 else "STUDY"

        cal.append({"date": date, "type": day_type, "plan": plan})
        date += timedelta(days=1)
        streak += 1
        day += 1

    return cal

# ----------------------------------
# GENERATE PLAN
# ----------------------------------
if st.button("Generate Study Plan"):
    q = build_queue()
    st.session_state.calendar = generate_calendar(q)

# ----------------------------------
# DISPLAY PLAN
# ----------------------------------
for idx, day in enumerate(st.session_state.calendar):
    st.subheader(f"{day['date'].strftime('%A, %d %b %Y')} ({day['type']})")

    carry = []
    for i, p in enumerate(day["plan"]):
        key = f"{day['date']}_{i}"
        label = f"{p['subject']} → {p['topic']} → {p['subtopic']} ({p['time']} min)"

        done = key in st.session_state.completed
        if st.checkbox(label, value=done, key=key):
            st.session_state.completed.add(key)
        else:
            carry.append(p)
            st.session_state.completed.discard(key)

    if st.button("Mark Day Completed", key=f"done_{idx}"):
        if carry and idx + 1 < len(st.session_state.calendar):
            st.session_state.calendar[idx + 1]["plan"] = (
                carry + st.session_state.calendar[idx + 1]["plan"]
            )
        st.success("Progress updated")

# ----------------------------------
# SAVE STATE
# ----------------------------------
with open(STATE_FILE, "w") as f:
    json.dump(list(st.session_state.completed), f)
