# app.py
import streamlit as st
import os, zipfile, gdown, fitz, json
from collections import defaultdict, deque
from datetime import datetime, timedelta

# -------------------------------------------------
# CONFIG
# -------------------------------------------------
DRIVE_FILE_ID = "1S6fcsuq9KvICTsOBOdp6_WN9FhzruixM"
ZIP_PATH = "plan.zip"
EXTRACT_DIR = "syllabus_data"
STATE_FILE = "progress.json"
MIN_SUBTOPIC_TIME_H = 0.33  # 20 minutes

DAY_STUDY = "Study"
DAY_REVISION = "Revision"
DAY_FREE = "Free"
DAY_TEST = "Test"

st.set_page_config("📚 Study Planner", layout="wide")

# -------------------------------------------------
# SESSION STATE
# -------------------------------------------------
if "completed_subtopics" not in st.session_state:
    st.session_state.completed_subtopics = set()

if "calendar_cache" not in st.session_state:
    st.session_state.calendar_cache = []

if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r") as f:
        st.session_state.completed_subtopics = set(json.load(f))

# -------------------------------------------------
# DOWNLOAD & EXTRACT
# -------------------------------------------------
if not os.path.exists(ZIP_PATH):
    gdown.download(f"https://drive.google.com/uc?id={DRIVE_FILE_ID}", ZIP_PATH)

if not os.path.exists(EXTRACT_DIR):
    with zipfile.ZipFile(ZIP_PATH, "r") as z:
        z.extractall(EXTRACT_DIR)

# -------------------------------------------------
# PDF CLEANING
# -------------------------------------------------
def is_garbage(line):
    bad = ["government", "commission", "notice", "annexure"]
    return any(b in line.lower() for b in bad) or len(line) > 120

def read_pdf(path):
    doc = fitz.open(path)
    lines = []
    for p in doc:
        for l in p.get_text().split("\n"):
            l = l.strip()
            if l and not is_garbage(l):
                lines.append(l)
    return lines

# -------------------------------------------------
# EXAM DETECTION
# -------------------------------------------------
def detect_exam(lines):
    t = " ".join(lines).upper()
    if "NEET" in t:
        return "NEET", "UG"
    if "JEE" in t:
        return "IIT JEE", "JEE Main"
    if "GATE" in t:
        return "GATE", "General"
    return None, None

# -------------------------------------------------
# PARSE SYLLABUS
# -------------------------------------------------
def parse_syllabus(root):
    data = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))
    for r, _, files in os.walk(root):
        for f in files:
            if not f.endswith(".pdf"):
                continue
            path = os.path.join(r, f)
            lines = read_pdf(path)
            exam, stage = detect_exam(lines)
            if not exam:
                continue

            subj, topic = None, None
            for l in lines:
                if l.isupper() and l.replace(" ", "").isalpha():
                    subj, topic = l.title(), None
                elif ":" in l and subj:
                    topic = l.replace(":", "").strip()
                elif subj and topic:
                    parts = [p.strip() for p in l.split(",") if len(p) > 3]
                    data[exam][stage][subj][topic].extend(parts)
    return data

syllabus = parse_syllabus(EXTRACT_DIR)

# -------------------------------------------------
# UI INPUTS
# -------------------------------------------------
st.title("📅 Competitive Exam Study Planner")
st.markdown("---")

exam = st.selectbox("Select Exam", syllabus.keys())
stage = st.selectbox("Select Stage", syllabus[exam].keys())
subjects = list(syllabus[exam][stage].keys())
selected_subjects = st.multiselect("Subjects (priority order)", subjects)

start_date = st.date_input("📆 Start Date", datetime.today())
total_days = st.number_input("🗓️ Total days", min_value=7, value=90)
daily_hours = st.number_input("⏱️ Daily study hours", min_value=1.0, value=6.0)

st.markdown("### 📌 Study Structure Options")

subjects_per_day = st.radio(
    "How many subjects per day?",
    options=[1, 2, 3],
    index=1
)

daily_questions = st.number_input(
    "📖 Daily practice questions",
    min_value=0,
    value=50
)

revision_gap_days = st.number_input(
    "🔁 Revision after every N study days",
    min_value=0,
    value=6
)

free_day_frequency = st.number_input(
    "💤 Free day every N days",
    min_value=0,
    value=14
)

