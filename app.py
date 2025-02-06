import os
import io
import json
import re
from flask import Flask, request, jsonify, render_template
import fitz  # PyMuPDF for PDF processing
import google.generativeai as genai
from werkzeug.utils import secure_filename
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from flask_cors import CORS, cross_origin  # Import CORS

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Enable CORS for all routes, allowing requests from Angular frontend
CORS(app, resources={r"/*": {"origins": "http://localhost:4200"}})

# Configure upload folder and max file size
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Max upload size: 16MB

# Create uploads folder if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

class ResumeParser:
    def __init__(self, api_key: str):
        """Initialize the ResumeParser with Gemini API key."""
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-pro')

    def extract_text_from_pdf(self, pdf_content: bytes) -> Optional[str]:
        try:
            pdf_stream = io.BytesIO(pdf_content)
            pdf = fitz.open(stream=pdf_stream, filetype="pdf")
            text_content = []

            for page_num in range(len(pdf)):
                page = pdf[page_num]
                text_content.append(page.get_text("text"))

            return "\n".join(text_content)

        except Exception as e:
            print(f"An error occurred while processing PDF: {e}")
            return None
        finally:
            if 'pdf' in locals():
                pdf.close()

    def preprocess_resume_text(self, text: str) -> str:
        return re.sub(r'\s+', ' ', text).strip()

    def _create_prompt(self, resume_text: str) -> str:
        return f"""
        Please analyze the following resume text and convert it into a structured JSON format.
        Include the following sections if present:
        - Personal Information (name, email, phone, location)
        - Summary/Objective
        - Work Experience (with company, position, dates, and responsibilities)
        - Education
        - Skills
        - Certifications
        - Projects

        Resume Text:
        {resume_text}

        Provide the output in valid JSON format only, without any additional text.
        """

    def _clean_response(self, response: str) -> str:
        return response.replace('```json', '').replace('```', '').strip()

    def parse_resume(self, pdf_content: bytes) -> Optional[Dict[str, Any]]:
        try:
            raw_text = self.extract_text_from_pdf(pdf_content)
            if not raw_text:
                return None

            resume_text = self.preprocess_resume_text(raw_text)
            prompt = self._create_prompt(resume_text)
            response = self.model.generate_content(prompt)
            cleaned_response = self._clean_response(response.text)
            resume_json = json.loads(cleaned_response)

            return resume_json

        except Exception as e:
            print(f"Error parsing resume: {str(e)}")
            return None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Initialize parser with environment variable API key
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')  # Load the API key securely from environment variables
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is not set.")
parser = ResumeParser(GEMINI_API_KEY)

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')  # Render the UI template

@app.route('/healthz', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok'}), 200

@app.route('/predict', methods=['POST'])
@cross_origin(origin='http://localhost:4200', headers=['Content-Type', 'Authorization'])
def parse_resume_endpoint():
    # Check if a file was sent in the request
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']

    # Check if a file was selected
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    # Check if the file is a PDF
    if file.filename.rsplit('.', 1)[1].lower() != 'pdf':
        return jsonify({'error': 'Invalid file type. Only PDF files are allowed'}), 400

    if file and allowed_file(file.filename):
        try:
            # Read the file content
            pdf_content = file.read()
            
            # Parse the resume
            result = parser.parse_resume(pdf_content)
            
            if result:
                return jsonify(result)
            else:
                return jsonify({'error': 'Failed to parse resume'}), 500
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    return jsonify({'error': 'Invalid file type'}), 400

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=81)  
