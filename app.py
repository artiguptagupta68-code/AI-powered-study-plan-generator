import streamlit as st
import os
import zipfile
import gdown
import fitz
from collections import defaultdict

# --------------------------------
# CONFIG
# --------------------------------
DRIVE_FILE_ID = "1S6fcsuq9KvICTsOBOdp6_WN9FhzruixM"
ZIP_FILE = "syllabus.zip"
EXTRACT_DIR = "syllabus_data"

st.set_page_config("Syllabus Viewer", layout="wide")
st.title("📚 Exam Syllabus Viewer")

# --------------------------------
# DOWNLOAD ZIP
# --------------------------------
if not os.path.exists(ZIP_FILE):
    with st.spinner("⬇️ Downloading syllabus ZIP..."):
        gdown.download(
            f"https://drive.google.com/uc?id={DRIVE_FILE_ID}",
            ZIP_FILE,
            quiet=False
        )
    st.success("ZIP downloaded")

# --------------------------------
# EXTRACT ZIP
# --------------------------------
os.makedirs(EXTRACT_DIR, exist_ok=True)
with zipfile.ZipFile(ZIP_FILE, "r") as z:
    z.extractall(EXTRACT_DIR)

# --------------------------------
# PDF READER
# --------------------------------
def read_pdf_lines(path):
    doc = fitz.open(path)
    lines = []
    for page in doc:
        for l in page.get_text().split("\n"):
            l = l.strip()
            if l:
                lines.append(l)
    return lines

# --------------------------------
# PARSE ALL SYLLABUS
# --------------------------------
def parse_all_syllabus(root):
    syllabus = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for root_dir, _, files in os.walk(root):
        for file in files:
            if not file.lower().endswith(".pdf"):
                continue

            pdf_path = os.path.join(root_dir, file)
            lines = read_pdf_lines(pdf_path)

            filename = file.lower()
            folder = os.path.basename(root_dir).lower()

            # ---------------- NEET ----------------
            if "neet" in folder:
                exam = "NEET"
                subject = None

                for line in lines:
                    if line.isupper() and len(line.split()) <= 4:
                        subject = line.title()
                        continue
                    if subject:
                        syllabus[exam][subject]["Topics"].append(line)

            # ---------------- IIT JEE ----------------
            elif "jee" in filename:
                exam = "IIT JEE"
                subject = None

                for line in lines:
                    if line.isupper() and len(line.split()) <= 4:
                        subject = line.title()
                        continue
                    if subject:
                        syllabus[exam][subject]["Topics"].append(line)

            # ---------------- GATE ----------------
            elif filename.startswith("gate"):
                exam = "GATE"
                branch = "General"

                for l in lines[:30]:
                    if l.isupper() and len(l.split()) <= 4 and "GATE" not in l:
                        branch = l
                        break

                subject = None
                for line in lines:
                    if line.isupper() and len(line.split()) <= 4:
                        subject = line.title()
                        continue
                    if subject:
                        syllabus[f"{exam} ({branch})"][subject]["Topics"].append(line)

    return syllabus

# --------------------------------
# RUN PARSER
# --------------------------------
syllabus_json = parse_all_syllabus(EXTRACT_DIR)

if not syllabus_json:
    st.error("❌ No syllabus detected")
    st.stop()

# --------------------------------
# UI
# --------------------------------
st.sidebar.header("🎯 Select")

exam = st.sidebar.selectbox("Exam", list(syllabus_json.keys()))
subject = st.sidebar.selectbox(
    "Subject", list(syllabus_json[exam].keys())
)

st.header(f"📘 {exam}")
st.subheader(f"📖 {subject}")

for topic in syllabus_json[exam][subject]["Topics"]:
    st.write(f"- {topic}")

# --------------------------------
# DEBUG
# --------------------------------
with st.expander("🔍 View Full JSON"):
    st.json(syllabus_json)
