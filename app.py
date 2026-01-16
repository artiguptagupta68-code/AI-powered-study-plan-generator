# app.py
import streamlit as st
import os, json, re
import fitz
from collections import deque, defaultdict
from datetime import datetime, timedelta

# ---------------- CONFIG ----------------
st.set_page_config("📚 AI Study Planner", layout="wide")
MAX_CONTINUOUS_DAYS = 6
STATE_FILE = "progress.json"

# ---------------- SESSION STATE ----------------
if "calendar" not in st.session_state:
    st.session_state.calendar = []

if "completed" not in st.session_state:
    st.session_state.completed = set()

if "practice_done" not in st.session_state:
    st.session_state.practice_done = {}

# ---------------- PDF PARSING ----------------
def clean_line(line):
    bad = ["annexure", "notice", "commission"]
    return (
        line.strip()
        and len(line) < 120
        and not any(b in line.lower() for b in bad)
    )

def read_pdf(file):
    doc = fitz.open(stream=file.read(), filetype="pdf")
    lines = []
    for page in doc:
        for l in page.get_text().split("\n"):
            if clean_line(l):
                lines.append(l.strip())
    return lines

def parse_uploaded_syllabus(files):
    """
    Output:
    {
        "Physics": ["Kinematics", "Laws of Motion", ...],
        "Maths": ["Limits", "Derivatives", ...]
    }
    """
    data = defaultdict(list)
    for f in files:
        lines = read_pdf(f)
        subject = None
        for l in lines:
            if l.isupper() and l.replace(" ", "").isalpha():
                subject = l.title()
            elif subject:
                parts = [p.strip() for p in re.split(",|•|-", l) if len(p.strip()) > 3]
                data[subject].extend(parts)
    return dict(data)

# ---------------- TIME ESTIMATION ----------------
def estimate_time(topic):
    words = len(topic.split())
    complexity = len(re.findall(r"(numerical|derivation|theorem|proof)", topic.lower()))
    return 20 + words * 3 + complexity * 10

# ---------------- SUBJECT QUEUES (CORE FIX) ----------------
def build_subject_queues(syllabus_json, selected_subjects):
    subject_queues = {}
    for subject in selected_subjects:
        q = deque()
        for topic in syllabus_json[subject]:
            q.append({
                "subject": subject,
                "topic": topic,
                "time_min": estimate_time(topic)
            })
        subject_queues[subject] = q
    return subject_queues

# ---------------- ROUND ROBIN DAILY ASSIGN ----------------
def assign_day(subject_queues, daily_minutes):
    day_plan = []
    subjects = list(subject_queues.keys())

    while daily_minutes > 0 and any(subject_queues[s] for s in subjects):
        for s in subjects:
            if not subject_queues[s]:
                continue

            item = subject_queues[s].popleft()
            alloc = min(item["time_min"], daily_minutes)

            day_plan.append({
                "subject": s,
                "topic": item["topic"],
                "time_min": alloc
            })

            item["time_min"] -= alloc
            daily_minutes -= alloc

            if item["time_min"] > 0:
                subject_queues[s].appendleft(item)

            if daily_minutes <= 0:
                break

    return day_plan

# ---------------- CALENDAR GENERATION ----------------
def generate_calendar(subject_queues, start_date, daily_hours,
                      revision_every, test_every, questions_per_topic):
    calendar = []
    streak = 0
    day_count = 0
    cur_date = datetime.combine(start_date, datetime.min.time())

    while any(subject_queues[s] for s in subject_queues):
        day_type = "STUDY"
        plan = []

        if streak >= MAX_CONTINUOUS_DAYS:
            day_type = "FREE"
            plan = [{"subject": "FREE", "topic": "Rest / Light revision", "time_min": 0}]
            streak = 0

        elif day_count != 0 and day_count % revision_every == 0:
            day_type = "REVISION"
            plan = [{"subject": "REVISION", "topic": "Revise completed topics", "time_min": int(daily_hours * 60)}]

        elif day_count != 0 and day_count % test_every == 0:
            day_type = "TEST"
            plan = [{"subject": "TEST", "topic": "Practice Test", "time_min": int(daily_hours * 60)}]

        else:
            plan = assign_day(subject_queues, int(daily_hours * 60))
            streak += 1

        calendar.append({
            "date": cur_date,
            "type": day_type,
            "plan": plan,
            "questions": questions_per_topic
        })

        day_count += 1
        cur_date += timedelta(days=1)

    return calendar

# ---------------- UI ----------------
st.title("📚 AI-Powered Study Planner")

exam_name = st.text_input("Enter Exam Name")
uploaded_files = st.file_uploader(
    "Upload syllabus PDF(s)",
    type=["pdf"],
    accept_multiple_files=True
)

if not uploaded_files:
    st.warning("Upload syllabus PDFs to continue")
    st.stop()

syllabus_json = parse_uploaded_syllabus(uploaded_files)
if not syllabus_json:
    st.error("Could not extract syllabus")
    st.stop()

subjects = list(syllabus_json.keys())
selected_subjects = st.multiselect(
    "Select Subjects",
    subjects,
    default=subjects
)

start_date = st.date_input("Start Date", datetime.today())
daily_hours = st.number_input("Daily study hours", 1.0, 12.0, 6.0)
questions_per_topic = st.number_input("Questions per topic", 5, 200, 30)
revision_every = st.number_input("Revision every N days", 3, 30, 7)
test_every = st.number_input("Test every N days", 5, 30, 14)

if st.button("🚀 Generate Study Plan"):
    subject_queues = build_subject_queues(syllabus_json, selected_subjects)
    st.session_state.calendar = generate_calendar(
        subject_queues,
        start_date,
        daily_hours,
        revision_every,
        test_every,
        questions_per_topic
    )

# ---------------- STUDY PLAN TAB ----------------
tab1, tab2 = st.tabs(["📖 Study Plan", "📝 Question Practice"])

with tab1:
    for day in st.session_state.calendar:
        st.subheader(f"{day['date'].strftime('%A, %d %b %Y')} ({day['type']})")
        for i, p in enumerate(day["plan"]):
            if p["subject"] in ["FREE", "REVISION", "TEST"]:
                st.markdown(f"- **{p['topic']}**")
                continue

            key = f"{day['date']}_{p['subject']}_{p['topic']}"
            st.checkbox(
                f"{p['subject']} → {p['topic']} ({p['time_min']} min)",
                key=key
            )

# ---------------- QUESTION PRACTICE ----------------
with tab2:
    if not st.session_state.calendar:
        st.info("Generate study plan first")
        st.stop()

    labels = [d["date"].strftime("%A, %d %b %Y") for d in st.session_state.calendar]
    sel = st.selectbox("Select Day", labels)
    idx = labels.index(sel)
    day = st.session_state.calendar[idx]

    q_count = st.number_input("Number of questions", 1, 200, day["questions"])
    q_type = st.selectbox("Question type", ["MCQs", "Subjective", "Long Questions"])

    for p in day["plan"]:
        if p["subject"] in ["FREE", "REVISION", "TEST"]:
            continue

        st.markdown(f"### {p['subject']} → {p['topic']}")
        for i in range(q_count):
            st.checkbox(
                f"{q_type} Q{i+1}",
                key=f"{sel}_{p['topic']}_{i}"
            )
