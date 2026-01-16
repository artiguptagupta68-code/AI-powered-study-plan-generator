# app.py
import streamlit as st
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import json
import re
from collections import defaultdict, deque
from datetime import datetime, timedelta
import io

# ---------------------------
# CONFIG
# ---------------------------
st.set_page_config(page_title="AI Study Planner", layout="wide")
st.title("📚 AI Study Planner (Junior Engineer Edition)")

STATE_FILE = "progress.json"
MAX_CONTINUOUS_DAYS = 6

# ---------------------------
# SESSION STATE
# ---------------------------
if "completed" not in st.session_state:
    st.session_state.completed = set()
if "calendar" not in st.session_state:
    st.session_state.calendar = []
if os.path.exists(STATE_FILE):
    with open(STATE_FILE,"r") as f:
        st.session_state.completed = set(json.load(f))

# ---------------------------
# PDF READER (TEXT + OCR)
# ---------------------------
def read_pdf(file):
    doc = fitz.open(stream=file.read(), filetype="pdf")
    lines = []
    for page in doc:
        text = page.get_text()
        if text.strip():
            page_lines = [l.strip() for l in text.split("\n") if len(l.strip())>2]
        else:
            pix = page.get_pixmap()
            img = Image.open(io.BytesIO(pix.tobytes()))
            ocr_text = pytesseract.image_to_string(img)
            page_lines = [l.strip() for l in ocr_text.split("\n") if len(l.strip())>2]
        lines.extend(page_lines)
    return lines

# ---------------------------
# PDF → SYLLABUS JSON
# ---------------------------
def pdf_to_syllabus_json(files):
    syllabus = defaultdict(lambda: defaultdict(list))
    current_subject = None
    current_topic = None

    for f in files:
        lines = read_pdf(f)
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Subject detection (ALL CAPS)
            if line.isupper() and len(line.split()) <= 6 and re.sub(r"[^A-Z]", "", line):
                current_subject = line.title()
                current_topic = None
            # Topic detection (Capitalized)
            elif line[0].isupper() and len(line.split()) <= 10:
                current_topic = line
            # Otherwise, subtopic
            else:
                if current_subject and current_topic:
                    syllabus[current_subject][current_topic].append(line)
                elif current_subject:
                    syllabus[current_subject]["General"].append(line)
                else:
                    syllabus["General"]["General"].append(line)
    return dict(syllabus)

# ---------------------------
# ESTIMATE TIME
# ---------------------------
def estimate_time(text):
    words = len(text.split())
    complexity = len(re.findall(r"(theorem|numerical|derivation|proof)", text.lower()))
    base = max(15, words*3 + complexity*10)
    return base

# ---------------------------
# BUILD QUEUE
# ---------------------------
def build_queue(syllabus_json, selected_subjects):
    q = deque()
    for subject in selected_subjects:
        for topic, subtopics in syllabus_json[subject].items():
            for subtopic in subtopics:
                q.append({
                    "subject": subject,
                    "topic": topic,
                    "subtopic": subtopic,
                    "time": estimate_time(subtopic)
                })
    return q

# ---------------------------
# ASSIGN DAILY PLAN
# ---------------------------
def assign_daily_plan(queue, daily_min):
    plan=[]
    subjects_today=list({item["subject"] for item in queue})
    if not subjects_today: return plan
    subject_queues={s:deque([item for item in queue if item["subject"]==s]) for s in subjects_today}
    while daily_min>0 and any(subject_queues.values()):
        for s in subjects_today:
            if not subject_queues[s]: continue
            item=subject_queues[s].popleft()
            alloc=min(item["time"], daily_min)
            plan.append({"subject":item["subject"], "topic":item["topic"], "subtopic":item["subtopic"], "minutes":alloc})
            daily_min -= alloc
            item["time"] -= alloc
            if item["time"] <= 0:
                for idx,q_item in enumerate(queue):
                    if q_item==item:
                        del queue[idx]
                        break
            if daily_min<=0:
                break
    return plan

