# app.py
import streamlit as st
import fitz  # PyMuPDF
import json
import re
from collections import defaultdict, deque
from datetime import datetime, timedelta

st.set_page_config(page_title="AI Study Planner", layout="wide")
st.title("📚 AI Study Planner (PDF → JSON → Plan)")

# --------------------------------------------------
# PDF READER
# --------------------------------------------------
def read_pdf(uploaded_file):
    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    lines = []
    for page in doc:
        for line in page.get_text().split("\n"):
            line = line.strip()
            if len(line) > 3:
                lines.append(line)
    return lines

# --------------------------------------------------
# PDF → SYLLABUS JSON
# --------------------------------------------------
def pdf_to_syllabus_json(files):
    syllabus = defaultdict(list)
    current_subject = "General"

    for f in files:
        lines = read_pdf(f)
        for line in lines:
            # Detect SUBJECT (ALL CAPS, short)
            if (
                line.isupper()
                and len(line.split()) <= 6
                and re.sub(r"[^A-Z]", "", line)
            ):
                current_subject = line.title()
            else:
                syllabus[current_subject].append(line)

    return dict(syllabus)

# --------------------------------------------------
# TIME ESTIMATION
# --------------------------------------------------
def estimate_time(topic):
    words = len(topic.split())
    return max(20, words * 3)

# --------------------------------------------------
# BUILD STUDY QUEUE
# --------------------------------------------------
def build_queue(syllabus_json, selected_subjects):
    q = deque()
    for subject in selected_subjects:
        for topic in syllabus_json[subject]:
            q.append({
                "subject": subject,
                "topic": topic,
                "time": estimate_time(topic)
            })
    return q

# --------------------------------------------------
# GENERATE STUDY CALENDAR
# --------------------------------------------------
def generate_calendar(queue, start_date, daily_hours):
    calendar = []
    cur_date = datetime.combine(start_date, datetime.min.time())
    daily_minutes = int(daily_hours * 60)

    while queue:
        remaining = daily_minutes
        day_plan = []

        while queue and remaining > 0:
            item = queue[0]
            alloc = min(item["time"], remaining)
            day_plan.append({
                "subject": item["subject"],
                "topic": item["topic"],
                "minutes": alloc
            })
            item["time"] -= alloc
            remaining -= alloc
            if item["time"] <= 0:
                queue.popleft()

        calendar.append({
            "date": cur_date,
            "plan": day_plan
        })
        cur_date += timedelta(days=1)

    return calendar

# --------------------------------------------------
# UI STEP 1: UPLOAD PDF
# --------------------------------------------------
uploaded_files = st.file_uploader(
    "📤 Upload syllabus PDF(s)",
    type=["pdf"],
    accept_multiple_files=True
)

if not uploaded_files:
    st.info("Upload syllabus PDF(s) to begin.")
    st.stop()

# --------------------------------------------------
# STEP 2: CONVERT TO JSON
# --------------------------------------------------
syllabus_json = pdf_to_syllabus_json(uploaded_files)

st.subheader("📌 Extracted Syllabus (Editable JSON)")
json_text = st.text_area(
    "Review / edit syllabus JSON",
    json.dumps(syllabus_json, indent=2, ensure_ascii=False),
    height=400
)

try:
    syllabus_json = json.loads(json_text)
except json.JSONDecodeError:
    st.error("❌ Invalid JSON. Fix it before proceeding.")
    st.stop()

# --------------------------------------------------
# STEP 3: CONFIRM
# --------------------------------------------------
confirm = st.checkbox("✅ I confirm this syllabus is correct")

if not confirm:
    st.warning("Please confirm the syllabus to continue.")
    st.stop()

st.success("Syllabus confirmed 🎉")

# --------------------------------------------------
# STEP 4: STUDY PLAN SETTINGS
# --------------------------------------------------
subjects = list(syllabus_json.keys())

selected_subjects = st.multiselect(
    "Select subjects to study",
    subjects,
    default=subjects
)

start_date = st.date_input("Start date", datetime.today())
daily_hours = st.number_input("Daily study hours", 1.0, 12.0, 6.0)

# --------------------------------------------------
# STEP 5: GENERATE PLAN
# --------------------------------------------------
if st.button("🚀 Generate Study Plan"):
    queue = build_queue(syllabus_json, selected_subjects)
    calendar = generate_calendar(queue, start_date, daily_hours)

    st.subheader("📆 Your Study Plan")

    for day in calendar:
        st.markdown(f"### {day['date'].strftime('%A, %d %b %Y')}")
        for p in day["plan"]:
            st.markdown(
                f"- **{p['subject']}** → {p['topic']} "
                f"({p['minutes']} min)"
            )

    st.success("✅ Study plan generated successfully!")

    st.download_button(
        "⬇️ Download Study Plan JSON",
        data=json.dumps(calendar, default=str, indent=2),
        file_name="study_plan.json",
        mime="application/json"
    )
