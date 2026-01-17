# app.py
import streamlit as st
import fitz  # PyMuPDF
import json, re, os
from collections import defaultdict, deque
from datetime import datetime, timedelta
from PIL import Image
import io

# -------------------------------
# CONFIG
# -------------------------------
STATE_FILE = "progress.json"
MAX_CONTINUOUS_DAYS = 6
AVAILABLE_SYLLABUS = ["NEET", "IIT JEE", "GATE"]

st.set_page_config(page_title="AI Study Planner", layout="wide")
st.title("📚 AI Study Planner (Junior Engineer Edition)")

# -------------------------------
# SESSION STATE
# -------------------------------
if "completed" not in st.session_state:
    st.session_state.completed = set()
if "calendar" not in st.session_state:
    st.session_state.calendar = []
if os.path.exists(STATE_FILE):
    with open(STATE_FILE,"r") as f:
        st.session_state.completed = set(json.load(f))

# -------------------------------
# PDF READER
# -------------------------------
def read_pdf(file):
    doc = fitz.open(stream=file.read(), filetype="pdf")
    lines=[]
    for page in doc:
        text = page.get_text()
        if text.strip():
            page_lines = [l.strip() for l in text.split("\n") if l.strip()]
        else:
            # fallback to OCR if page empty
            pix = page.get_pixmap()
            img = Image.open(io.BytesIO(pix.tobytes()))
            try:
                import pytesseract
                ocr_text = pytesseract.image_to_string(img)
                page_lines = [l.strip() for l in ocr_text.split("\n") if l.strip()]
            except:
                page_lines=[]
        lines.extend(page_lines)
    return lines

# -------------------------------
# HIERARCHY PARSER
# -------------------------------
def parse_pdf_hierarchy(files):
    """Return: {Exam: {Subject: {Topic: [Subtopics]}}}"""
    data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for f in files:
        lines = read_pdf(f)
        exam_name = None
        for l in lines:
            l_clean = l.strip()
            if not l_clean:
                continue
            # Detect exam from available syllabus
            for ex in AVAILABLE_SYLLABUS:
                if ex.upper() in l_clean.upper():
                    exam_name = ex
                    break
        if not exam_name:
            exam_name = "CUSTOM"

        current_subject = None
        current_topic = None
        for l in lines:
            l_clean = l.strip()
            if not l_clean:
                continue
            # Subject: ALL CAPS
            if l_clean.isupper() and len(l_clean.split())<=6:
                current_subject = l_clean.title()
                current_topic = None
            # Topic: Capitalized, <= 10 words
            elif l_clean[0].isupper() and len(l_clean.split())<=10:
                current_topic = l_clean
            # Subtopic: everything else
            else:
                if current_subject and current_topic:
                    data[exam_name][current_subject][current_topic].append(l_clean)
                elif current_subject:
                    data[exam_name][current_subject]["General"].append(l_clean)
                else:
                    data[exam_name]["General"]["General"].append(l_clean)
    return data

# -------------------------------
# TIME ESTIMATION
# -------------------------------
def estimate_time(subtopic):
    words = len(subtopic.split())
    complexity = len(re.findall(r"(theorem|numerical|derivation|proof)", subtopic.lower()))
    return max(15, words*3 + complexity*10)  # in minutes

# -------------------------------
# QUEUE BUILDING
# -------------------------------
def build_queue(syllabus_json, selected_subjects):
    """Flatten subjects → topic → subtopic into a queue with time"""
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

# -------------------------------
# DAILY PLAN ALLOCATION
# -------------------------------
def assign_daily_plan(queue, daily_min):
    plan=[]
    subjects_today=list({item["subject"] for item in queue})
    if not subjects_today:
        return plan
    subject_queues={s:deque([item for item in queue if item["subject"]==s]) for s in subjects_today}

    while daily_min>0 and any(subject_queues.values()):
        for s in subjects_today:
            if not subject_queues[s]:
                continue
            item=subject_queues[s].popleft()
            alloc=min(item["time"], daily_min)
            plan.append({
                "subject": item["subject"],
                "topic": item["topic"],
                "subtopic": item["subtopic"],
                "minutes": alloc
            })
            daily_min -= alloc
            item["time"] -= alloc
            if item["time"] > 0:
                # unfinished, push back
                subject_queues[s].appendleft(item)
            else:
                # remove from main queue
                for idx,q_item in enumerate(queue):
                    if q_item==item:
                        del queue[idx]
                        break
            if daily_min<=0:
                break
    return plan

