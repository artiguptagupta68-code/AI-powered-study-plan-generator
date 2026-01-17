# app.py
import streamlit as st
import os, zipfile, gdown, fitz, json, re, io
from collections import deque, defaultdict
from datetime import datetime, timedelta
from PIL import Image
import pytesseract

# -------------------------------
# CONFIG
# -------------------------------
AVAILABLE_SYLLABUS = ["NEET","IIT JEE","GATE"]
DRIVE_FILE_ID = "1S6fcsuq9KvICTsOBOdp6_WN9FhzruixM"
ZIP_PATH = "plan.zip"
EXTRACT_DIR = "syllabus_data"
STATE_FILE = "progress.json"
MAX_CONTINUOUS_DAYS = 6

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
    with open(STATE_FILE,"r") as f:
        st.session_state.completed = set(json.load(f))

# -------------------------------
# PDF READER
# -------------------------------
def read_pdf(file):
    try:
        doc = fitz.open(file.name if isinstance(file, io.IOBase) else file)
    except:
        doc = fitz.open(stream=file.read(), filetype="pdf")
    lines=[]
    for page in doc:
        text = page.get_text()
        if text.strip():
            page_lines = [l.strip() for l in text.split("\n") if len(l.strip())>2]
        else:
            # OCR fallback
            pix = page.get_pixmap()
            img = Image.open(io.BytesIO(pix.tobytes()))
            ocr_text = pytesseract.image_to_string(img)
            page_lines = [l.strip() for l in ocr_text.split("\n") if len(l.strip())>2]
        lines.extend(page_lines)
    return lines

# -------------------------------
# PARSE PDF TO HIERARCHY
# -------------------------------
def parse_pdf_hierarchy(files, forced_exam=None):
    data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for f in files:
        lines = read_pdf(f)
        exam_name = forced_exam
        if not exam_name:
            text_upper = " ".join(lines).upper()
            for ex in AVAILABLE_SYLLABUS:
                if ex in text_upper:
                    exam_name = ex
                    break
        if not exam_name:
            # fallback filename check
            fname = os.path.basename(f.name).upper()
            for ex in AVAILABLE_SYLLABUS:
                if ex in fname:
                    exam_name = ex
                    break
        if not exam_name:
            continue  # skip PDF if exam can't be detected

        current_subject = None
        current_topic = None
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.isupper() and len(line.split()) <= 6:
                current_subject = line.title()
                current_topic = None
            elif line[0].isupper() and len(line.split()) <= 10:
                current_topic = line
            else:
                if current_subject and current_topic:
                    data[exam_name][current_subject][current_topic].append(line)
                elif current_subject:
                    data[exam_name][current_subject]["General"].append(line)
                else:
                    data[exam_name]["General"]["General"].append(line)
    return dict(data)

# -------------------------------
# ESTIMATE TIME
# -------------------------------
def estimate_time(subtopic):
    words = len(subtopic.split())
    complexity = len(re.findall(r"(theorem|numerical|derivation|proof)", subtopic.lower()))
    return max(15, words*3 + complexity*10)

# -------------------------------
# BUILD QUEUE
# -------------------------------
def build_queue(syllabus_json, selected_subjects):
    q = deque()
    for subj in selected_subjects:
        for topic, subtopics in syllabus_json[subj].items():
            for subtopic in subtopics:
                q.append({"subject":subj,"topic":topic,"subtopic":subtopic,"time_min":estimate_time(subtopic)})
    return q

# -------------------------------
# ASSIGN DAILY PLAN
# -------------------------------
def assign_daily_plan(queue, daily_min):
    plan=[]
    subjects_today=list({item["subject"] for item in queue})
    if not subjects_today: return plan
    subject_queues={s:deque([item for item in queue if item["subject"]==s]) for s in subjects_today}
    while daily_min>0 and any(subject_queues.values()):
        for s in subjects_today:
            if not subject_queues[s]: continue
            item=subject_queues[s].popleft()
            alloc=min(item["time_min"],daily_min)
            plan.append({"subject":item["subject"],"topic":item["topic"],"subtopic":item["subtopic"],"time_min":alloc})
            daily_min-=alloc
            item["time_min"]-=alloc
            if item["time_min"]<=0:
                for idx,q_item in enumerate(queue):
                    if q_item==item:
                        del queue[idx]
                        break
            if daily_min<=0: break
    return plan

# -------------------------------
# GENERATE CALENDAR
# -------------------------------
def generate_calendar(queue,start_date,daily_hours,revision_every_n_days=7,test_every_n_days=14):
    calendar=[]
    streak=0
    day_count=0
    cur_date=datetime.combine(start_date, datetime.min.time())
    daily_min=int(daily_hours*60)
    while queue:
        day_type="STUDY"
        plan=assign_daily_plan(queue,daily_min)
        if streak>=MAX_CONTINUOUS_DAYS:
            day_type="FREE"
            plan=[{"subject":"FREE","topic":"Rest","subtopic":"Relax / Light revision","time_min":0}]
            streak=0
        elif day_count%revision_every_n_days==0 and day_count!=0:
            day_type="REVISION"
            plan=[{"subject":"REVISION","topic":"Revise Completed","subtopic":"All completed topics","time_min":daily_min}]
        elif day_count%test_every_n_days==0 and day_count!=0:
            day_type="TEST"
            plan=[{"subject":"TEST","topic":"Test Completed","subtopic":"All completed topics","time_min":daily_min}]
        calendar.append({"date":cur_date,"plan":plan,"type":day_type})
        streak += 1 if day_type=="STUDY" else 0
        day_count += 1
        cur_date += timedelta(days=1)
    return calendar