# ---------------------------
# GENERATE CALENDAR
# ---------------------------
def generate_calendar(queue, start_date, daily_hours, revision_every_n_days=7, test_every_n_days=14):
    calendar=[]
    streak=0
    day_count=0
    cur_date=datetime.combine(start_date, datetime.min.time())
    daily_min=int(daily_hours*60)
    while queue:
        day_type="STUDY"
        plan=assign_daily_plan(queue, daily_min)
        if streak>=MAX_CONTINUOUS_DAYS:
            day_type="FREE"
            plan=[{"subject":"FREE","topic":"Rest","subtopic":"Relax / Light revision","minutes":0}]
            streak=0
        elif day_count%revision_every_n_days==0 and day_count!=0:
            day_type="REVISION"
            plan=[{"subject":"REVISION","topic":"Revise Completed","subtopic":"All completed topics", "minutes":daily_min}]
        elif day_count%test_every_n_days==0 and day_count!=0:
            day_type="TEST"
            plan=[{"subject":"TEST","topic":"Test Completed","subtopic":"All completed topics", "minutes":daily_min}]
        calendar.append({"date":cur_date,"plan":plan,"type":day_type})
        streak += 1 if day_type=="STUDY" else 0
        day_count += 1
        cur_date += timedelta(days=1)
    return calendar

# ---------------------------
# STEP 1: UPLOAD PDF
# ---------------------------
uploaded_files = st.file_uploader("📤 Upload syllabus PDF(s)", type=["pdf"], accept_multiple_files=True)
if not uploaded_files:
    st.info("Upload at least one PDF to continue.")
    st.stop()

# ---------------------------
# STEP 2: PDF → JSON
# ---------------------------
syllabus_json = pdf_to_syllabus_json(uploaded_files)
if not any(syllabus_json.values()):
    st.error("❌ No readable content found in PDFs.")
    st.stop()

st.subheader("📌 Extracted Syllabus (Editable JSON)")
json_text = st.text_area(
    "Edit subjects/topics/subtopics if needed",
    value=json.dumps(syllabus_json, indent=2, ensure_ascii=False),
    height=400
)
try:
    syllabus_json = json.loads(json_text)
except:
    st.error("Invalid JSON")
    st.stop()

confirm = st.checkbox("✅ Confirm syllabus")
if not confirm:
    st.warning("Confirm the syllabus to continue.")
    st.stop()

# ---------------------------
# STEP 3: STUDY PLAN SETTINGS
# ---------------------------
subjects = list(syllabus_json.keys())
selected_subjects = st.multiselect("Select subjects to study", subjects, default=subjects)
start_date = st.date_input("Start date", datetime.today())
daily_hours = st.number_input("Daily study hours", 1.0, 12.0, 6.0)
revision_every_n_days = st.number_input("Revision every N days", 5, 30, 7)
test_every_n_days = st.number_input("Test every N days", 7, 30, 14)

# ---------------------------
# STEP 4: GENERATE CALENDAR
# ---------------------------
if st.button("🚀 Generate Study Plan"):
    queue = build_queue(syllabus_json, selected_subjects)
    st.session_state.calendar = generate_calendar(queue, start_date, daily_hours, revision_every_n_days, test_every_n_days)
    st.success("✅ Study plan generated!")

# ---------------------------
# STEP 5: DISPLAY PLAN + DAY COMPLETED LOGIC
# ---------------------------
if st.session_state.calendar:
    st.subheader("📆 Weekly Study Plan")
    for day_idx, day in enumerate(st.session_state.calendar):
        day_label = day['date'].strftime("%A, %d %b %Y")
        st.markdown(f"### {day_label} ({day['type']} DAY)")
        unfinished_today = []
        for idx, p in enumerate(day["plan"]):
            subtopic = p.get("subtopic", p.get("topic", ""))
            key = f"{day_label}_{idx}_{subtopic}"
            checked = key in st.session_state.completed
            label = f"**{p['subject']} → {p.get('topic','')} → {subtopic}** ({p.get('minutes',0)} min)"
            if st.checkbox(label, key=key, value=checked):
                st.session_state.completed.add(key)
            else:
                st.session_state.completed.discard(key)
                if p.get("subject") not in ["REVISION","TEST","FREE"]:
                    unfinished_today.append(p)
        if st.button(f"Mark Day Completed ({day_label})", key=f"complete_day_{day_idx}"):
            if not unfinished_today:
                st.success("🎉 All subtopics completed for this day!")
            else:
                st.warning(f"{len(unfinished_today)} subtopics unfinished. Carrying forward to next day.")
                next_idx = day_idx + 1
                if next_idx >= len(st.session_state.calendar):
                    next_date = day["date"] + timedelta(days=1)
                    st.session_state.calendar.append({"date":next_date,"plan":[],"type":"STUDY"})
                st.session_state.calendar[next_idx]["plan"] = unfinished_today + st.session_state.calendar[next_idx]["plan"]

# ---------------------------
# STEP 6: SAVE PROGRESS
# ---------------------------
with open(STATE_FILE,"w") as f:
    json.dump(list(st.session_state.completed), f)
