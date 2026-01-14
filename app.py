# app.py
import streamlit as st
import os, zipfile, gdown, fitz, re
from collections import defaultdict
from datetime import datetime, timedelta

st.set_page_config(page_title="Smart Study Planner", layout="wide")

# -----------------------------
# CONFIGURATION
# -----------------------------
DRIVE_FILE_ID = "1S6fcsuq9KvICTsOBOdp6_WN9FhzruixM"
ZIP_PATH = "plan.zip"
EXTRACT_DIR = "syllabus_data"

# -----------------------------
# DOWNLOAD & EXTRACT ZIP
# -----------------------------
if not os.path.exists(ZIP_PATH):
    gdown.download(f"https://drive.google.com/uc?id={DRIVE_FILE_ID}", ZIP_PATH, quiet=False)

if not os.path.exists(EXTRACT_DIR):
    os.makedirs(EXTRACT_DIR, exist_ok=True)
    with zipfile.ZipFile(ZIP_PATH, "r") as zip_ref:
        zip_ref.extractall(EXTRACT_DIR)

# -----------------------------
# PDF READING & CLEANING
# -----------------------------
def is_garbage(line):
    l=line.lower()
    garbage_keywords=[
        "annexure","government of india","national medical commission",
        "medical education","ugmeb","neet (ug exam)","date:","sector",
        "dwarka","new delhi","pocket-","phase-","board)","exam)"
    ]
    if any(k in l for k in garbage_keywords):
        return True
    if re.match(r"[a-z]-\d+/\d+", l):
        return True
    if re.search(r"\d{1,2}(st|nd|rd|th)?\s+[a-z]+\s+\d{4}", l):
        return True
    if len(line)>120:
        return True
    return False

def read_pdf_lines(path):
    doc=fitz.open(path)
    lines=[]
    for page in doc:
        for line in page.get_text().split("\n"):
            line=line.strip()
            if line and not is_garbage(line):
                lines.append(line)
    return lines

# -----------------------------
# DETECT EXAM
# -----------------------------
def detect_exam(path, lines):
    text=" ".join(lines).upper()
    filename=os.path.basename(path).upper()
    folder=os.path.basename(os.path.dirname(path)).upper()
    if "NEET" in text or "NEET" in filename or "NEET" in folder:
        return "NEET","UG"
    if "JEE" in text or "IIT" in text:
        return "IIT JEE","JEE Advanced" if "ADVANCED" in text else "JEE Main"
    if "GATE" in text or "GRADUATE APTITUDE TEST" in text:
        branch="General"
        for l in lines:
            if l.upper().strip() in ["ME","IN","CE"]:
                branch=l.upper().strip()
                break
        return "GATE",branch
    return None,None

# -----------------------------
# PARSE SYLLABUS
# -----------------------------
def parse_syllabus(root_dir):
    syllabus=defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))
    remove_subjects=["SECRETARY","PUBLIC NOTICE"]
    for root,_,files in os.walk(root_dir):
        for file in files:
            if not file.lower().endswith(".pdf"): continue
            path=os.path.join(root,file)
            lines=read_pdf_lines(path)
            exam,stage=detect_exam(path,lines)
            if not exam: continue
            current_subject=None
            current_topic=None
            for line in lines:
                if line.isupper() and line.replace(" ","").isalpha() and len(line.split())<=5:
                    if line.upper() in remove_subjects:
                        current_subject=None
                        current_topic=None
                        continue
                    current_subject=line.title()
                    current_topic=None
                    continue
                if (":" in line or line[:2].isdigit() or line.startswith("-")) and len(line.split())<=12:
                    current_topic=line.replace(":","").strip()
                    if current_subject:
                        syllabus[exam][stage][current_subject][current_topic]=[]
                    continue
                if current_subject and current_topic:
                    parts=[p.strip() for p in line.split(",") if len(p.strip())>3]
                    syllabus[exam][stage][current_subject][current_topic].extend(parts)
    return syllabus

syllabus=parse_syllabus(EXTRACT_DIR)

if not syllabus:
    st.error("No syllabus found!")
    st.stop()

# -----------------------------
# SESSION STATE
# -----------------------------
if "queue" not in st.session_state: st.session_state.queue=[]
if "today" not in st.session_state: st.session_state.today=datetime.today()
if "remaining" not in st.session_state: st.session_state.remaining=0

# -----------------------------
# UI
# -----------------------------
st.title("📚 Smart Competitive Study Planner")

# Select exam and subject(s)
exam_list=list(syllabus.keys())
selected_exam=st.selectbox("Select Exam",exam_list)
stage_list=list(syllabus[selected_exam].keys())
selected_stage=st.selectbox("Select Stage / Branch",stage_list)
subjects=list(syllabus[selected_exam][selected_stage].keys())
selected_subjects=st.multiselect("Select Subject(s)",subjects)

# Enter study capacity
capacity=st.number_input("Enter your study hours today",min_value=1.0,value=6.0,step=0.5)

# -----------------------------
# ASSIGN SUBTOPICS AUTOMATICALLY
# -----------------------------
if st.button("Assign Today's Subtopics"):
    st.session_state.queue=[]
    st.session_state.remaining=capacity
    for subject in selected_subjects:
        for topic,subs in syllabus[selected_exam][selected_stage][subject].items():
            for sub in subs:
                # Time estimate based on length
                time=max(0.25,min(1.5,0.25 + len(sub.split())/80))
                st.session_state.queue.append({
                    "subject":subject,
                    "topic":topic,
                    "subtopic":sub,
                    "time":round(time,2),
                    "done":False
                })

# -----------------------------
# DISPLAY TODAY'S PLAN
# -----------------------------
if st.session_state.queue:
    st.subheader(f"📌 Today's Study Plan ({len(selected_subjects)} subject(s))")
    remaining=st.session_state.remaining

    for idx,item in enumerate(st.session_state.queue):
        if remaining<=0: break
        if not item["done"]:
            if item["time"]<=remaining:
                checked=st.checkbox(f"{item['subtopic']} ({item['time']}h)",key=str(idx))
                if checked: st.session_state.queue[idx]["done"]=True
                remaining-=item["time"]
            else:
                st.checkbox(f"{item['subtopic']} ({item['time']}h ⏳ Not enough time today)",key="skip"+str(idx))

    st.session_state.remaining=remaining

    # Carryover: incomplete subtopics remain in queue for next day
    st.progress(sum(1 for s in st.session_state.queue if s["done"])/len(st.session_state.queue))
    st.caption(f"{sum(1 for s in st.session_state.queue if s['done'])}/{len(st.session_state.queue)} subtopics completed ✅")
    if remaining<=0 or all([s["done"] for s in st.session_state.queue]):
        st.session_state.today+=timedelta(days=1)
        st.session_state.remaining=capacity
        st.info(f"⏩ Moving to next day: {st.session_state.today.strftime('%Y-%m-%d')}")
