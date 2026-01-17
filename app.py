# app.py
import streamlit as st
import fitz  # PyMuPDF
import json, re, os
from collections import defaultdict, deque
from datetime import datetime, timedelta
from PIL import Image
import io

# ---------------------------
# CONFIG
# ---------------------------
STATE_FILE = "progress.json"
MAX_CONTINUOUS_DAYS = 6

st.set_page_config(page_title="AI Study Planner", layout="wide")
st.title("📚 AI Study Planner ")

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
    with open(STATE_FILE,"r") as f:
        st.session_state.completed = set(json.load(f))

# ---------------------------
# PDF READER
# ---------------------------
def read_pdf(file):
    """Read PDF text using PyMuPDF, fallback to OCR"""
    doc = fitz.open(stream=file.read(), filetype="pdf")
    lines = []
    for page in doc:
        text = page.get_text().strip()
        if text:
            page_lines = [l.strip() for l in text.split("\n") if len(l.strip())>2]
        else:
            pix = page.get_pixmap()
            img = Image.open(io.BytesIO(pix.tobytes()))
            import pytesseract
            ocr_text = pytesseract.image_to_string(img)
            page_lines = [l.strip() for l in ocr_text.split("\n") if len(l.strip())>2]
        lines.extend(page_lines)
    return lines

# ---------------------------
# HIERARCHY PARSER
# ---------------------------
def parse_syllabus_hierarchy(files):
    """
    Robust hierarchy detection:
    Subject (all caps or contains keywords) → Topic → Subtopic
    Returns nested dict: subject -> topic -> list[subtopics]
    """
    syllabus = defaultdict(lambda: defaultdict(list))

    for f in files:
        temp_path = f"__temp_{f.name}"
        with open(temp_path, "wb") as out:
            out.write(f.read())
        lines = read_pdf(open(temp_path,"rb"))
        os.remove(temp_path)

        subject = None
        topic = None

        for l in lines:
            l = l.strip()
            if len(l) < 2:
                continue

            # SUBJECT detection: all caps OR known keywords
            if (l.isupper() and len(l.split()) <= 6 and re.search(r"[A-Z]", l)) \
                or re.search(r"(CIVIL|MECHANICAL|ELECTRICAL|BIOLOGY|PHYSICS|CHEMISTRY|MATHEMATICS)", l, re.I):
                subject = l.title()
                topic = None
                continue

            # TOPIC detection: title case or numbered
            if re.match(r"^(\d+(\.\d+)?|[A-Z]\.|[IVX]+)\s+", l) or l.istitle():
                topic = l
                continue

            # Otherwise subtopic
            if subject:
                if topic:
                    syllabus[subject][topic].append(l)
                else:
                    syllabus[subject]["General"].append(l)
            else:
                syllabus["General"]["General"].append(l)

    if not syllabus:
        syllabus["General"]["General"] = ["Uploaded syllabus content"]

    return dict(syllabus)

# ---------------------------
# ESTIMATE TIME
# ---------------------------
def estimate_time(text):
    words = len(text.split())
    complexity = len(re.findall(r"(theorem|numerical|derivation|proof)", text.lower()))
    return max(15, words*3 + complexity*10)

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
            plan.append({
                "subject": item["subject"],
                "topic": item["topic"],
                "subtopic": item["subtopic"],
                "minutes": alloc
            })
            daily_min -= alloc
            item["time"] -= alloc
            if item["time"] <= 0:
                for idx,q_item in enumerate(queue):
                    if q_item==item:
                        del queue[idx]
                        break
            if daily_min <= 0:
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
        plan = assign_daily_plan(queue, daily_min)

        if streak >= MAX_CONTINUOUS_DAYS:
            day_type="FREE"
            plan=[{"subject":"FREE","topic":"Rest","subtopic":"Relax / Light revision","minutes":0}]
            streak = 0
        elif day_count % revision_every_n_days == 0 and day_count != 0:
            day_type="REVISION"
            plan=[{"subject":"REVISION","topic":"Revise Completed","subtopic":"All completed topics","minutes":daily_min}]
        elif day_count % test_every_n_days == 0 and day_count != 0:
            day_type="TEST"
            plan=[{"subject":"TEST","topic":"Test Completed","subtopic":"All completed topics","minutes":daily_min}]

        calendar.append({"date": cur_date, "plan": plan, "type": day_type})
        streak += 1 if day_type=="STUDY" else 0
        day_count += 1
        cur_date += timedelta(days=1)
    return calendar

