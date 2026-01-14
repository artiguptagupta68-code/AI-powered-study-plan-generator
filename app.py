# app.py
import streamlit as st
import os
import zipfile
import gdown
import fitz  # PyMuPDF
import re
import json
from collections import defaultdict
from datetime import datetime, timedelta
from math import ceil

# -----------------------------
# CONFIGURATION
# -----------------------------
DRIVE_FILE_ID = "1S6fcsuq9KvICTsOBOdp6_WN9FhzruixM"
ZIP_PATH = "plan.zip"
EXTRACT_DIR = "syllabus_data"

st.set_page_config(page_title="📚 Competitive Study Planner", layout="wide")

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
def is_garbage_line(line: str) -> bool:
    l = line.lower()
    garbage_keywords = [
        "annexure", "government of india", "national medical commission",
        "medical education", "ugmeb", "neet (ug exam)", "date:", "sector",
        "dwarka", "new delhi", "pocket-", "phase-", "board)", "exam)"
    ]
    if any(k in l for k in garbage_keywords):
        return True
    if re.match(r"[a-z]-\d+/\d+", l):
        return True
    if re.search(r"\d{1,2}(st|nd|rd|th)?\s+[a-z]+\s+\d{4}", l):
        return True
    if len(line) > 120:
        return True
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

    # NEET
    if "NEET" in text or "NEET" in filename or "NEET" in folder:
        return "NEET", "UG"
    # IIT JEE
    if "JEE" in text or "IIT" in text:
        if "ADVANCED" in text:
            return "IIT JEE", "JEE Advanced"
        return "IIT JEE", "JEE Main"
    # GATE
    if "GATE" in text or "GRADUATE APTITUDE TEST" in text:
        branch = "General"
        for l in lines:
            l_clean = l.upper().strip()
            if l_clean in ["ME", "IN", "CE"]:
                branch = l_clean
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
            if not file.lower().endswith(".pdf"):
                continue

            pdf_path = os.path.join(root, file)
            lines = read_pdf_lines(pdf_path)
            exam, stage = detect_exam(pdf_path, lines)
            if not exam:
                continue

            current_subject = None
            current_topic = None

            for line in lines:
                # SUBJECT
                if line.isupper() and line.replace(" ", "").isalpha() and len(line.split()) <= 5:
                    if line.upper() in remove_subjects:
                        current_subject = None
                        current_topic = None
                        continue
                    current_subject = line.title()
                    current_topic = None
                    continue

                # TOPIC
                if (":" in line or line[:2].isdigit() or line.startswith("-")) and len(line.split()) <= 12:
                    current_topic = line.replace(":", "").strip()
                    if current_subject:
                        syllabus[exam][stage][current_subject][current_topic] = []
                    continue

                # SUBTOPIC
                if current_subject and current_topic:
                    parts = [p.strip() for p in line.split(",") if len(p.strip()) > 3]
                    syllabus[exam][stage][current_subject][current_topic].extend(parts)
    return syllabus

syllabus_json = parse_syllabus(EXTRACT_DIR)

if not syllabus_json:
    st.error("⚠️ No syllabus detected!")
    st.stop()

# -----------------------------
# STUDY PLANNER STATE
# -----------------------------
if "carryover" not in st.session_state:
    st.session_state.carryover = defaultdict(list)

# -----------------------------
# UI
# -----------------------------
st.title("📚 Competitive Exam Study Planner")

# Step 1: Select exam
selected_exam = st.selectbox("Select Exam", list(syllabus_json.keys()))
st.write(f"Selected Exam: **{selected_exam}**")

# Step 2: Select subjects
available_subjects = list(syllabus_json[selected_exam].keys())
selected_subjects = st.multiselect("Select Subject(s)", available_subjects)

# Step 3: Enter today's study capacity
capacity = st.number_input("Enter your available study hours today", min_value=1.0, value=6.0, step=0.5)

# Step 4: Assign subtopics automatically
if st.button("Load Today's Subtopics"):
    today_subtopics = []
    for subject in selected_subjects:
        for topic, subs in syllabus_json[selected_exam][subject].items():
            for sub in subs:
                today_subtopics.append({
                    "subject": subject,
                    "subtopic": sub,
                    "time": max(0.2, 0.5/len(sub)),  # dynamic weighting
                    "done": False
                })

    # Include carryover
    if st.session_state.carryover[selected_exam]:
        today_subtopics = st.session_state.carryover[selected_exam] + today_subtopics
        st.session_state.carryover[selected_exam] = []

    # Assign subtopics based on capacity
    assigned_subtopics = []
    used_hours = 0
    for s in today_subtopics:
        est = s["time"]
        if used_hours + est <= capacity:
            assigned_subtopics.append(s)
            used_hours += est
        else:
            # carryover the rest
            st.session_state.carryover[selected_exam].append(s)

    st.subheader(f"📌 Today's Assigned Subtopics ({len(assigned_subtopics)} subtopics, {used_hours:.2f}h)")
    st.caption(f"💡 Complete these first. Unfinished subtopics will carry over to the next day.")

    # Display in 2 columns
    cols = st.columns(2)
    col_idx = 0
    for idx, item in enumerate(assigned_subtopics):
        checked = cols[col_idx].checkbox(f"{item['subtopic']} ({item['time']:.2f}h)", key=f"sub_{idx}")
        if checked:
            assigned_subtopics[idx]["done"] = True
        col_idx = (col_idx + 1) % 2

    # Progress bar
    completed = sum(1 for s in assigned_subtopics if s["done"])
    st.progress(completed / len(assigned_subtopics))
    st.caption(f"{completed}/{len(assigned_subtopics)} subtopics completed ✅")
