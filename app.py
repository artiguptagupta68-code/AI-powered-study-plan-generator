# app.py
import streamlit as st
import os, zipfile, gdown, fitz, re
from collections import defaultdict
from datetime import datetime, timedelta
import random

st.set_page_config(page_title="Smart Study Planner", layout="wide")

# -----------------------------
# Configuration
# -----------------------------
DRIVE_FILE_ID = "1S6fcsuq9KvICTsOBOdp6_WN9FhzruixM"
ZIP_PATH = "plan.zip"
EXTRACT_DIR = "syllabus_data"

# Download & extract ZIP
if not os.path.exists(ZIP_PATH):
    with st.spinner("⬇️ Downloading syllabus ZIP..."):
        gdown.download(f"https://drive.google.com/uc?id={DRIVE_FILE_ID}", ZIP_PATH, quiet=False)

if not os.path.exists(EXTRACT_DIR):
    os.makedirs(EXTRACT_DIR, exist_ok=True)
    with zipfile.ZipFile(ZIP_PATH, "r") as zip_ref:
        zip_ref.extractall(EXTRACT_DIR)

# -----------------------------
# Read PDF and clean garbage
# -----------------------------
def is_garbage(line):
    l = line.lower()
    keywords = ["annexure","government of india","national medical commission",
                "medical education","ugmeb","neet (ug exam)","date:","sector",
                "dwarka","new delhi","pocket-","phase-","board)","exam)"]
    if any(k in l for k in keywords):
        return True
    if re.match(r"[a-z]-\d+/\d+", l):
        return True
    if re.search(r"\d{1,2}(st|nd|rd|th)?\s+[a-z]+\s+\d{4}", l):
        return True
    if len(line)>120:
        return True
    return False

def read_pdf_lines(path):
    doc = fitz.open(path)
    lines=[]
    for page in doc:
        for line in page.get_text().split("\n"):
            line=line.strip()
            if line and not is_garbage(line):
                lines.append(line)
    return lines

# -----------------------------
# Detect Exam & Stage/Branch
# -----------------------------
def detect_exam(path, lines):
    text=" ".join(lines).upper()
    filename=os.path.basename(path).upper()
    folder=os.path.basename(os.path.dirname(path)).upper()

    if "NEET" in text or "NEET" in filename or "NEET" in folder:
        return "NEET","UG"
    if "JEE" in text or "IIT" in text:
        if "ADVANCED" in text:
            return "IIT JEE","JEE Advanced"
        return "IIT JEE","JEE Main"
    if "GATE" in text or "GRADUATE APTITUDE TEST" in text:
        branch="General"
        for l in lines:
            if l.upper().strip() in ["ME","IN","CE"]:
                branch=l.upper().strip()
                break
        return "GATE",branch
    return None,None

# -----------------------------
# Parse syllabus
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

# -----------------------------
# Build syllabus
# -----------------------------
syllabus=parse_syllabus(EXTRACT_DIR)

if not syllabus:
    st.error("No syllabus found!")
    st.stop()

# -----------------------------
# Session state
# -----------------------------
if "queue" not in st.session_state: st.session_state.queue=[]
if "remaining" not in st.session_state: st.session_state.remaining=0
if "today" not in st.session_state: st.session_state.today=datetime.today()

# -----------------------------
# UI
# -----------------------------
st.title("📚 Smart Competitive Exam Study Planner 💡")

exam_list=list(syllabus.keys())
selected_exam=st.selectbox("Select Exam",exam_list)
stage_list=list(syllabus[selected_exam].keys())
selected_stage=st.selectbox("Select Stage / Branch",stage_list)
subjects=list(syllabus[selected_exam][selected_stage].keys())
selected_subject=st.selectbox("Select Subject",subjects)

capacity=st.number_input("Available study hours today",min_value=1.0,value=6.0,step=0.5)

# -----------------------------
# Build study queue with automatic subtopic timings
# -----------------------------
if st.button("Load Subtopics"):
    st.session_state.queue=[]
    st.session_state.remaining=capacity
    st.session_state.today=datetime.today()
    for topic, subs in syllabus[selected_exam][selected_stage][selected_subject].items():
        for sub in subs:
            # assign time based on subtopic length
            words=len(sub.split())
            time=max(0.25,min(1.5,0.25 + words/80))  # 0.25h short, 1.5h long
            st.session_state.queue.append({
                "topic":topic,
                "subtopic":sub,
                "time":round(time,2),
                "done":False
            })

# -----------------------------
# Display today's plan
# -----------------------------
if st.session_state.queue:
    st.subheader(f"📌 Study Plan for {selected_subject} ({selected_exam})")
    today=st.session_state.today
    st.write(f"📅 Date: {today.strftime('%Y-%m-%d')}")
    remaining=st.session_state.remaining

    for idx,item in enumerate(st.session_state.queue):
        if remaining<=0: break
        if not item["done"]:
            if item["time"]<=remaining:
                checked=st.checkbox(f"{item['topic']} → {item['subtopic']} ({item['time']}h)",key=item['subtopic']+str(idx))
                if checked: st.session_state.queue[idx]['done']=True
                remaining-=item["time"]
            else:
                st.checkbox(f"{item['topic']} → {item['subtopic']} ({item['time']}h, Not enough time today)",key="skip"+str(idx))
    
    st.session_state.remaining=remaining

    # Move to next day automatically
    if remaining<=0 or all([s["done"] for s in st.session_state.queue]):
        st.session_state.today+=timedelta(days=1)
        st.session_state.remaining=capacity
        st.info("⏩ Moving to next day!")

    # Progress bar
    done_count=sum(1 for s in st.session_state.queue if s["done"])
    total=len(st.session_state.queue)
    st.progress(done_count/total)
    st.caption(f"{done_count}/{total} subtopics completed ✅")
