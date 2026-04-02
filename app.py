import os
import io
import base64
import json
import uuid
import functools

from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

import pytesseract
from pdf2image import convert_from_path
from PIL import Image
from docx import Document

from groq import Groq

load_dotenv()

app = Flask(__name__)
CORS(app)

# ---------------- CONFIG ---------------- #

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
API_KEY = os.getenv("API_KEY")

client = Groq(api_key=GROQ_API_KEY)


# ---------------- AUTH ---------------- #

def require_api_key(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):

        key = request.headers.get("x-api-key")

        if not key or key != API_KEY:
            return jsonify({
                "status": "error",
                "message": "Unauthorized"
            }), 401

        return f(*args, **kwargs)

    return decorated


# ---------------- OCR FUNCTIONS ---------------- #

def extract_pdf_text(path):

    text = ""

    pages = convert_from_path(
        path,
        dpi=200,
        first_page=1,
        last_page=3
    )

    for page in pages:

        text += pytesseract.image_to_string(
            page,
            config="--oem 3 --psm 6"
        )

    return text


def extract_image_text(path):

    img = Image.open(path).convert("L")

    return pytesseract.image_to_string(
        img,
        config="--oem 3 --psm 6"
    )


def extract_docx_text(file_bytes):

    doc = Document(io.BytesIO(file_bytes))

    return "\n".join(
        p.text for p in doc.paragraphs if p.text.strip()
    )


# ---------------- AI ANALYSIS ---------------- #

def analyse(text):

    prompt = f"""
You are a document analysis AI.

Return ONLY JSON.

Format:

{{
 "summary":"",
 "entities": {{
  "names":[],
  "dates":[],
  "organizations":[],
  "amounts":[]
 }},
 "sentiment":"Positive | Neutral | Negative"
}}

Document:

{text[:2000]}
"""

    chat = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=300,
    )

    raw = chat.choices[0].message.content.strip()

    if raw.startswith("```"):
        raw = raw.split("```")[1]
        raw = raw.replace("json", "").strip()

    try:
        return json.loads(raw)
    except:
        return {
            "summary": raw,
            "entities": {
                "names": [],
                "dates": [],
                "organizations": [],
                "amounts": []
            },
            "sentiment": "Neutral"
        }


# ---------------- ROUTES ---------------- #

@app.route("/")
def home():
    return {"status": "running"}


@app.route("/health")
def health():
    return {"status": "ok"}


@app.route("/api/document-analyze", methods=["POST"])
@require_api_key
def analyze():

    body = request.get_json(silent=True)

    if not body:
        return jsonify({
            "status":"error",
            "message":"JSON body required"
        }),400

    file_name = body.get("fileName","file")
    file_type = body.get("fileType","").lower()
    file_b64  = body.get("fileBase64")

    if not file_type or not file_b64:
        return jsonify({
            "status":"error",
            "message":"fileType and fileBase64 required"
        }),400


    try:
        file_bytes = base64.b64decode(file_b64)
    except:
        return jsonify({
            "status":"error",
            "message":"Invalid base64"
        }),400


    text = ""

    try:

        if file_type == "docx":

            text = extract_docx_text(file_bytes)


        elif file_type == "pdf":

            path = f"/tmp/{uuid.uuid4()}.pdf"

            with open(path,"wb") as f:
                f.write(file_bytes)

            text = extract_pdf_text(path)

            os.remove(path)


        elif file_type in ["png","jpg","jpeg"]:

            path = f"/tmp/{uuid.uuid4()}.png"

            with open(path,"wb") as f:
                f.write(file_bytes)

            text = extract_image_text(path)

            os.remove(path)


        else:

            return jsonify({
                "status":"error",
                "message":"Unsupported fileType"
            }),400


    except Exception as e:

        return jsonify({
            "status":"error",
            "message":f"OCR failed: {str(e)}"
        }),500


    if not text.strip():

        return jsonify({
            "status":"error",
            "message":"No text extracted"
        }),422


    try:

        analysis = analyse(text)

    except Exception as e:

        return jsonify({
            "status":"error",
            "message":f"AI analysis failed: {str(e)}"
        }),500


    return jsonify({

        "status":"success",
        "fileName":file_name,
        "summary":analysis.get("summary",""),
        "entities":analysis.get("entities",{
            "names":[],
            "dates":[],
            "organizations":[],
            "amounts":[]
        }),
        "sentiment":analysis.get("sentiment","Neutral")

    })


# ---------------- RUN ---------------- #

if __name__ == "__main__":

    port = int(os.getenv("PORT",5000))

    app.run(
        host="0.0.0.0",
        port=port
    )