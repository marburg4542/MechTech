import os
import json
import google.generativeai as genai
import pytz
from dotenv import load_dotenv
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from PyPDF2 import PdfReader

# โหลดค่า API key
load_dotenv("GEMINI_API_KEY.env")
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# ตั้งค่าการสร้างข้อความ
generation_config = {
    "temperature": 2.0,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 4096,
    "response_mime_type": "text/plain",
}

# สร้างโมเดล
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config,
    system_instruction="""
    เธอชื่อ MechTech เป็น AI chatbot เพศหญิงที่สามารถพูดคุยกับผู้ใช้ได้อย่างเป็นกันเอง
    เธอสามารถตอบคำถามเกี่ยวกับวิศวกรรมเครื่องกลและข้อมูลทางเทคนิคได้ แต่ก็สามารถพูดคุยเล่น
    เล่าเรื่องตลก ให้กำลังใจ หรือแม้แต่เล่นเกมคำถามกับผู้ใช้ได้ด้วย
    เธอสามารถตอบได้ทั้งภาษาไทยและภาษาอังกฤษ
    """,
)

app = Flask(__name__)
CORS(app)  # อนุญาตให้ frontend เชื่อมต่อกับ backend

# ฟังก์ชันโหลดประวัติการสนทนา
def load_chat_history():
    if os.path.exists("chat_log.json"):
        try:
            with open("chat_log.json", "r", encoding="utf-8") as file:
                return json.load(file)
        except json.JSONDecodeError:
            return []
    return []

# ฟังก์ชันบันทึกการสนทนา
def log_chat(role, message):
    tz = pytz.timezone('Asia/Bangkok')
    current_time = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    chat_log = load_chat_history()
    chat_log.append({"role": role, "message": message, "timestamp": current_time})
    with open("chat_log.json", "w", encoding="utf-8") as file:
        json.dump(chat_log, file, ensure_ascii=False, indent=4)

# ฟังก์ชันโหลดข้อมูลจากไฟล์ PDF ทั้งหมดในโฟลเดอร์ SUT_Plan
def load_data_from_pdfs(folder_path):
    all_text = ""
    if not os.path.exists(folder_path):
        print(f"โฟลเดอร์ {folder_path} ไม่พบ")
        return ""
    
    for filename in os.listdir(folder_path):
        if filename.endswith(".pdf"):
            pdf_path = os.path.join(folder_path, filename)
            try:
                with open(pdf_path, "rb") as file:
                    pdf_reader = PdfReader(file)
                    for page in pdf_reader.pages:
                        all_text += page.extract_text() + "\n"
            except Exception as e:
                print(f"เกิดข้อผิดพลาดในการอ่าน {filename}: {e}")
    return all_text.strip()

# ระบุโฟลเดอร์ PDF
documents_text = load_data_from_pdfs("SUT_Plan")

@app.route("/chatbot", methods=["POST"])
def chatbot():
    data = request.json
    user_message = data.get("message", "")
    
    if not user_message:
        return jsonify({"response": "โปรดป้อนข้อความ"})  # ภาษาไทย
    elif user_message.isascii():  # ถ้าเป็นภาษาอังกฤษ
        language = "en"
    else:  # ถ้าเป็นภาษาไทย
        language = "th"

    try:
        chat_history = load_chat_history()
        formatted_chat_history = [
            {"role": entry["role"], "parts": [{"text": entry["message"]}]} 
            for entry in chat_history
        ]
        
        chat_session = model.start_chat(history=formatted_chat_history)
        prompt = f"{documents_text}\n\nผู้ใช้: {user_message}" if language == "th" else f"{documents_text}\n\nUser: {user_message}"
        response = chat_session.send_message(prompt)
        
        if not response.text:
            return jsonify({"response": "ขอโทษค่ะ ฉันไม่สามารถตอบได้ในขณะนี้"})  # ภาษาไทย
        
        # บันทึกประวัติการสนทนา
        log_chat("user", user_message)
        log_chat("model", response.text)
        
        return jsonify({"response": response.text})
    
    except Exception as e:
        print(f"Error in chatbot: {e}")
        return jsonify({"response": "เกิดข้อผิดพลาด โปรดลองใหม่อีกครั้ง"})  # ภาษาไทย

if __name__ == "__main__":
    app.run(debug=True, port=5000)
