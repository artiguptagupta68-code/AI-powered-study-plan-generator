import os
import zipfile
import fitz
import gdown
from collections import defaultdict

# -----------------------------
# CONFIG
# -----------------------------
DRIVE_FILE_ID = "1S6fcsuq9KvICTsOBOdp6_WN9FhzruixM"
ZIP_PATH = "plan.zip"
EXTRACT_DIR = "syllabus_data"

# -----------------------------
# DOWNLOAD ZIP
# -----------------------------
if not os.path.exists(ZIP_PATH):
    gdown.download(f"https://drive.google.com/uc?id={DRIVE_FILE_ID}", ZIP_PATH, quiet=False)

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
        lines += [l.strip() for l in page.get_text().split("\n") if l.strip()]
    return lines

# -----------------------------
# DETECT EXAM + STAGE
# -----------------------------
def detect_exam(pdf_path, lines):
    text = " ".join(lines).upper()
    fname = os.path.basename(pdf_path).upper()

    # NEET
    if "NEET" in text or "NEET" in fname:
        return "NEET", "UG"

    # IIT JEE
    if "JEE" in text or "IIT" in text:
        if "ADVANCED" in text:
            return "IIT JEE", "JEE Advanced"
        return "IIT JEE", "JEE Main"

    # GATE
    if "GATE" in text or fname.startswith("GATE"):
        branch = "General"
        for l in lines:
            if l.isupper() and len(l.split()) <= 5 and "GATE" not in l:
                branch = l
                break
        return "GATE", branch

    return None, None

# -----------------------------
# PARSE ALL PDFs
# -----------------------------
def parse_syllabus(root):
    syllabus = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))

    for root_dir, _, files in os.walk(root):
        for file in files:
            if not file.lower().endswith(".pdf"):
                continue

            path = os.path.join(root_dir, file)
            lines = read_pdf_lines(path)
            exam, stage = detect_exam(path, lines)

            if not exam:
                continue

            subject = topic = None

            for line in lines:
                # SUBJECT
                if line.isupper() and line.replace(" ", "").isalpha() and len(line.split()) <= 5:
                    subject = line.title()
                    continue

                # TOPIC
                if (":" in line or line[:2].isdigit()) and subject:
                    topic = line.replace(":", "").strip()
                    syllabus[exam][stage][subject][topic] = []
                    continue

                # SUBTOPIC
                if subject and topic:
                    syllabus[exam][stage][subject][topic].append(line)

    return syllabus

# -----------------------------
# RUN
# -----------------------------
syllabus_json = parse_syllabus(EXTRACT_DIR)

print("✅ Exams detected:", list(syllabus_json.keys()))