# -------------------------------
# USER INPUT: EXAM & SYLLABUS
# -------------------------------
st.title("📚 AI Study Planner")

custom_plan = st.checkbox("Create study plan from uploaded PDFs (custom syllabus)")

if custom_plan:
    exam_name = st.text_input("Enter exam name for uploaded syllabus")
    uploaded_files = st.file_uploader("Upload syllabus PDFs", type=["pdf"], accept_multiple_files=True)
    if not uploaded_files:
        st.warning("Upload at least one PDF")
        st.stop()
    syllabus_dict = parse_pdf_hierarchy(uploaded_files, forced_exam=exam_name)
    if not syllabus_dict or exam_name not in syllabus_dict:
        st.error("No valid syllabus detected in uploaded PDFs")
        st.stop()
    syllabus_json = syllabus_dict[exam_name]
else:
    exam_name = st.selectbox("Select Exam", AVAILABLE_SYLLABUS)
    syllabus_source = st.radio("Syllabus Source", ["Use default syllabus","Upload PDFs for selected exam"])
    syllabus_root = EXTRACT_DIR
    if syllabus_source=="Use default syllabus":
        if not os.path.exists(syllabus_root):
            if not os.path.exists(ZIP_PATH):
                gdown.download(f"https://drive.google.com/uc?id={DRIVE_FILE_ID}", ZIP_PATH, quiet=True)
            with zipfile.ZipFile(ZIP_PATH) as z:
                z.extractall(EXTRACT_DIR)
        all_files = [os.path.join(syllabus_root,f) for f in os.listdir(syllabus_root) if f.lower().endswith(".pdf")]
        syllabus_dict = parse_pdf_hierarchy(all_files, forced_exam=exam_name)
        if not syllabus_dict or exam_name not in syllabus_dict:
            st.error(f"No syllabus found for {exam_name}")
            st.stop()
        syllabus_json = syllabus_dict[exam_name]
    else:
        uploaded_files = st.file_uploader(f"Upload syllabus PDFs for {exam_name}", type=["pdf"], accept_multiple_files=True)
        if uploaded_files:
            syllabus_dict = parse_pdf_hierarchy(uploaded_files, forced_exam=exam_name)
            if not syllabus_dict or exam_name not in syllabus_dict:
                st.error(f"No valid syllabus detected in uploaded PDFs for {exam_name}")
                st.stop()
            syllabus_json = syllabus_dict[exam_name]

subjects = list(syllabus_json.keys())
selected_subjects = st.multiselect("Select subjects", subjects, default=subjects)

start_date = st.date_input("Start Date", datetime.today())
daily_hours = st.number_input("Daily study hours",1.0,12.0,6.0)
revision_every_n_days = st.number_input("Revision every N days",5,30,7)
test_every_n_days = st.number_input("Test every N days",7,30,14)

# -------------------------------
# GENERATE CALENDAR
# -------------------------------
if st.button("🚀 Generate Study Plan"):
    queue = build_queue(syllabus_json, selected_subjects)
    st.session_state.calendar = generate_calendar(queue,start_date,daily_hours,revision_every_n_days,test_every_n_days)
    st.success("Study plan generated!")

# -------------------------------
# DISPLAY PLAN + MARK DAY COMPLETED
# -------------------------------
if st.session_state.calendar:
    st.subheader("📆 Weekly Study Plan")
    for day_idx, day in enumerate(st.session_state.calendar):
        day_label = day["date"].strftime("%A, %d %b %Y")
        st.markdown(f"### {day_label} ({day['type']} DAY)")
        unfinished_today=[]
        for idx, p in enumerate(day["plan"]):
            if p["subject"] in ["FREE","REVISION","TEST"]:
                st.markdown(f"- **{p['subject']} → {p['topic']} → {p['subtopic']}**")
                continue
            key = f"{day_label}_{idx}_{p['subtopic']}"
            checked = key in st.session_state.completed
            label = f"{p['subject']} → {p['topic']} → {p['subtopic']} ({p['time_min']} min)"
            if st.checkbox(label, key=key, value=checked):
                st.session_state.completed.add(key)
            else:
                st.session_state.completed.discard(key)
                unfinished_today.append(p)
        if st.button(f"Mark Day Completed ({day_label})", key=f"complete_{day_idx}"):
            if not unfinished_today:
                st.success("🎉 All subtopics completed!")
            else:
                st.warning(f"{len(unfinished_today)} subtopics unfinished. Carrying forward to next day.")
                next_idx = day_idx + 1
                if next_idx >= len(st.session_state.calendar):
                    next_date = day["date"] + timedelta(days=1)
                    st.session_state.calendar.append({"date":next_date,"plan":[],"type":"STUDY"})
                st.session_state.calendar[next_idx]["plan"] = unfinished_today + st.session_state.calendar[next_idx]["plan"]

# -------------------------------
# SAVE STATE
# -------------------------------
with open(STATE_FILE,"w") as f:
    json.dump(list(st.session_state.completed), f)
