# app.py
import streamlit as st
import os
import zipfile
import gdown
import fitz
import re
from collections import defaultdict, deque
from datetime import datetime, timedelta
import pandas as pd

# -----------------------------
# CONFIGURATION
# -----------------------------
DRIVE_FILE_ID = "1S6fcsuq9KvICTsOBOdp6_WN9FhzruixM"
ZIP_PATH = "plan.zip"
EXTRACT_DIR = "syllabus_data"

st.set_page_config(page_title="📚 Study Planner Calendar", layout="wide")

# -----------------------------
# DOWNLOAD & EXTRACT ZIP
# -----------------------------
if not os.path.exists(ZIP_PATH):
    with st.spinner("⬇️ Downloading syllabus ZIP..."):
        gdown.download(f"https://drive.google.com/uc?id={DRIVE_FILE_ID}", ZIP_PATH, quiet=False)

if not os.path.exists(EXTRACT_DIR):
    os.makedirs(EXTRACT_DIR, exist_ok=True)
    with zipfile.ZipFile(ZIP_PATH, "r") as zip_ref:
        zip_ref.extractall(EXTRACT_DIR)

# -----------------------------
# CLEAN PDF LINES
# -----------------------------
def is_garbage_line(line):
    l = line.lower()
    garbage_keywords = ["annexure", "government of india", "national medical commission",
                        "medical education", "ugmeb", "neet (ug exam)", "date:", "sector",
                        "dwarka", "new delhi", "pocket-", "phase-", "board)", "exam)"]
    if any(k in l for k in garbage_keywords): return True
    if re.match(r"[a-z]-\d+/\d+", l): return True
    if re.search(r"\d{1,2}(st|nd|rd|th)?\s+[a-z]+\s+\d{4}", l): return True
    if len(line) > 120: return True
    return False

def read_pdf_lines(pdf_path):
    doc = fitz.open(pdf_path)
    lines = []
    for page in doc:
        text = page.get_text()
        for line in text.split("\n"):
            line = line.strip()
            if line and not is_garbage_line(line):
                lines.append(line)
    return lines

# -----------------------------
# DETECT EXAM & STAGE/BRANCH
# -----------------------------
def detect_exam(pdf_path, lines):
    text = " ".join(lines).upper()
    filename = os.path.basename(pdf_path).upper()
    folder = os.path.basename(os.path.dirname(pdf_path)).upper()
    if "NEET" in text or "NEET" in filename or "NEET" in folder:
        return "NEET", "UG"
    if "JEE" in text or "IIT" in text:
        return "IIT JEE", "JEE Advanced" if "ADVANCED" in text else "JEE Main"
    if "GATE" in text or "GRADUATE APTITUDE TEST" in text:
        branch = "General"
        for l in lines:
            if l.upper().strip() in ["ME","IN","CE"]:
                branch = l.upper().strip()
                break
        return "GATE", branch
    return None, None

# -----------------------------
# PARSE SYLLABUS TO JSON
# -----------------------------
def parse_syllabus(root_dir):
    syllabus = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))
    remove_subjects = ["SECRETARY", "PUBLIC NOTICE"]
    for root, _, files in os.walk(root_dir):
        for file in files:
            if not file.lower().endswith(".pdf"): continue
            pdf_path = os.path.join(root, file)
            lines = read_pdf_lines(pdf_path)
            exam, stage = detect_exam(pdf_path, lines)
            if not exam: continue
            current_subject = None
            current_topic = None
            for line in lines:
                if line.isupper() and line.replace(" ","").isalpha() and len(line.split())<=5:
                    if line.upper() in remove_subjects:
                        current_subject = None
                        current_topic = None
                        continue
                    current_subject = line.title()
                    current_topic = None
                    continue
                if (":" in line or line[:2].isdigit() or line.startswith("-")) and len(line.split())<=12:
                    current_topic = line.replace(":", "").strip()
                    if current_subject:
                        syllabus[exam][stage][current_subject][current_topic] = []
                    continue
                if current_subject and current_topic:
                    parts = [p.strip() for p in line.split(",") if len(p.strip())>3]
                    syllabus[exam][stage][current_subject][current_topic].extend(parts)
    return syllabus

syllabus_json = parse_syllabus(EXTRACT_DIR)
if not syllabus_json:
    st.error("⚠️ No syllabus detected!")
    st.stop()

# -----------------------------
# UI: Select Exam & Subjects
# -----------------------------
st.title("📅 Competitive Exam Study Planner Calendar")
st.markdown("Plan your study schedule based on your priorities and time availability!")

selected_exam = st.selectbox("Select Exam", list(syllabus_json.keys()))
available_stages = list(syllabus_json[selected_exam].keys())
selected_stage = st.selectbox("Select Stage / Branch", available_stages)
available_subjects = list(syllabus_json[selected_exam][selected_stage].keys())
selected_subjects = st.multiselect("Select Subjects (priority order)", available_subjects)

# -----------------------------
# USER INPUTS
# -----------------------------
start_date = st.date_input("Choose your start day of preparation", value=datetime.today())
total_days = st.number_input("Enter the number of days to complete the syllabus", min_value=1, value=30, step=1)
capacity = st.number_input("Enter your daily study capacity (hours)", min_value=1.0, value=6.0, step=0.5)

