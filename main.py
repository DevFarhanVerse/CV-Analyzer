import os
import glob
import re
import pandas as pd
from PyPDF2 import PdfReader
from docx import Document
from flask import Flask, request, render_template, send_file, redirect, url_for
import shutil

app = Flask(__name__)

# Directory setup
BASE_DIR = os.getcwd()
INPUT_DIR = os.path.join(BASE_DIR, "Input Data")
OUTPUT_CSV = os.path.join(BASE_DIR, "cv_extracted_details.csv")

# Ensure Input Data directory exists
if not os.path.exists(INPUT_DIR):
    os.makedirs(INPUT_DIR)

# Regular expressions for extracting data
EMAIL_REGEX = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
PHONE_REGEX = r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
NAME_REGEX = r'Name:?\s*([A-Za-z]+\s+[A-Za-z]+)|^[A-Za-z]+\s+[A-Za-z]+'


# Function to extract text from PDF
def extract_text_from_pdf(file_path):
    try:
        reader = PdfReader(file_path, strict=False)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text
        return text
    except Exception as e:
        print(f"Error reading PDF {file_path}: {e}")
        return ""


# Function to extract text from DOCX
def extract_text_from_docx(file_path):
    try:
        doc = Document(file_path)
        text = "\n".join([para.text for para in doc.paragraphs])
        return text
    except Exception as e:
        print(f"Error reading DOCX {file_path}: {e}")
        return ""


# Function to extract text from TXT
def extract_text_from_txt(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        print(f"Error reading TXT {file_path}: {e}")
        return ""


# Function to extract details from text
def extract_details(text, file_name):
    email = re.search(EMAIL_REGEX, text)
    email = email.group(0) if email else "Not Found"

    phone = re.search(PHONE_REGEX, text)
    phone = phone.group(0) if phone else "Not Found"

    name_match = re.search(NAME_REGEX, text, re.MULTILINE)
    if name_match:
        name = name_match.group(1) if name_match.group(
            1) else name_match.group(0)
    else:
        words = text.split()[:2]
        name = " ".join(words) if len(words) >= 2 else "Not Found"

    return {
        "File Name": file_name,
        "Full Name": name,
        "Email Address": email,
        "Phone Number": phone
    }


# Route for the homepage
@app.route('/', methods=['GET', 'POST'])
def index():
    status = "Ready to upload CV files."
    uploaded_files = []
    csv_ready = False

    if request.method == 'POST':
        # Clear previous files in Input Data directory
        for file in glob.glob(os.path.join(INPUT_DIR, "*")):
            os.remove(file)

        # Handle file uploads
        if 'files' not in request.files:
            status = "No files selected."
            return render_template('index.html',
                                   status=status,
                                   uploaded_files=uploaded_files,
                                   csv_ready=csv_ready)

        files = request.files.getlist('files')
        if not files or all(file.filename == '' for file in files):
            status = "No files selected."
            return render_template('index.html',
                                   status=status,
                                   uploaded_files=uploaded_files,
                                   csv_ready=csv_ready)

        # Save uploaded files to Input Data directory
        for file in files:
            if file:
                file_path = os.path.join(INPUT_DIR, file.filename)
                file.save(file_path)
                uploaded_files.append(file.filename)

        # Process the files
        extracted_data = []
        supported_extensions = {".pdf", ".docx", ".txt"}
        unique_files = set()

        for file_name in uploaded_files:
            file_path = os.path.join(INPUT_DIR, file_name)
            if file_name.startswith("~") or file_name in {"Thumbs.db"}:
                continue

            _, ext = os.path.splitext(file_path)
            ext = ext.lower()

            if ext in supported_extensions and file_path not in unique_files:
                unique_files.add(file_path)
                if ext == ".pdf":
                    text = extract_text_from_pdf(file_path)
                elif ext == ".docx":
                    text = extract_text_from_docx(file_path)
                elif ext == ".txt":
                    text = extract_text_from_txt(file_path)
                else:
                    continue

                if text:
                    details = extract_details(text, file_name)
                    extracted_data.append(details)
                else:
                    extracted_data.append({
                        "File Name": file_name,
                        "Full Name": "Not Found",
                        "Email Address": "Not Found",
                        "Phone Number": "Not Found"
                    })

        if extracted_data:
            df = pd.DataFrame(extracted_data)
            df.to_csv(OUTPUT_CSV, index=False)
            status = "Extraction complete! Ready to download CSV."
            csv_ready = True
        else:
            status = "No data extracted."
            csv_ready = False

    return render_template('index.html',
                           status=status,
                           uploaded_files=uploaded_files,
                           csv_ready=csv_ready)


# Route to download the CSV
@app.route('/download')
def download_csv():
    if os.path.exists(OUTPUT_CSV):
        return send_file(OUTPUT_CSV, as_attachment=True)
    else:
        return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
