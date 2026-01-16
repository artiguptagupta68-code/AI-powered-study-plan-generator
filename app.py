# app.py
import streamlit as st
import fitz
import os
import json
import re
from collections import defaultdict, deque
from datetime import datetime, timedelta

# ----------------------------------
# CONFIG
# ----------------------------------
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
if "practice" not in st.session_state:
    st.session_state.practice = {}

# ----------------------------------
# PDF UTILITIES
# ----------------------------------
def read_pdf(file):
    doc = fitz.open(stream=file.read(), filetype="pdf")
    lines = []
    for page in doc:
        for l in page.get_text().split("\n"):
            l = l.strip()
            if len(l) >= 4 and len(l) < 150:
                lines.append(l)
    return lines

# ----------------------------------
# 🔥 BULLETPROOF SYLLABUS EXTRACTION
# Subject → Topic → Subtopic
# ----------------------------------
def extract_syllabus(files):
    syllabus = defaultdict(lambda: defaultdict(list))

    for f in files:
        subject = f.name.replace(".pdf", "").strip().title()
        lines = read_pdf(f)

        current_topic = None
        topic_counter = 1

        for line in lines:
            clean = re.sub(r"^[\d\.\-\)\•\*]+", "", line).strip()

            if len(clean) < 4:
                continue

            # Topic detection
            if (
                clean.isupper()
                or clean.istitle()
                or re.match(r"^\d+[\.\)]", line)
            ):
                current_topic = clean
                syllabus[subject][current_topic] = []
                continue

            # Subtopic fallback
            if current_topic is None:
                current_topic = f"Topic {topic_counter}"
                syllabus[subject][current_topic] = []
                topic_counter += 1

            syllabus[subject][current_topic].append(clean)

    # Absolute fallback (never empty)
    if not syllabus:
        syllabus["General Subject"]["General Topic"] = [
            "Review uploaded syllabus manually"
        ]

    return syllabus

# ----------------------------------
# TIME ESTIMATION (MINUTES)
# ----------------------------------
def estimate_time(subtopic):
    words = len(subtopic.split())
    complexity = len(re.findall(r"(theorem|proof|numerical|derivation)", subtopic.lower()))
    return max(20, 10 + words * 3 + complexity * 10)

# ----------------------------------
# UI: EXAM & SYLLABUS
# ----------------------------------
st.title("📚 AI-Powered Study Planner")

exam_name = st.text_input("Enter Exam Name", placeholder="e.g. GATE Mechanical / UPSC / Custom Exam")

uploaded_files = st.file_uploader(
    "Upload syllabus PDF(s)",
    type=["pdf"],
    accept_multiple_files=True
)

if not uploaded_files:
    st.info("👆 Upload syllabus PDFs to generate study plan")
    st.stop()

syllabus = extract_syllabus(uploaded_files)

subjects = list(syllabus.keys())
selected_subjects = st.multiselect("Select Subjects", subjects, default=subjects)

start_date = st.date_input("Start Date", datetime.today())
daily_hours = st.number_input("Daily Study Hours", 1.0, 12.0, 6.0)
subjects_per_day = st.number_input("Subjects per day", 1, len(selected_subjects), min(2, len(selected_subjects)))

revision_gap = st.number_input("Revision Day Frequency", 5, 30, 7)
test_gap = st.number_input("Test Day Frequency", 7, 30, 14)

# ----------------------------------
# BUILD QUEUE (MULTI-SUBJECT SAFE)
# ----------------------------------
def build_queue():
    q = deque()
    for subject in selected_subjects:
        for topic, subs in syllabus[subject].items():
            for sub in subs:
                q.append({
                    "subject": subject,
                    "topic": topic,
                    "subtopic": sub,
                    "time": estimate_time(sub)
                })
    return q

# ----------------------------------
# CALENDAR GENERATION
# ----------------------------------
def generate_calendar(queue):
    calendar = []
    cur_date = start_date
    streak = 0
    day_count = 0

    while queue:
        daily_minutes = int(daily_hours * 60)
        today = []

        subjects_today = list({q["subject"] for q in list(queue)[:subjects_per_day]})

        while daily_minutes > 0 and queue:
            item = queue.popleft()

            if item["subject"] not in subjects_today:
                queue.append(item)
                continue

            alloc = min(item["time"], daily_minutes)
            today.append({**item, "time": alloc})
            item["time"] -= alloc
            daily_minutes -= alloc

            if item["time"] > 0:
                queue.appendleft(item)

        day_type = "STUDY"

        if streak >= MAX_CONTINUOUS_DAYS:
            day_type = "FREE"
            today = []
            streak = 0
        elif day_count % revision_gap == 0 and day_count != 0:
            day_type = "REVISION"
            today = []
        elif day_count % test_gap == 0 and day_count != 0:
            day_type = "TEST"
            today = []

        calendar.append({
            "date": cur_date,
            "type": day_type,
            "plan": today
        })

        cur_date += timedelta(days=1)
        day_count += 1
        streak += 1 if day_type == "STUDY" else 0

    return calendar

if not st.session_state.calendar:
    st.session_state.calendar = generate_calendar(build_queue())

# ----------------------------------
# TABS
# ----------------------------------
tab1, tab2 = st.tabs(["📖 Study Plan", "📝 Question Practice"])

# ----------------------------------
# STUDY PLAN
# ----------------------------------
with tab1:
    st.header("📆 Weekly Study Plan")

    weeks = defaultdict(list)
    for i, day in enumerate(st.session_state.calendar):
        weeks[i // 7 + 1].append(day)

    for w in sorted(weeks):
        st.subheader(f"Week {w}")
        for d in weeks[w]:
            st.markdown(f"### {d['date'].strftime('%A, %d %b %Y')} ({d['type']})")

            unfinished = []
            for i, p in enumerate(d["plan"]):
                key = f"{d['date']}_{i}"
                label = f"{p['subject']} → {p['subtopic']} ({p['time']} min / {round(p['time']/60,2)} h)"
                if st.checkbox(label, key=key):
                    st.session_state.completed.add(key)
                else:
                    unfinished.append(p)

            if st.button(f"Mark Day Completed ({d['date']})", key=str(d['date'])):
                if unfinished:
                    st.warning("Unfinished topics moved to next day")
                    idx = st.session_state.calendar.index(d)
                    if idx + 1 < len(st.session_state.calendar):
                        st.session_state.calendar[idx+1]["plan"] = unfinished + st.session_state.calendar[idx+1]["plan"]

# ----------------------------------
# QUESTION PRACTICE
# ----------------------------------
with tab2:
    st.header("📝 Question Practice")

    day_labels = [d["date"].strftime("%d %b %Y") for d in st.session_state.calendar]
    selected_day = st.selectbox("Select Day", day_labels)

    idx = day_labels.index(selected_day)
    day = st.session_state.calendar[idx]

    q_count = st.number_input("Number of questions", 5, 100, 30)
    q_type = st.selectbox("Question Type", ["MCQs", "Subjective", "Long"])

    for p in day["plan"]:
        st.markdown(f"**{p['subject']} → {p['subtopic']}**")
        for i in range(q_count):
            st.checkbox(f"{q_type} Q{i+1}", key=f"{selected_day}_{p['subtopic']}_{i}")

# ----------------------------------
# SAVE STATE
# ----------------------------------
with open(STATE_FILE, "w") as f:
    json.dump(list(st.session_state.completed), f)