st.subheader("Optional: Assign number of days per subject")
subject_days = {}
for subj in selected_subjects:
    days = st.number_input(f"Days to spend on {subj} (leave 0 for auto)", min_value=0, value=0, step=1)
    if days > 0:
        subject_days[subj] = days

# -----------------------------
# BUILD SUBJECT TIME MAP
# -----------------------------
def build_subject_time_map(exam, stage, subjects):
    subject_times = {}
    subject_subtopics = {}
    for subj in subjects:
        subtopics = []
        total_time = 0
        for topic, subs in syllabus_json[exam][stage][subj].items():
            for sub in subs:
                est_time_h = max(0.3 + 0.05 * len(sub.split()), 0.33)  # min 20 min
                est_time_min = round(est_time_h * 60)
                subtopics.append({"topic": topic, "subtopic": sub, "time_h": est_time_h, "time_min": est_time_min})
                total_time += est_time_h
        subject_times[subj] = total_time
        subject_subtopics[subj] = deque(subtopics)
    return subject_times, subject_subtopics

if selected_subjects:
    subject_times, subject_subtopics = build_subject_time_map(selected_exam, selected_stage, selected_subjects)

    # -----------------------------
    # PROGRESSIVE PRIORITY CALENDAR
    # -----------------------------
    calendar = []
    current_date = datetime.combine(start_date, datetime.min.time())
    num_subjects = len(selected_subjects)

    for day_index in range(total_days):
        day_plan = []
        day_progress = day_index / total_days
        dynamic_weights = []
        for i, subj in enumerate(selected_subjects):
            if subj in subject_days:
                # user-defined days
                daily_allocation = subject_times[subj] / subject_days[subj]
                dynamic_weights.append(daily_allocation)
            else:
                initial_weight = num_subjects - i
                weight = initial_weight * (1 - day_progress) + 1 * day_progress
                dynamic_weights.append(weight)

        total_weight = sum(dynamic_weights)
        allocation_map = {}
        for i, subj in enumerate(selected_subjects):
            if subj in subject_days:
                allocation_map[subj] = dynamic_weights[i]
            else:
                allocation_map[subj] = capacity * dynamic_weights[i] / total_weight

        # Assign subtopics for the day
        for subj in selected_subjects:
            remaining_time = allocation_map[subj]
            subtopic_queue = subject_subtopics[subj]
            while subtopic_queue and remaining_time > 0:
                item = subtopic_queue[0]
                time_to_assign_h = min(item["time_h"], remaining_time)
                day_plan.append({
                    "subject": subj,
                    "subtopic": item["subtopic"],
                    "time_h": time_to_assign_h,
                    "time_min": round(time_to_assign_h * 60)
                })
                remaining_time -= time_to_assign_h
                item["time_h"] -= time_to_assign_h
                if item["time_h"] <= 0.001:
                    subtopic_queue.popleft()

        calendar.append({"date": current_date, "plan": day_plan})
        current_date += timedelta(days=1)

    # -----------------------------
    # DASHBOARD
    # -----------------------------
    if 'completed_subtopics' not in st.session_state:
        st.session_state.completed_subtopics = set()

    # Colors for subjects
    subject_colors = {}
    default_colors = ["#FF9999","#99CCFF","#99FF99","#FFCC99","#FFCCFF","#CCFF99","#FF9966"]
    for i, subj in enumerate(selected_subjects):
        subject_colors[subj] = default_colors[i % len(default_colors)]

    st.header("📅 Study Planner Dashboard")
    weeks = total_days // 7 + 1
    tabs = st.tabs([f"Week {i+1}" for i in range(weeks)])

    for week_index, tab in enumerate(tabs):
        with tab:
            week_start = week_index * 7
            week_end = min((week_index + 1) * 7, total_days)
            for day_index in range(week_start, week_end):
                day = calendar[day_index]
                st.markdown(f"### 📌 {day['date'].strftime('%A, %d %b %Y')}")
                if day['plan']:
                    for sub_index, s in enumerate(day['plan']):
                        key = f"{day_index}_{s['subject']}_{s['subtopic']}_{sub_index}"
                        checked = key in st.session_state.completed_subtopics
                        st.checkbox(f"{s['subject']} → {s['subtopic']} ({s['time_min']} min)", value=checked, key=key)
                        if checked:
                            st.session_state.completed_subtopics.add(key)
                        else:
                            st.session_state.completed_subtopics.discard(key)
                else:
                    st.info("Rest day / No subtopics assigned")

    # Remaining time per subject
    st.subheader("⏳ Remaining Study Time per Subject")
    subject_remaining = {subj: 0 for subj in selected_subjects}
    for day_index, day in enumerate(calendar):
        for subj in selected_subjects:
            day_subj_time = sum(s["time_h"] for s in day['plan'] if s["subject"] == subj)
            day_subj_done = sum(
                s["time_h"]
                for sub_index, s in enumerate(day['plan'])
                if s["subject"] == subj and
                f"{day_index}_{s['subject']}_{s['subtopic']}_{sub_index}" in st.session_state.completed_subtopics
            )
            remaining_time = day_subj_time - day_subj_done
            subject_remaining[subj] += max(remaining_time, 0)

    cols = st.columns(len(selected_subjects))
    for col, subj in zip(cols, selected_subjects):
        col.metric(label=f"📘 {subj}", value=f"{round(subject_remaining[subj]*60)} min remaining")
