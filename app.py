# app.py
import streamlit as st
import os, zipfile, gdown, fitz, json, re
from collections import deque, defaultdict
from datetime import datetime, timedelta

# ======================================================
# CONFIG
# ======================================================
DRIVE_FILE_ID = "1S6fcsuq9KvICTsOBOdp6_WN9FhzruixM"
ZIP_PATH = "plan.zip"
EXTRACT_DIR = "syllabus_data"
STATE_FILE = "progress.json"
MAX_CONTINUOUS_DAYS = 6

st.set_page_config(page_title="📚 AI Study Planner", layout="wide")
st.title("📚 AI Study Planner")

# ======================================================
# SESSION STATE
# ======================================================
if "completed" not in st.session_state:
    st.session_state.completed = set()
if "calendar" not in st.session_state:
    st.session_state.calendar = []
if "practice_done" not in st.session_state:
    st.session_state.practice_done = {}

if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r") as f:
        st.session_state.completed = set(json.load(f))

# ======================================================
# PDF HELPERS
# ======================================================
def clean_line(line):
    bad = ["annexure", "notice", "commission"]
    return (
        line.strip()
        and len(line) < 120
        and not any(b in line.lower() for b in bad)
    )

def read_pdf(path):
    doc = fitz.open(path)
    lines = []
    for page in doc:
        for l in page.get_text().split("\n"):
            if clean_line(l):
                lines.append(l.strip())
    return lines

# ======================================================
# SYLLABUS PARSERS
# ======================================================
def detect_exam(lines):
    text = " ".join(lines).upper()
    if "NEET" in text:
        return "NEET"
    if "JEE" in text:
        return "IIT JEE"
    if "GATE" in text:
        return "GATE"
    return None

def parse_syllabus(root_dir):
    data = defaultdict(lambda: defaultdict(list))
    for r, _, files in os.walk(root_dir):
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
                    topics = [
                        p.strip() for p in l.split(",")
                        if len(p.strip()) > 3
                    ]
                    data[exam][subject].extend(topics)
    return data

def parse_uploaded_syllabus(files):
    data = defaultdict(list)
    for f in files:
        temp_path = f"__temp_{f.name}"
        with open(temp_path, "wb") as out:
            out.write(f.read())

        lines = read_pdf(temp_path)
        os.remove(temp_path)

        subject = None
        for l in lines:
            if l.isupper() and l.replace(" ", "").isalpha():
                subject = l.title()
            elif subject:
                parts = [
                    p.strip() for p in l.split(",")
                    if len(p.strip()) > 3
                ]
                data[subject].extend(parts)
    return dict(data)

# ======================================================
# TIME ESTIMATION
# ======================================================
def estimate_time_min(topic):
    words = len(topic.split())
    complexity = len(
        re.findall(r"(theorem|numerical|derivation|proof)", topic.lower())
    )
    return max(15, words * 3 + complexity * 10)

# ======================================================
# SYLLABUS SOURCE SELECTION
# ======================================================
syllabus_choice = st.radio(
    "Choose syllabus source",
    ["Available syllabus", "Upload syllabus"],
    horizontal=True
)

# ---------- OPTION 1: AVAILABLE SYLLABUS ----------
if syllabus_choice == "Available syllabus":
    exam = st.selectbox("Select Exam", ["NEET", "IIT JEE", "GATE"])

    if not os.path.exists(EXTRACT_DIR):
        if not os.path.exists(ZIP_PATH):
            gdown.download(
                f"https://drive.google.com/uc?id={DRIVE_FILE_ID}",
                ZIP_PATH,
                quiet=True
            )
        with zipfile.ZipFile(ZIP_PATH) as z:
            z.extractall(EXTRACT_DIR)

    syllabus_all = parse_syllabus(EXTRACT_DIR)
    if exam not in syllabus_all:
        st.error(f"No syllabus found for {exam}")
        st.stop()

    syllabus_json = syllabus_all[exam]

# ---------- OPTION 2: UPLOAD SYLLABUS ----------
else:
    exam = st.text_input("Exam Name", value="Custom Exam")
    uploaded_files = st.file_uploader(
        "Upload syllabus PDF(s)",
        type=["pdf"],
        accept_multiple_files=True
    )
    if not uploaded_files:
        st.warning("Please upload at least one PDF")
        st.stop()

    syllabus_json = parse_uploaded_syllabus(uploaded_files)
    if not syllabus_json:
        st.error("No valid syllabus detected")
        st.stop()

subjects = list(syllabus_json.keys())

# ======================================================
# STUDY SETTINGS
# ======================================================
selected_subjects = st.multiselect(
    "Select subjects",
    subjects,
    default=subjects
)

