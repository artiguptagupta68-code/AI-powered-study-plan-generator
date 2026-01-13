import fitz
import os
import json
from collections import defaultdict

# -----------------------------
# 1. Read PDF text safely
# -----------------------------
def read_pdf_lines(pdf_path):
    doc = fitz.open(pdf_path)
    lines = []
    for page in doc:
        text = page.get_text("text")
        for line in text.split("\n"):
            line = line.strip()
            if line:
                lines.append(line)
    return lines


# -----------------------------
# 2. Detect exam name
# -----------------------------
def detect_exam(lines):
    text = " ".join(lines[:50]).upper()
    if "GATE" in text:
        return "GATE"
    if "SSC" in text:
        return "SSC"
    if "UPSC" in text or "UNION PUBLIC SERVICE COMMISSION" in text:
        return "UPSC"
    return "UNKNOWN"


# -----------------------------
# 3. PDF → JSON syllabus
# -----------------------------
def pdfs_to_json(pdf_folder):
    syllabus = defaultdict(
        lambda: defaultdict(
            lambda: defaultdict(list)
        )
    )

    for file in os.listdir(pdf_folder):
        if not file.lower().endswith(".pdf"):
            continue

        pdf_path = os.path.join(pdf_folder, file)
        lines = read_pdf_lines(pdf_path)

        exam = detect_exam(lines)

        current_subject = None
        current_topic = None

        for line in lines:
            clean = line.strip()

            # ---- SUBJECT HEURISTIC ----
            if (
                clean.isupper()
                and clean.replace(" ", "").isalpha()
                and len(clean.split()) <= 5
            ):
                current_subject = clean.title()
                current_topic = None
                continue

            # ---- TOPIC HEURISTIC ----
            if (
                ":" in clean
                or clean[:2].isdigit()
                or clean.startswith("-")
            ) and len(clean.split()) <= 12:
                current_topic = clean.replace(":", "").strip()
                if current_subject:
                    syllabus[exam][current_subject][current_topic] = []
                continue

            # ---- SUBTOPIC HEURISTIC ----
            if current_subject and current_topic:
                # split comma-separated syllabus lines
                parts = [p.strip() for p in clean.split(",") if len(p.strip()) > 3]
                syllabus[exam][current_subject][current_topic].extend(parts)

    return syllabus


# -----------------------------
# 4. Save JSON
# -----------------------------
def save_json(data, output_path="syllabus.json"):
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