# ---------------------------
# STEP 1: CHOOSE SYLLABUS
# ---------------------------
st.subheader("📌 Syllabus Selection")

option = st.radio("Select syllabus type", ["Available Syllabus", "Upload Syllabus (PDF)"])

syllabus_json = {}
if option == "Available Syllabus":
    exam = st.selectbox("Select Exam", ["NEET","GATE","IIT JEE"])
    # Full default syllabus for multiple subjects per exam
    default_syllabus = {
        "NEET": {
            "Biology": {"Genetics":["Mendelian laws","DNA structure"], "Anatomy":["Heart","Lungs"]},
            "Chemistry": {"Organic":["Alkanes","Alkenes"], "Inorganic":["Periodic Table","Chemical Bonding"]},
            "Physics": {"Mechanics":["Newton's laws","Work-Energy"], "Optics":["Reflection","Refraction"]}
        },
        "GATE": {
            "Mechanical": {"Thermodynamics":["Laws","Cycles"], "Fluid Mechanics":["Bernoulli","Viscosity"]},
            "Electrical": {"Circuits":["AC","DC"], "Electromagnetics":["Maxwell's Equations","EM Waves"]}
        },
        "IIT JEE": {
            "Physics": {"Mechanics":["Newton's laws","Work-Energy"], "Electrostatics":["Coulomb's Law","Capacitance"]},
            "Chemistry": {"Organic":["Alkanes","Alkenes"], "Physical":["Thermodynamics","Equilibrium"]},
            "Mathematics": {"Calculus":["Limits","Differentiation"], "Algebra":["Matrices","Determinants"]}
        }
    }
    syllabus_json = default_syllabus.get(exam, {})
elif option == "Upload Syllabus (PDF)":
    uploaded_files = st.file_uploader("Upload syllabus PDFs", type=["pdf"], accept_multiple_files=True)
    if uploaded_files:
        syllabus_json = parse_syllabus_hierarchy(uploaded_files)
    if not syllabus_json:
        st.error("No valid syllabus detected.")
        st.stop()

# ---------------------------
# STEP 2: SUBJECT SELECTION
# ---------------------------
subjects = list(syllabus_json.keys())
selected_subjects = st.multiselect("Select Subjects to study", subjects, default=subjects)
start_date = st.date_input("Start Date", datetime.today())
daily_hours = st.number_input("Daily study hours",1.0,12.0,6.0)
revision_every_n_days = st.number_input("Revision every N days",5,30,7)
test_every_n_days = st.number_input("Test every N days",7,30,14)

# ---------------------------
# STEP 3: GENERATE PLAN
# ---------------------------
if st.button("🚀 Generate Study Plan"):
    queue = build_queue(syllabus_json, selected_subjects)
    st.session_state.calendar = generate_calendar(queue, start_date, daily_hours, revision_every_n_days, test_every_n_days)
    st.success("✅ Study plan generated!")

# ---------------------------
# STEP 4: DISPLAY PLAN
# ---------------------------
if st.session_state.calendar:
    st.subheader("📆 Weekly Study Plan")
    for day_idx, day in enumerate(st.session_state.calendar):
        day_label = day['date'].strftime("%A, %d %b %Y")
        st.markdown(f"### {day_label} ({day['type']} DAY)")
        unfinished_today = []

        for idx, p in enumerate(day["plan"]):
            if p["subject"] in ["FREE","REVISION","TEST"]:
                st.markdown(f"- **{p['subject']} → {p['topic']} → {p['subtopic']}**")
                continue

            key = f"{day_label}_{idx}_{p['subtopic']}"
            checked = key in st.session_state.completed
            label = f"**{p['subject']} → {p['topic']} → {p['subtopic']}** ({p['minutes']} min)"
            if st.checkbox(label, key=key, value=checked):
                st.session_state.completed.add(key)
            else:
                st.session_state.completed.discard(key)
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
# SAVE STATE
# ---------------------------
with open(STATE_FILE,"w") as f:
    json.dump(list(st.session_state.completed),f)
