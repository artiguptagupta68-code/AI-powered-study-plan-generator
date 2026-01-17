# app.py
import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import json, re, io, os
from collections import defaultdict, deque
from datetime import datetime, timedelta

# ---------------------------
# OPTIONAL OCR (SAFE)
# ---------------------------
try:
    import pytesseract
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False

# ---------------------------
# CONFIG
# ---------------------------
st.set_page_config(page_title="📚 AI Study Planner", layout="wide")
st.title("📚 AI Study Planner – Junior Engineer")

STATE_FILE = "progress.json"
MAX_CONTINUOUS_DAYS = 6

# ---------------------------
# SESSION STATE
# ---------------------------
if "completed" not in st.session_state:
    st.session_state.completed = set()
if "calendar" not in st.session_state:
    st.session_state.calendar = []
if "practice_done" not in st.session_state:
    st.session_state.practice_done = {}

if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r") as f:
        st.session_state.completed = set(json.load(f))

# ---------------------------
# PDF READER (TEXT + OPTIONAL OCR)
# ---------------------------
def read_pdf(file):
    doc = fitz.open(stream=file.read(), filetype="pdf")
    lines = []
    for page in doc:
        text = page.get_text()
        if text.strip():
            lines.extend([l.strip() for l in text.split("\n") if len(l.strip()) > 2])
        elif OCR_AVAILABLE:
            pix = page.get_pixmap()
            img = Image.open(io.BytesIO(pix.tobytes()))
            ocr_text = pytesseract.image_to_string(img)
            lines.extend([l.strip() for l in ocr_text.split("\n") if len(l.strip()) > 2])
    return lines

# ---------------------------
# PDF → SYLLABUS JSON
# ---------------------------
def pdf_to_syllabus_json(files):
    syllabus = defaultdict(lambda: defaultdict(list))
    current_subject, current_topic = None, None

    for f in files:
        for line in read_pdf(f):
            if line.isupper() and len(line.split()) <= 6:
                current_subject = line.title()
                current_topic = None
            elif line[0].isupper() and len(line.split()) <= 10:
                current_topic = line
            else:
                if current_subject and current_topic:
                    syllabus[current_subject][current_topic].append(line)
                elif current_subject:
                    syllabus[current_subject]["General"].append(line)
                else:
                    syllabus["General"]["General"].append(line)

    return dict(syllabus)

# ---------------------------
# TIME ESTIMATION
# ---------------------------
def estimate_time(text):
    words = len(text.split())
    complexity = len(re.findall(r"(numerical|derivation|theorem|proof)", text.lower()))
    return max(15, words * 3 + complexity * 10)

# ---------------------------
# BUILD QUEUE
# ---------------------------
def build_queue(syllabus_json, selected_subjects):
    q = deque()
    for subject in selected_subjects:
        for topic, subs in syllabus_json[subject].items():
            for sub in subs:
                q.append({
                    "subject": subject,
                    "topic": topic,
                    "subtopic": sub,
                    "time": estimate_time(sub)
                })
    return q

# ---------------------------
# DAILY ASSIGNMENT
# ---------------------------
def assign_daily_plan(queue, daily_min):
    plan = []
    while queue and daily_min > 0:
        item = queue[0]
        alloc = min(item["time"], daily_min)
        plan.append({**item, "minutes": alloc})
        item["time"] -= alloc
        daily_min -= alloc
        if item["time"] <= 0:
            queue.popleft()
    return plan

# ---------------------------
# CALENDAR GENERATION
# ---------------------------
def generate_calendar(queue, start_date, daily_hours, rev_n, test_n):
    calendar = []
    cur_date = datetime.combine(start_date, datetime.min.time())
    day_count, streak = 0, 0
    daily_min = int(daily_hours * 60)

    while queue:
        day_type = "STUDY"
        plan = assign_daily_plan(queue, daily_min)

        if streak >= MAX_CONTINUOUS_DAYS:
            day_type = "FREE"
            plan = [{"subject": "FREE", "topic": "Rest", "subtopic": "Relax", "minutes": 0}]
            streak = 0
        elif day_count and day_count % rev_n == 0:
            day_type = "REVISION"
            plan = [{"subject": "REVISION", "topic": "Revision", "subtopic": "Completed topics", "minutes": daily_min}]
        elif day_count and day_count % test_n == 0:
            day_type = "TEST"
            plan = [{"subject": "TEST", "topic": "Test", "subtopic": "Completed topics", "minutes": daily_min}]

        calendar.append({"date": cur_date, "plan": plan, "type": day_type})
        streak += 1 if day_type == "STUDY" else 0
        day_count += 1
        cur_date += timedelta(days=1)

    return calendar