test_day_frequency = st.number_input(
    "📝 Test day every N days",
    min_value=0,
    value=7
)

# -------------------------------------------------
# COLORS
# -------------------------------------------------
COLORS = ["#4CAF50","#2196F3","#FF9800","#9C27B0","#009688","#E91E63"]
subject_color = {s: COLORS[i % len(COLORS)] for i, s in enumerate(selected_subjects)}

# -------------------------------------------------
# BUILD SUBJECT QUEUES
# -------------------------------------------------
def build_subject_queues():
    subject_queues = {s: deque() for s in selected_subjects}
    for s in selected_subjects:
        for t, subs in syllabus[exam][stage][s].items():
            for sub in subs:
                est_h = max(0.3 + 0.05 * len(sub.split()), MIN_SUBTOPIC_TIME_H)
                subject_queues[s].append({
                    "subject": s,
                    "subtopic": sub,
                    "time_h": est_h,
                    "time_min": round(est_h * 60)
                })
    return subject_queues

# -------------------------------------------------
# PLAN GENERATION
# -------------------------------------------------
if selected_subjects:
    subject_queues = build_subject_queues()
    calendar = []
    cur_date = datetime.combine(start_date, datetime.min.time())
    study_day_counter = 0
    subject_cycle = deque(selected_subjects)

    for day_idx in range(total_days):
        day_type = DAY_STUDY

        if free_day_frequency and day_idx > 0 and day_idx % free_day_frequency == 0:
            day_type = DAY_FREE
        elif test_day_frequency and day_idx > 0 and day_idx % test_day_frequency == 0:
            day_type = DAY_TEST
        elif revision_gap_days and study_day_counter > 0 and study_day_counter % revision_gap_days == 0:
            day_type = DAY_REVISION

        plan = []

        if day_type == DAY_STUDY:
            rem_h = daily_hours
            today_subjects = []

            for _ in range(subjects_per_day):
                subject_cycle.rotate(-1)
                today_subjects.append(subject_cycle[0])

            while rem_h > 0 and any(subject_queues[s] for s in today_subjects):
                for s in today_subjects:
                    if not subject_queues[s] or rem_h <= 0:
                        continue
                    item = subject_queues[s].popleft()
                    alloc = min(item["time_h"], rem_h)
                    plan.append({**item, "time_h": alloc, "time_min": round(alloc * 60)})
                    rem_h -= alloc

            study_day_counter += 1

        elif day_type == DAY_REVISION:
            plan.append({
                "subject": "REVISION",
                "subtopic": "Revise notes & previous mistakes",
                "time_min": int(daily_hours * 60)
            })

        elif day_type == DAY_TEST:
            plan.append({
                "subject": "TEST",
                "subtopic": "Mock test + analysis",
                "time_min": int(daily_hours * 60)
            })

        elif day_type == DAY_FREE:
            plan.append({
                "subject": "FREE",
                "subtopic": "Rest / light revision",
                "time_min": 0
            })

        calendar.append({
            "date": cur_date,
            "day_type": day_type,
            "questions": daily_questions if day_type == DAY_STUDY else 0,
            "plan": plan
        })

        cur_date += timedelta(days=1)

    st.session_state.calendar_cache = calendar

    # -------------------------------------------------
    # WEEKLY VIEW
    # -------------------------------------------------
    st.header("📆 Weekly Study Calendar")

    weeks = defaultdict(list)
    for day in calendar:
        weeks[day["date"].isocalendar().week].append(day)

    tabs = st.tabs([f"Week {w}" for w in sorted(weeks.keys())])

    for tab, w in zip(tabs, sorted(weeks.keys())):
        with tab:
            for day in weeks[w]:
                st.markdown(
                    f"### {day['date'].strftime('%A, %d %b %Y')} "
                    f"({day['day_type']})  |  📖 {day['questions']} Questions"
                )

                for i, s in enumerate(day["plan"]):
                    st.markdown(
                        f"- **{s['subject']}** → {s['subtopic']} "
                        f"({s.get('time_min', 0)} min)"
                    )

    # -------------------------------------------------
    # SAVE STATE
    # -------------------------------------------------
    with open(STATE_FILE, "w") as f:
        json.dump(list(st.session_state.completed_subtopics), f)
