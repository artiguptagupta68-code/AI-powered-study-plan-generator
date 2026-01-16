# app.py
import streamlit as st
import fitz
import os, json, re
from collections import deque, defaultdict
from datetime import datetime, timedelta

# ---------------------------------
# CONFIG
# ---------------------------------
MAX_CONTINUOUS_DAYS = 6
STATE_FILE = "progress.json"

st.set_page_config("📚 AI Study Planner", layout="wide")

# ---------------------------------
# SESSION STATE
# ---------------------------------
for key, default in {
    "calendar": [],
    "completed": set(),
    "practice_done": {}
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ---------------------------------
# PDF HELPERS
# ---------------------------------
def read_pdf(file):
    doc = fitz.open(stream=file.read(), filetype="pdf")
    lines = []
    for page in doc:
        for l in page.get_text().split("\n"):
            l = l.strip()
            if len(l) > 3 and len(l) < 120:
                lines.append(l)
    return lines

def parse_uploaded_syllabus(files):
    """
    Robust syllabus parser
    Works for real exam PDFs
    """
    syllabus = defaultdict(list)
    current_subject = None

    SUBJECT_PATTERNS = [
        r"^UNIT\s+\d+",
        r"^MODULE\s+\d+",
        r"^SECTION\s+\d+",
        r"^[A-Z][A-Za-z\s]{3,}$"
    ]

    for f in files:
        lines = read_pdf(f)

        for line in lines:
            # SUBJECT
            if any(re.match(p, line, re.IGNORECASE) for p in SUBJECT_PATTERNS):
                current_subject = line.title()
                continue

            # TOPIC
            if current_subject:
                topic = re.sub(r"^[\d\.\)\-•–]+\s*", "", line)
                if len(topic.split()) >= 3:
                    syllabus[current_subject].append(topic)

    # Fallback if subject not detected
    if not syllabus:
        syllabus["General Topics"] = [
            l for f in files for l in read_pdf(f) if len(l.split()) >= 4
        ]

    return dict(syllabus)

# ---------------------------------
# TIME ESTIMATION
# ---------------------------------
def estimate_time(topic):
    words = len(topic.split())
    complexity = len(re.findall(r"(numerical|theorem|derivation|proof)", topic.lower()))
    return 15 + words * 3 + complexity * 10

# ---------------------------------
# UI: EXAM & SYLLABUS
# ---------------------------------
st.title("📚 AI-Powered Study Planner")

custom = st.checkbox("Create study plan using my own syllabus")

if custom:
    exam_name = st.text_input("Enter Exam Name")
    uploaded = st.file_uploader(
        "Upload syllabus PDFs",
        type=["pdf"],
        accept_multiple_files=True
    )

    if not uploaded:
        st.warning("Upload at least one syllabus PDF")
        st.stop()

    syllabus = parse_uploaded_syllabus(uploaded)

else:
    st.info("Please use custom syllabus mode for now (default syllabus removed for stability)")
    st.stop()

st.success("✅ Syllabus extracted successfully")
st.json(syllabus)

subjects = list(syllabus.keys())
selected_subjects = st.multiselect(
    "Select Subjects",
    subjects,
    default=subjects
)

# ---------------------------------
# STUDY PREFERENCES
# ---------------------------------
start_date = st.date_input("Start Date", datetime.today())
daily_hours = st.number_input("Daily Study Hours", 1, 12, 6)
subjects_per_day = st.number_input("Subjects per day", 1, len(selected_subjects), min(2, len(selected_subjects)))
revision_freq = st.number_input("Revision every N days", 3, 30, 7)
test_freq = st.number_input("Test every N days", 5, 30, 14)

# ---------------------------------
# BUILD ROUND-ROBIN QUEUE (FIXED)
# ---------------------------------
def build_queue():
    queues = {
        s: deque(
            {"subject": s, "topic": t, "time": estimate_time(t)}
            for t in syllabus[s]
        )
        for s in selected_subjects
    }
    return queues

# ---------------------------------
# DAILY ASSIGNMENT (MULTI SUBJECT FIX)
# ---------------------------------
def assign_day(queues, daily_minutes):
    plan = []
    active_subjects = [s for s in queues if queues[s]]

    for s in active_subjects[:subjects_per_day]:
        if daily_minutes <= 0:
            break

        item = queues[s].popleft()
        allocated = min(item["time"], daily_minutes)

        plan.append({
            "subject": s,
            "topic": item["topic"],
            "time": allocated
        })

        item["time"] -= allocated
        daily_minutes -= allocated

        if item["time"] > 0:
            queues[s].appendleft(item)

    return plan

# ---------------------------------
# GENERATE CALENDAR
# ---------------------------------
def generate_calendar():
    queues = build_queue()
    calendar = []
    date = start_date
    day = 0
    streak = 0

    while any(queues[s] for s in queues):
        day_type = "STUDY"

        if streak >= MAX_CONTINUOUS_DAYS:
            day_type = "FREE"
            plan = [{"subject": "FREE", "topic": "Rest Day", "time": 0}]
            streak = 0

        elif day > 0 and day % revision_freq == 0:
            day_type = "REVISION"
            plan = [{"subject": "REVISION", "topic": "Revise previous topics", "time": daily_hours * 60}]

        elif day > 0 and day % test_freq == 0:
            day_type = "TEST"
            plan = [{"subject": "TEST", "topic": "Mock Test", "time": daily_hours * 60}]

        else:
            plan = assign_day(queues, daily_hours * 60)
            streak += 1

        calendar.append({
            "date": date,
            "type": day_type,
            "plan": plan
        })

        date += timedelta(days=1)
        day += 1

    return calendar

if not st.session_state.calendar:
    st.session_state.calendar = generate_calendar()

# ---------------------------------
# TABS
# ---------------------------------
tab1, tab2 = st.tabs(["📖 Study Plan", "📝 Question Practice"])

# ---------------------------------
# STUDY PLAN TAB
# ---------------------------------
with tab1:
    st.header("📆 Weekly Study Calendar")

    weeks = defaultdict(list)
    for i, d in enumerate(st.session_state.calendar):
        weeks[i // 7 + 1].append(d)

    for w in weeks:
        st.subheader(f"Week {w}")

        for day in weeks[w]:
            st.markdown(f"**{day['date'].strftime('%A %d %b')} ({day['type']})**")

            unfinished = []
            for i, p in enumerate(day["plan"]):
                if p["subject"] in ["FREE", "REVISION", "TEST"]:
                    st.write(f"- {p['topic']}")
                    continue

                key = f"{day['date']}_{p['topic']}"
                done = key in st.session_state.completed

                if st.checkbox(
                    f"{p['subject']} → {p['topic']} ({p['time']} min)",
                    value=done,
                    key=key
                ):
                    st.session_state.completed.add(key)
                else:
                    unfinished.append(p)

            if st.button(f"Mark {day['date']} completed", key=str(day['date'])):
                if unfinished:
                    st.warning("Unfinished topics moved to next day")
                    idx = st.session_state.calendar.index(day)
                    if idx + 1 < len(st.session_state.calendar):
                        st.session_state.calendar[idx + 1]["plan"] = unfinished + \
                            st.session_state.calendar[idx + 1]["plan"]

# ---------------------------------
# QUESTION PRACTICE TAB
# ---------------------------------
with tab2:
    st.header("📝 Question Practice")

    labels = [d["date"].strftime("%d %b %Y") for d in st.session_state.calendar]
    sel = st.selectbox("Select Day", labels)

    idx = labels.index(sel)
    day = st.session_state.calendar[idx]

    num_q = st.number_input("Number of Questions", 1, 200, 30)
    qtype = st.selectbox("Question Type", ["MCQs", "Subjective", "Long"])

    for p in day["plan"]:
        if p["subject"] in ["FREE", "REVISION", "TEST"]:
            continue

        st.subheader(f"{p['subject']} → {p['topic']}")
        for i in range(num_q):
            st.checkbox(
                f"{qtype} Q{i+1}",
                key=f"{sel}_{p['topic']}_{i}"
            )

# ---------------------------------
# SAVE STATE
# ---------------------------------
with open(STATE_FILE, "w") as f:
    json.dump(list(st.session_state.completed), f)
