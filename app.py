# app.py
import streamlit as st
import fitz
import re, json
from collections import defaultdict, deque
from datetime import datetime, timedelta

# ---------------- CONFIG ----------------
MAX_CONTINUOUS_DAYS = 6
st.set_page_config("📚 AI Study Planner", layout="wide")

# ---------------- SESSION ----------------
for k in ["calendar", "completed", "practice_done"]:
    if k not in st.session_state:
        st.session_state[k] = [] if k == "calendar" else {}

# ---------------- PDF READER ----------------
def read_pdf(file):
    doc = fitz.open(stream=file.read(), filetype="pdf")
    text = []
    for page in doc:
        for line in page.get_text().split("\n"):
            line = line.strip()
            if 4 < len(line) < 150:
                text.append(line)
    return text

# ---------------- SYLLABUS PARSER (FIXED) ----------------
def extract_syllabus(files):
    syllabus = defaultdict(list)

    for f in files:
        lines = read_pdf(f)
        subject = f.name.replace(".pdf", "").title()

        for l in lines:
            # Remove bullets / numbering
            topic = re.sub(r"^[\d\.\-\)\•\–\*]+", "", l).strip()

            # Ignore garbage
            if len(topic.split()) < 3:
                continue
            if any(x in topic.lower() for x in ["page", "unit", "module"]):
                continue

            syllabus[subject].append(topic)

    # FINAL GUARANTEE
    if not syllabus:
        syllabus["General Syllabus"] = [
            l for f in files for l in read_pdf(f) if len(l.split()) >= 4
        ]

    return dict(syllabus)

# ---------------- TIME ESTIMATION ----------------
def estimate_time(topic):
    words = len(topic.split())
    complexity = len(re.findall(r"(numerical|theorem|proof|derivation)", topic.lower()))
    return 15 + words * 3 + complexity * 10

# ---------------- UI ----------------
st.title("📚 AI-Powered Study Planner")

exam = st.text_input("Enter Exam Name")
uploaded_files = st.file_uploader(
    "Upload syllabus PDF(s)",
    type=["pdf"],
    accept_multiple_files=True
)

if not uploaded_files:
    st.warning("Upload at least one syllabus PDF")
    st.stop()

syllabus = extract_syllabus(uploaded_files)

st.success("✅ Syllabus extracted successfully")
st.json({k: len(v) for k, v in syllabus.items()})

subjects = list(syllabus.keys())
selected_subjects = st.multiselect(
    "Select Subjects",
    subjects,
    default=subjects
)

start_date = st.date_input("Start Date", datetime.today())
daily_hours = st.number_input("Daily study hours", 1, 12, 6)
subjects_per_day = st.number_input(
    "Subjects per day", 1, len(selected_subjects), min(2, len(selected_subjects))
)
revision_every = st.number_input("Revision every N days", 3, 30, 7)
test_every = st.number_input("Test every N days", 5, 30, 14)

# ---------------- QUEUE BUILDER ----------------
def build_queues():
    queues = {}
    for s in selected_subjects:
        queues[s] = deque([
            {"subject": s, "topic": t, "time": estimate_time(t)}
            for t in syllabus[s]
        ])
    return queues

# ---------------- DAILY ASSIGNMENT ----------------
def assign_day(queues, minutes):
    plan = []
    active = [s for s in queues if queues[s]]

    for s in active[:subjects_per_day]:
        if minutes <= 0:
            break

        item = queues[s].popleft()
        used = min(item["time"], minutes)

        plan.append({
            "subject": s,
            "topic": item["topic"],
            "time": used
        })

        item["time"] -= used
        minutes -= used

        if item["time"] > 0:
            queues[s].appendleft(item)

    return plan

# ---------------- CALENDAR GENERATOR ----------------
def generate_calendar():
    queues = build_queues()
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

        elif day and day % revision_every == 0:
            day_type = "REVISION"
            plan = [{"subject": "REVISION", "topic": "Revise completed topics", "time": daily_hours * 60}]

        elif day and day % test_every == 0:
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

# ---------------- TABS ----------------
tab1, tab2 = st.tabs(["📖 Study Plan", "📝 Question Practice"])

# ---------------- STUDY PLAN ----------------
with tab1:
    weeks = defaultdict(list)
    for i, d in enumerate(st.session_state.calendar):
        weeks[i // 7 + 1].append(d)

    for w in weeks:
        st.subheader(f"Week {w}")
        for d in weeks[w]:
            st.markdown(f"**{d['date'].strftime('%A %d %b')} ({d['type']})**")

            carry = []
            for p in d["plan"]:
                if p["subject"] in ["FREE", "REVISION", "TEST"]:
                    st.write(f"- {p['topic']}")
                    continue

                key = f"{d['date']}_{p['topic']}"
                done = st.checkbox(
                    f"{p['subject']} → {p['topic']} ({p['time']} min)",
                    key=key
                )

                if not done:
                    carry.append(p)

            if st.button(f"Mark {d['date']} completed", key=str(d['date'])):
                if carry:
                    idx = st.session_state.calendar.index(d)
                    if idx + 1 < len(st.session_state.calendar):
                        st.session_state.calendar[idx + 1]["plan"] = carry + \
                            st.session_state.calendar[idx + 1]["plan"]

# ---------------- QUESTION PRACTICE ----------------
with tab2:
    labels = [d["date"].strftime("%d %b %Y") for d in st.session_state.calendar]
    sel = st.selectbox("Select Day", labels)
    idx = labels.index(sel)
    day = st.session_state.calendar[idx]

    n = st.number_input("Number of questions", 1, 200, 30)
    qtype = st.selectbox("Question type", ["MCQs", "Subjective", "Long"])

    for p in day["plan"]:
        if p["subject"] in ["FREE", "REVISION", "TEST"]:
            continue

        st.subheader(f"{p['subject']} → {p['topic']}")
        for i in range(n):
            st.checkbox(f"{qtype} Q{i+1}", key=f"{sel}_{p['topic']}_{i}")
