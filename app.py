# app.py
import streamlit as st
import fitz  # PyMuPDF
import json
import re
import os
from collections import defaultdict, deque
from datetime import datetime, timedelta
import io

# ---------------------------------
# CONFIG
# ---------------------------------
st.set_page_config(page_title="AI Study Planner", layout="wide")
st.title("📚 AI Study Planner – Junior Engineer")

STATE_FILE = "progress.json"
MAX_CONTINUOUS_DAYS = 6

# ---------------------------------
# SESSION STATE
# ---------------------------------
if "completed" not in st.session_state:
    st.session_state.completed = set()
if "calendar" not in st.session_state:
    st.session_state.calendar = []

if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r") as f:
        st.session_state.completed = set(json.load(f))

# ---------------------------------
# SAFE PDF READER (NO OCR CRASH)
# ---------------------------------
def read_pdf(uploaded_file):
    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    lines = []
    for page in doc:
        text = page.get_text()
        if text.strip():
            lines.extend(
                [l.strip() for l in text.split("\n") if len(l.strip()) > 2]
            )
    return lines

# ---------------------------------
# PDF → SYLLABUS JSON
# ---------------------------------
def pdf_to_syllabus_json(files):
    syllabus = defaultdict(lambda: defaultdict(list))
    current_subject = None
    current_topic = None

    for f in files:
        lines = read_pdf(f)
        for line in lines:
            if line.isupper() and len(line.split()) <= 6:
                current_subject = line.title()
                current_topic = None
            elif line[:1].isupper() and len(line.split()) <= 10:
                current_topic = line
            else:
                if current_subject and current_topic:
                    syllabus[current_subject][current_topic].append(line)

    return dict(syllabus)

# ---------------------------------
# DEFAULT AVAILABLE SYLLABUS
# ---------------------------------
def load_available_syllabus():
    return {
        "Civil Engineering": {
            "Strength of Materials": [
                "Stress and strain",
                "Elastic constants",
                "Bending of beams"
            ],
            "Surveying": [
                "Chain surveying",
                "Compass surveying",
                "Levelling"
            ]
        },
        "Mechanical Engineering": {
            "Thermodynamics": [
                "Laws of thermodynamics",
                "Heat engines",
                "Entropy"
            ]
        }
    }

# ---------------------------------
# TIME ESTIMATION
# ---------------------------------
def estimate_time(text):
    words = len(text.split())
    return max(20, words * 3)

# ---------------------------------
# BUILD QUEUE
# ---------------------------------
def build_queue(syllabus_json, selected_subjects):
    q = deque()
    for subject in selected_subjects:
        for topic, subtopics in syllabus_json[subject].items():
            for sub in subtopics:
                q.append({
                    "subject": subject,
                    "topic": topic,
                    "subtopic": sub,
                    "time": estimate_time(sub)
                })
    return q

# ---------------------------------
# DAILY ASSIGNMENT
# ---------------------------------
def assign_daily_plan(queue, daily_min):
    plan = []
    while daily_min > 0 and queue:
        item = queue[0]
        alloc = min(item["time"], daily_min)

        plan.append({
            "subject": item["subject"],
            "topic": item["topic"],
            "subtopic": item["subtopic"],
            "minutes": alloc
        })

        item["time"] -= alloc
        daily_min -= alloc

        if item["time"] <= 0:
            queue.popleft()

    return plan

# ---------------------------------
# GENERATE CALENDAR
# ---------------------------------
def generate_calendar(queue, start_date, daily_hours):
    calendar = []
    cur_date = start_date
    streak = 0

    while queue:
        daily_min = int(daily_hours * 60)
        day_type = "STUDY"
        plan = assign_daily_plan(queue, daily_min)

        if streak >= MAX_CONTINUOUS_DAYS:
            day_type = "FREE"
            plan = []
            streak = 0

        calendar.append({
            "date": cur_date,
            "plan": plan,
            "type": day_type
        })

        streak += 1 if day_type == "STUDY" else 0
        cur_date += timedelta(days=1)

    return calendar

# ---------------------------------
# STEP 1: CHOOSE SYLLABUS SOURCE
# ---------------------------------
choice = st.radio(
    "Choose syllabus source",
    ["Available syllabus", "Upload syllabus (PDF)"]
)

if choice == "Available syllabus":
    syllabus_json = load_available_syllabus()

else:
    uploaded_files = st.file_uploader(
        "Upload syllabus PDF(s)",
        type=["pdf"],
        accept_multiple_files=True
    )
    if not uploaded_files:
        st.stop()

    syllabus_json = pdf_to_syllabus_json(uploaded_files)
    if not syllabus_json:
        st.error("No valid syllabus found in PDF")
        st.stop()

# ---------------------------------
# STEP 2: CONFIRM SYLLABUS
# ---------------------------------
st.subheader("📌 Syllabus (Editable)")
json_text = st.text_area(
    "Confirm or edit syllabus JSON",
    json.dumps(syllabus_json, indent=2),
    height=350
)

try:
    syllabus_json = json.loads(json_text)
except:
    st.error("Invalid JSON")
    st.stop()

if not st.checkbox("✅ Confirm syllabus"):
    st.stop()

# ---------------------------------
# STEP 3: SETTINGS
# ---------------------------------
subjects = list(syllabus_json.keys())
selected_subjects = st.multiselect(
    "Select subjects",
    subjects,
    default=subjects
)

start_date = st.date_input("Start date", datetime.today())
daily_hours = st.number_input("Daily study hours", 1.0, 12.0, 6.0)

# ---------------------------------
# STEP 4: GENERATE PLAN
# ---------------------------------
if st.button("🚀 Generate Study Plan"):
    queue = build_queue(syllabus_json, selected_subjects)
    st.session_state.calendar = generate_calendar(
        queue, start_date, daily_hours
    )
    st.success("Study plan generated")

# ---------------------------------
# STEP 5: DISPLAY + CARRY FORWARD
# ---------------------------------
for d_idx, day in enumerate(st.session_state.calendar):
    st.markdown(
        f"### {day['date'].strftime('%A, %d %b %Y')} ({day['type']})"
    )

    unfinished = []

    for p_idx, p in enumerate(day["plan"]):
        key = f"{d_idx}_{p_idx}"
        checked = key in st.session_state.completed

        label = f"{p['subject']} → {p['topic']} → {p['subtopic']} ({p['minutes']} min)"

        if st.checkbox(label, key=key, value=checked):
            st.session_state.completed.add(key)
        else:
            unfinished.append(p)

    if st.button("Mark Day Completed", key=f"done_{d_idx}"):
        if unfinished:
            if d_idx + 1 < len(st.session_state.calendar):
                st.session_state.calendar[d_idx + 1]["plan"] = (
                    unfinished + st.session_state.calendar[d_idx + 1]["plan"]
                )
            st.warning("Unfinished topics carried forward")
        else:
            st.success("Day completed 🎉")

# ---------------------------------
# SAVE STATE
# ---------------------------------
with open(STATE_FILE, "w") as f:
    json.dump(list(st.session_state.completed), f)