# -------------------------------
# CALENDAR GENERATION
# -------------------------------
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
            plan=[{"subject":"REVISION","topic":"Revise Completed","subtopic":"All completed topics","minutes":daily_min}]
        elif day_count%test_every_n_days==0 and day_count!=0:
            day_type="TEST"
            plan=[{"subject":"TEST","topic":"Test Completed","subtopic":"All completed topics","minutes":daily_min}]

        calendar.append({"date":cur_date,"plan":plan,"type":day_type})
        streak += 1 if day_type=="STUDY" else 0
        day_count +=1
        cur_date += timedelta(days=1)
    return calendar

# -------------------------------
# STEP 1: EXAM & SYLLABUS SELECTION
# -------------------------------
custom_plan = st.checkbox("Upload my own syllabus / custom PDFs")
if custom_plan:
    exam_name = st.text_input("Exam Name", key="custom_exam")
    uploaded_files = st.file_uploader(f"Upload syllabus PDF(s) for {exam_name}", type=["pdf"], accept_multiple_files=True)
    if not uploaded_files:
        st.warning("Upload at least one PDF to proceed")
        st.stop()
    syllabus_data = parse_pdf_hierarchy(uploaded_files)
    syllabus_json = syllabus_data[exam_name]
else:
    exam_name = st.selectbox("Select Exam", AVAILABLE_SYLLABUS)
    uploaded_files = st.file_uploader(f"Upload syllabus PDFs for {exam_name} (optional)", type=["pdf"], accept_multiple_files=True)
    if uploaded_files:
        syllabus_data = parse_pdf_hierarchy(uploaded_files)
        syllabus_json = syllabus_data.get(exam_name, {})
    else:
        # For demo, empty syllabus
        syllabus_json = {"Physics":{"Mechanics":["Kinematics","Dynamics"]},
                         "Chemistry":{"Organic":["Alkanes","Alkenes"]},
                         "Mathematics":{"Algebra":["Quadratic","Progressions"]}}

if not syllabus_json:
    st.error("No valid syllabus detected")
    st.stop()

# -------------------------------
# SUBJECT SELECTION
# -------------------------------
subjects = list(syllabus_json.keys())
selected_subjects = st.multiselect("Select Subjects", subjects, default=subjects)

# -------------------------------
# STUDY PLAN SETTINGS
# -------------------------------
start_date = st.date_input("Start Date", datetime.today())
daily_hours = st.number_input("Daily Study Hours", 1.0, 12.0, 6.0)
revision_every_n_days = st.number_input("Revision every N days", 5, 30, 7)
test_every_n_days = st.number_input("Test every N days", 7, 30, 14)

# -------------------------------
# GENERATE CALENDAR
# -------------------------------
if st.button("🚀 Generate Study Plan"):
    queue = build_queue(syllabus_json, selected_subjects)
    st.session_state.calendar = generate_calendar(queue, start_date, daily_hours, revision_every_n_days, test_every_n_days)
    st.success("✅ Study plan generated!")

# -------------------------------
# STUDY PLAN DISPLAY + DAY COMPLETED LOGIC
# -------------------------------
if st.session_state.calendar:
    st.subheader("📆 Weekly Study Plan")
    for day_idx, day in enumerate(st.session_state.calendar):
        day_label = day['date'].strftime("%A, %d %b %Y")
        st.markdown(f"### {day_label} ({day['type']} DAY)")
        unfinished_today=[]
        for idx, p in enumerate(day["plan"]):
            if p["subject"] in ["FREE","REVISION","TEST"]:
                st.markdown(f"- **{p['subject']} → {p['topic']} → {p['subtopic']}**")
                continue
            key = f"{day_label}_{idx}_{p['subtopic']}"
            checked = key in st.session_state.completed
            label = f"{p['subject']} → {p['topic']} → {p['subtopic']} ({p['minutes']} min)"
            if st.checkbox(label, key=key, value=checked):
                st.session_state.completed.add(key)
            else:
                st.session_state.completed.discard(key)
                unfinished_today.append(p)
        # Carry-forward logic
        if st.button(f"Mark Day Completed ({day_label})", key=f"complete_{day_idx}"):
            if not unfinished_today:
                st.success("🎉 All subtopics completed for this day!")
            else:
                st.warning(f"{len(unfinished_today)} subtopics unfinished. Carrying forward to next day.")
                next_idx = day_idx + 1
                if next_idx >= len(st.session_state.calendar):
                    next_date = day["date"] + timedelta(days=1)
                    st.session_state.calendar.append({"date": next_date,"plan":[],"type":"STUDY"})
                st.session_state.calendar[next_idx]["plan"] = unfinished_today + st.session_state.calendar[next_idx]["plan"]

# -------------------------------
# SAVE PROGRESS
# -------------------------------
with open(STATE_FILE,"w") as f:
    json.dump(list(st.session_state.completed), f)
