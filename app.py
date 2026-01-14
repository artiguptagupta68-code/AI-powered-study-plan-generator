# app.py
import streamlit as st
import os
import zipfile
import gdown
import fitz
from collections import defaultdict
import json

# -----------------------------
# CONFIG
# -----------------------------
DRIVE_FILE_ID = "1S6fcsuq9KvICTsOBOdp6_WN9FhzruixM"
ZIP_PATH = "syllabus.zip"
EXTRACT_DIR = "syllabus_data"

st.set_page_config(page_title="GATE Syllabus Viewer", layout="wide")
st.title("📘 GATE Syllabus Viewer")

# -----------------------------
# DOWNLOAD ZIP
# -----------------------------
if not os.path.exists(ZIP_PATH):
    with st.spinner("⬇️ Downloading syllabus ZIP from Google Drive..."):
        gdown.download(
            f"https://drive.google.com/uc?id={DRIVE_FILE_ID}",
            ZIP_PATH,
            quiet=False
        )
    st.success("✅ ZIP downloaded")
else:
    st.info("ℹ️ ZIP already downloaded")

# -----------------------------
# EXTRACT ZIP
# -----------------------------
os.makedirs(EXTRACT_DIR, exist_ok=True)
with zipfile.ZipFile(ZIP_PATH, "r") as z:
    z.extractall(EXTRACT_DIR)

# -----------------------------
# READ PDF
# -----------------------------
def read_pdf_lines(path):
    doc = fitz.open(path)
    lines = []
    for page in doc:
        for l in page.get_text().split("\n"):
            l = l.strip()
            if l:
                lines.append(l)
    return lines

# -----------------------------
# DETECT GATE BRANCH
# -----------------------------
def detect_gate_branch(lines):
    for l in lines:
        if (
            l.isupper()
            and len(l.split()) <= 5
            and "GATE" not in l
            and not l.isdigit()
        ):
            return l
    return "General"

# -----------------------------
# PARSE ONLY GATE PDFs
# -----------------------------
def parse_gate_syllabus(root):
    gate_json = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for root_dir, _, files in os.walk(root):
        for file in files:
            if not file.lower().endswith(".pdf"):
                continue

            if not file.lower().startswith("gate"):
                continue  # ONLY gate PDFs

            pdf_path = os.path.join(root_dir, file)
            lines = read_pdf_lines(pdf_path)

            branch = detect_gate_branch(lines)

            subject = topic = None

            for line in lines:
                # SUBJECT
                if (
                    line.isupper()
                    and line.replace(" ", "").isalpha()
                    and len(line.split()) <= 5
                ):
                    subject = line.title()
                    topic = None
                    continue

                # TOPIC
                if (":" in line or line[:2].isdigit()) and subject:
                    topic = line.replace(":", "").strip()
                    gate_json[branch][subject][topic] = []
                    continue

                # SUBTOPIC
                if subject and topic:
                    gate_json[branch][subject][topic].append(line)

    return gate_json

# -----------------------------
# RUN PARSING
# -----------------------------
gate_syllabus = parse_gate_syllabus(EXTRACT_DIR)

if not gate_syllabus:
    st.error("❌ No GATE syllabus detected in ZIP")
    st.stop()

st.success(f"✅ GATE branches detected: {', '.join(gate_syllabus.keys())}")

# -----------------------------
# UI
# -----------------------------
st.sidebar.header("🎯 Select")

branch = st.sidebar.selectbox("Branch", list(gate_syllabus.keys()))
subject = st.sidebar.selectbox(
    "Subject", list(gate_syllabus[branch].keys())
)

st.header(f"🧠 Branch: {branch}")
st.subheader(f"📚 Subject: {subject}")

for topic, subtopics in gate_syllabus[branch][subject].items():
    with st.expander(f"📌 {topic}"):
        if subtopics:
            for s in subtopics:
                st.write(f"- {s}")
        else:
            st.write("No subtopics listed")

# -----------------------------
# DEBUG
# -----------------------------
with st.expander("🔍 View Raw GATE JSON"):
    st.json(gate_syllabus)
