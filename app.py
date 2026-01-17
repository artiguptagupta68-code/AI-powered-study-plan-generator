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

# ----------------------------------
# PDF READER (TEXT ONLY, NO OCR)
# ----------------------------------
def read_pdf(path):
    doc = fitz.open(path)
    lines = []
    for page in doc:
        text = page.get_text()
        for l in text.split("\n"):
            l = l.strip()
            if 3 < len(l) < 200:
                lines.append(l)
    return lines

# ----------------------------------
# FLEXIBLE HIERARCHY DETECTION
# ----------------------------------
def is_subject(line):
    return (
        line.isupper()
        or re.match(r"^[IVX]+\.?\s+[A-Za-z ]+$", line)
        or len(line.split()) <= 4
    )

def is_topic(line):
    return bool(re.match(r"^\d+(\.\d+)?\s+.+", line))

def is_subtopic(line):
    return (
        line.startswith(("•", "-", "–"))
        or re.match(r"^\d+(\.\d+){2,}\s+.+", line)
        or len(line.split()) > 6
    )

# ----------------------------------
# VERY ROBUST PARSER (NEVER RETURNS EMPTY)
# ----------------------------------
def parse_pdf_hierarchy(pdf_paths):
    data = defaultdict(lambda: defaultdict(list))

    for path in pdf_paths:
        lines = read_pdf(path)

        subject = "General"
        topic = "General Topics"

        for l in lines:
            clean = re.sub(r"^[•\-\–\d\.\)\(]+", "", l).strip()

            if is_subject(clean):
                subject = clean.title()
                topic = "General Topics"

            elif is_topic(clean):
                topic = clean.title()

            else:
                data[subject][topic].append(clean)

    # GUARANTEED NON-EMPTY
    if not data:
        data["General"]["General Topics"] = ["Syllabus Content"]

    return dict(data)

# ----------------------------------
# TIME ESTIMATION
# ----------------------------------
def estimate_time(text):
    return 15 + len(text.split()) * 2

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
            gdown.download(
                f"https://drive.google.com/uc?id={DRIVE_FILE_ID}",
                ZIP_PATH,
                quiet=True
            )
        with zipfile.ZipFile(ZIP_PATH) as z:
            z.extractall(EXTRACT_DIR)

    exam_dir = os.path.join(EXTRACT_DIR, exam)
    pdfs = [
        os.path.join(r, f)
        for r, _, files in os.walk(exam_dir)
        for f in files if f.endswith(".pdf")
    ]

    syllabus_json = parse_pdf_hierarchy(pdfs)

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
        st.warning("Upload at least one syllabus PDF")
        st.stop()

    temp = []
    for f in uploads:
        path = f"_tmp_{f.name}"
        with open(path, "wb") as out:
            out.write(f.read())
        temp.append(path)

    syllabus_json = parse_pdf_hierarchy(temp)

    for p in temp:
        os.remove(p)

# ----------------------------------
# SUBJECT SELECTION (USER CONTROLLED)
# ----------------------------------
subjects = sorted(syllabus_json.keys())

selected_subjects = st.multiselect(
    "Select subjects",
    subjects,
    default=subjects
)

if not selected_subjects:
    st.warning("Select at least one subject")
    st.stop()

# ----------------------------------
# STUDY SETTINGS
# ----------------------------------
start_date = st.date_input("Start Date", datetime.today())
daily_hours = st.number_input("Daily study hours", 1, 12, 6)

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
# GENERATE PLAN
# ----------------------------------
def generate_calendar(queue):
    cal = []
    date = datetime.combine(start_date, datetime.min.time())

    while queue:
        minutes = daily_hours * 60
        plan = []

        while queue and minutes > 0:
            item = queue.popleft()
            plan.append(item)
            minutes -= item["time"]

        cal.append({"date": date, "plan": plan})
        date += timedelta(days=1)

    return cal

if st.button("Generate Study Plan"):
    st.session_state.calendar = generate_calendar(build_queue())

# ----------------------------------
# DISPLAY PLAN
# ----------------------------------
for idx, day in enumerate(st.session_state.calendar):
    st.subheader(day["date"].strftime("%A, %d %b %Y"))

    carry = []
    for i, p in enumerate(day["plan"]):
        key = f"{idx}_{i}"
        label = f"{p['subject']} → {p['topic']} → {p['subtopic']}"

        if not st.checkbox(label, key=key):
            carry.append(p)

    if st.button("Day Completed", key=f"d_{idx}") and carry:
        if idx + 1 < len(st.session_state.calendar):
            st.session_state.calendar[idx + 1]["plan"] = (
                carry + st.session_state.calendar[idx + 1]["plan"]
            )
