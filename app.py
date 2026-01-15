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
FREE_DAY_BUFFER_MIN = 300  # 5 hours

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
# DOWNLOAD & EXTRACT
# -------------------------------
if not os.path.exists(ZIP_PATH):
    gdown.download(f"https://drive.google.com/uc?id={DRIVE_FILE_ID}", ZIP_PATH, quiet=True)

if not os.path.exists(EXTRACT_DIR):
    with zipfile.ZipFile(ZIP_PATH) as z:
        z.extractall(EXTRACT_DIR)

# -------------------------------
# PDF PARSING
# -------------------------------
def clean_line(line):
    bad = ["annexure", "notice", "commission"]
    return line.strip() and not any(b in line.lower() for b in bad) and len(line) < 120

def read_pdf(path):
    doc = fitz.open(path)
    lines = []
    for p in doc:
        for l in p.get_text().split("\n"):
            if clean_line(l):
                lines.append(l.strip())
    return lines

def detect_exam(lines):
    text = " ".join(lines).upper()
    if "NEET" in text: return "NEET"
    if "JEE" in text: return "IIT JEE"
    if "GATE" in text: return "GATE"
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
                    parts = [p.strip() for p in l.split(",") if len(p.strip()) > 3]
                    data[exam][subject].extend(parts)
    return data

syllabus = parse_syllabus(EXTRACT_DIR)
if not syllabus:
    st.error("❌ No syllabus data found.")
    st.stop()

# -------------------------------
# TIME ESTIMATION
# -------------------------------
def estimate_time_min(topic, exam):
    words = len(topic.split())
    complexity = len(re.findall(r"(theorem|numerical|derivation|proof)", topic.lower()))
    base = 15 + words * 3 + complexity * 10
    weight = {"NEET":1.1, "IIT JEE":1.3, "GATE":1.5}.get(exam,1)
    return int(base * weight)

# -------------------------------
# UI INPUTS
# -------------------------------
st.title("📅 AI Study Planner (Week-Based)")

exam = st.selectbox("Select Exam", list(syllabus.keys()), key="exam_select")
subjects = list(syllabus[exam].keys())
selected_subjects = st.multiselect("Select Subjects", subjects, key="subject_select")

start_date = st.date_input("Start Date", datetime.today(), key="start_date")
daily_hours = st.number_input("Daily study hours", 1.0, 12.0, 6.0, key="daily_hours")
questions_per_topic = st.number_input("Questions per topic per day", 10, 200, 30, key="questions_per_topic")

# -------------------------------
# BUILD QUEUE
# -------------------------------
def build_queue():
    q = deque()
    for s in selected_subjects:
        for t in syllabus[exam][s]:
            q.append({
                "subject": s,
                "topic": t,
                "time_min": estimate_time_min(t, exam)
            })
    return q

# -------------------------------
# GENERATE CALENDAR (DYNAMIC)
# -------------------------------
def generate_calendar(queue, start_date, daily_hours):
    calendar = []
    streak = 0
    cur_date = datetime.combine(start_date, datetime.min.time())

    while queue:
        daily_min = int(daily_hours * 60)
        plan = []

        while queue and daily_min > 0:
            item = queue.popleft()
            if item["time_min"] <= daily_min:
                plan.append(item)
                daily_min -= item["time_min"]
            else:
                plan.append({**item, "time_min": daily_min})
                item["time_min"] -= daily_min
                queue.appendleft(item)
                daily_min = 0

        if streak >= MAX_CONTINUOUS_DAYS:
            calendar.append({
                "date": cur_date,
                "plan": [{"subject":"FREE","topic":"Rest / light revision","time_min":0}],
                "questions":0
            })
            streak = 0
        else:
            calendar.append({
                "date": cur_date,
                "plan": plan,
                "questions": questions_per_topic
            })
            streak += 1

        cur_date += timedelta(days=1)

    return calendar

if selected_subjects and not st.session_state.calendar:
    queue = build_queue()
    st.session_state.calendar = generate_calendar(queue, start_date, daily_hours)

# -------------------------------
# TABS
# -------------------------------
tab1, tab2 = st.tabs([
    "📖 Study Plan",
    "📝 Question Practice"
])

# -------------------------------
# STUDY PLAN TAB
# -------------------------------
with tab1:
    st.header("📆 Weekly Study Plan")

    # Week grouping: sequential starting from Week 1
    weeks = defaultdict(list)
    for idx, day in enumerate(st.session_state.calendar):
        week_num = idx // 7 + 1
        weeks[week_num].append(day)

    for w_num in sorted(weeks.keys()):
        st.subheader(f"Week {w_num}")
        for day_idx, day in enumerate(weeks[w_num]):
            st.markdown(f"**{day['date'].strftime('%A, %d %b %Y')}**")
            unfinished_today = []

            for i, p in enumerate(day["plan"]):
                key = f"{day['date']}_{i}_{p['topic']}"
                checked = key in st.session_state.completed
                label = f"{p['subject']} → {p['topic']} ({p['time_min']} min / {round(p['time_min']/60,2)} h)"
                if st.checkbox(label, checked, key=f"study_{key}"):
                    st.session_state.completed.add(key)
                else:
                    st.session_state.completed.discard(key)
                    if p["subject"] != "FREE":
                        unfinished_today.append(p)

            # Immediate "Mark Day Completed" button
            if st.button(f"Mark Day Completed ({day['date'].strftime('%d %b %Y')})", key=f"complete_{day['date']}"):
                if not unfinished_today:
                    st.success("🎉 All subtopics completed for this day!")
                else:
                    st.warning(f"{len(unfinished_today)} subtopics unfinished. Moving to next day.")

                    # Ensure next day exists
                    if day_idx + 1 >= len(weeks[w_num]):
                        next_date = day["date"] + timedelta(days=1)
                        st.session_state.calendar.append({
                            "date": next_date,
                            "plan": [],
                            "questions": questions_per_topic
                        })

                    # Move unfinished topics to next day
                    st.session_state.calendar[day_idx + 1]["plan"] = unfinished_today + st.session_state.calendar[day_idx + 1]["plan"]

                    for u in unfinished_today:
                        st.write(f"• {u['subject']} → {u['topic']}")

# -------------------------------
# QUESTION PRACTICE TAB
# -------------------------------
with tab2:
    st.header("📝 Daily Question Practice")
    day_labels = [d["date"].strftime("%A, %d %b %Y") for d in st.session_state.calendar]
    sel = st.selectbox("Select Day", day_labels, key="practice_day_select")
    idx = day_labels.index(sel)
    day = st.session_state.calendar[idx]

    for i, p in enumerate(day["plan"]):
        if p["subject"] == "FREE":
            continue
        key = f"Q_{sel}_{i}"
        st.session_state.practice_done[key] = st.number_input(
            f"{p['subject']} → {p['topic']} ({day['questions']} questions)",
            0, day["questions"],
            st.session_state.practice_done.get(key,0),
            key=f"practice_{key}"
        )

# -------------------------------
# SAVE STATE
# -------------------------------
with open(STATE_FILE,"w") as f:
    json.dump(list(st.session_state.completed), f)