start_date = st.date_input("Start Date", datetime.today())
daily_hours = st.number_input("Daily study hours", 1.0, 12.0, 6.0)
questions_per_topic = st.number_input("Questions per topic", 10, 200, 30)
revision_every_n_days = st.number_input("Revision every N days", 5, 30, 7)
test_every_n_days = st.number_input("Test every N days", 7, 30, 14)

# ======================================================
# QUEUE BUILDER
# ======================================================
def build_queue():
    q = deque()
    for s in selected_subjects:
        for t in syllabus_json[s]:
            q.append({
                "subject": s,
                "topic": t,
                "time": estimate_time_min(t)
            })
    return q

# ======================================================
# DAILY ASSIGNMENT
# ======================================================
def assign_daily_plan(queue, daily_min):
    plan = []
    while daily_min > 0 and queue:
        item = queue[0]
        alloc = min(item["time"], daily_min)
        plan.append({
            "subject": item["subject"],
            "topic": item["topic"],
            "minutes": alloc
        })
        item["time"] -= alloc
        daily_min -= alloc
        if item["time"] <= 0:
            queue.popleft()
    return plan

# ======================================================
# CALENDAR GENERATOR
# ======================================================
def generate_calendar(queue):
    calendar = []
    cur_date = datetime.combine(start_date, datetime.min.time())
    streak = 0
    day_count = 0

    while queue:
        day_type = "STUDY"
        daily_min = int(daily_hours * 60)
        plan = assign_daily_plan(queue, daily_min)

        if streak >= MAX_CONTINUOUS_DAYS:
            day_type = "FREE"
            plan = [{"subject": "FREE", "topic": "Rest", "minutes": 0}]
            streak = 0
        elif day_count and day_count % revision_every_n_days == 0:
            day_type = "REVISION"
            plan = [{"subject": "REVISION", "topic": "Revision", "minutes": daily_min}]
        elif day_count and day_count % test_every_n_days == 0:
            day_type = "TEST"
            plan = [{"subject": "TEST", "topic": "Mock Test", "minutes": daily_min}]

        calendar.append({
            "date": cur_date,
            "type": day_type,
            "plan": plan
        })

        streak += 1 if day_type == "STUDY" else 0
        day_count += 1
        cur_date += timedelta(days=1)

    return calendar

if st.button("🚀 Generate Study Plan"):
    st.session_state.calendar = generate_calendar(build_queue())
    st.success("Study plan generated")

# ======================================================
# TABS
# ======================================================
tab1, tab2 = st.tabs(["📖 Study Plan", "📝 Question Practice"])

# ---------------- STUDY PLAN TAB ----------------
with tab1:
    for i, day in enumerate(st.session_state.calendar):
        label = day["date"].strftime("%A, %d %b %Y")
        st.subheader(f"{label} ({day['type']} DAY)")

        unfinished = []
        for j, p in enumerate(day["plan"]):
            key = f"{label}_{j}_{p['topic']}"
            checked = key in st.session_state.completed

            if st.checkbox(
                f"{p['subject']} → {p['topic']} ({p['minutes']} min)",
                value=checked,
                key=key
            ):
                st.session_state.completed.add(key)
            else:
                st.session_state.completed.discard(key)
                if p["subject"] not in ["FREE", "REVISION", "TEST"]:
                    unfinished.append(p)

        if st.button(f"Mark Day Completed ({label})", key=f"done_{i}"):
            if unfinished:
                st.warning("Unfinished topics moved to next day")
                if i + 1 >= len(st.session_state.calendar):
                    st.session_state.calendar.append({
                        "date": day["date"] + timedelta(days=1),
                        "type": "STUDY",
                        "plan": []
                    })
                st.session_state.calendar[i + 1]["plan"] = (
                    unfinished + st.session_state.calendar[i + 1]["plan"]
                )
            else:
                st.success("All topics completed 🎉")

# ---------------- QUESTION PRACTICE TAB ----------------
with tab2:
    if st.session_state.calendar:
        days = [d["date"].strftime("%A, %d %b %Y") for d in st.session_state.calendar]
        sel = st.selectbox("Select Day", days)
        idx = days.index(sel)
        day = st.session_state.calendar[idx]

        for p in day["plan"]:
            if p["subject"] in ["FREE", "REVISION", "TEST"]:
                continue
            st.markdown(f"**{p['subject']} → {p['topic']}**")
            for q in range(questions_per_topic):
                st.checkbox(
                    f"Q{q+1} on {p['topic']}",
                    key=f"{sel}_{p['topic']}_q{q}"
                )

# ======================================================
# SAVE STATE
# ======================================================
with open(STATE_FILE, "w") as f:
    json.dump(list(st.session_state.completed), f)