# ---------------------------
# UPLOAD PDF
# ---------------------------
uploaded_files = st.file_uploader("📤 Upload syllabus PDF(s)", type=["pdf"], accept_multiple_files=True)
if not uploaded_files:
    st.stop()

# ---------------------------
# PARSE & CONFIRM JSON
# ---------------------------
syllabus_json = pdf_to_syllabus_json(uploaded_files)
st.subheader("📌 Extracted Syllabus (Editable)")
json_text = st.text_area("Edit if required", json.dumps(syllabus_json, indent=2), height=350)

try:
    syllabus_json = json.loads(json_text)
except:
    st.error("Invalid JSON")
    st.stop()

if not st.checkbox("✅ Confirm syllabus"):
    st.stop()

# ---------------------------
# SETTINGS
# ---------------------------
subjects = list(syllabus_json.keys())
selected_subjects = st.multiselect("Subjects", subjects, default=subjects)
start_date = st.date_input("Start date", datetime.today())
daily_hours = st.number_input("Daily hours", 1.0, 12.0, 6.0)
rev_n = st.number_input("Revision every N days", 5, 30, 7)
test_n = st.number_input("Test every N days", 7, 30, 14)

if st.button("🚀 Generate Plan"):
    queue = build_queue(syllabus_json, selected_subjects)
    st.session_state.calendar = generate_calendar(queue, start_date, daily_hours, rev_n, test_n)

# ---------------------------
# TABS
# ---------------------------
tab1, tab2 = st.tabs(["📖 Study Plan", "📝 Question Practice"])

# ---------------------------
# STUDY PLAN + CARRY FORWARD
# ---------------------------
with tab1:
    for i, day in enumerate(st.session_state.calendar):
        label = day["date"].strftime("%A, %d %b %Y")
        st.markdown(f"### {label} ({day['type']})")
        unfinished = []

        for j, p in enumerate(day["plan"]):
            if p["subject"] in ["FREE", "REVISION", "TEST"]:
                st.markdown(f"- **{p['subject']}** → {p['subtopic']}")
                continue

            key = f"{label}_{j}_{p['subtopic']}"
            checked = key in st.session_state.completed
            if st.checkbox(f"{p['subject']} → {p['topic']} → {p['subtopic']} ({p['minutes']} min)", value=checked, key=key):
                st.session_state.completed.add(key)
            else:
                unfinished.append(p)
                st.session_state.completed.discard(key)

        if st.button(f"Mark Day Completed ({label})", key=f"done_{i}"):
            if unfinished:
                if i + 1 >= len(st.session_state.calendar):
                    st.session_state.calendar.append({
                        "date": day["date"] + timedelta(days=1),
                        "plan": [],
                        "type": "STUDY"
                    })
                st.session_state.calendar[i + 1]["plan"] = unfinished + st.session_state.calendar[i + 1]["plan"]

# ---------------------------
# QUESTION PRACTICE
# ---------------------------
with tab2:
    days = [d["date"].strftime("%A, %d %b %Y") for d in st.session_state.calendar]
    if days:
        sel = st.selectbox("Select Day", days)
        idx = days.index(sel)
        day = st.session_state.calendar[idx]

        qn = st.number_input("Questions per subtopic", 5, 100, 20)
        qtype = st.selectbox("Question Type", ["MCQs", "Numerical", "Subjective"])

        for p in day["plan"]:
            if p["subject"] in ["FREE", "REVISION", "TEST"]:
                continue
            st.markdown(f"**{p['subject']} → {p['subtopic']}**")
            for k in range(qn):
                st.checkbox(f"{qtype} Q{k+1}", key=f"{sel}_{p['subtopic']}_{k}")

# ---------------------------
# SAVE STATE
# ---------------------------
with open(STATE_FILE, "w") as f:
    json.dump(list(st.session_state.completed), f)
