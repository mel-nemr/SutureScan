from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
import json
import os
import re
import time
import csv
import pandas as pd
from PIL import Image, ImageEnhance
import io
import base64
from openai import OpenAI
import threading

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXCEL_FILE = os.path.join(BASE_DIR, "suture_catalogue.xlsx")
METRICS_FILE = os.path.join(BASE_DIR, "scan_metrics.csv")
MEMORY_FILE = os.path.join(BASE_DIR, "ai_memory.json")

file_lock = threading.Lock()

print("Connecting to LM Studio Local Server...")
client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

def load_memory():
    with file_lock:
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, "r") as f:
                return json.load(f)
        return []

def save_memory(mistake_log):
    with file_lock:
        memory = []
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, "r") as f:
                memory = json.load(f)
                
        memory.insert(0, mistake_log)
        memory = memory[:10]  
        
        with open(MEMORY_FILE, "w") as f:
            json.dump(memory, f, indent=4)

def log_metrics(processing_time, is_rescan, has_missing, missing_fields):
    with file_lock:
        file_exists = os.path.exists(METRICS_FILE)
        with open(METRICS_FILE, mode="a", newline="") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Timestamp", "Processing_Time_Sec", "Is_Rescan", "First_Pass_Success", "Missing_Fields"])
            
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            writer.writerow([timestamp, round(processing_time, 2), is_rescan, not has_missing and not is_rescan, ", ".join(missing_fields)])

def extract_json_from_text(text):
    """Robust JSON extractor for model outputs."""
    json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL | re.IGNORECASE)
    if json_match:
        text = json_match.group(1)
    else:
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            text = json_match.group(0)
    try:
        return json.loads(text)
    except Exception as e:
        print(f"JSON Parse Error: {e}\nRaw Output: {text}")
        return {}

def process_image_lmstudio(image_bytes):
    start_time = time.time()
    
    img = Image.open(io.BytesIO(image_bytes))
    img.thumbnail((1280, 1280)) 
    
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.2)
    sharpener = ImageEnhance.Sharpness(img)
    img = sharpener.enhance(1.2)
    
    width, height = img.size
    collage = Image.new('RGB', (width * 2, height))
    collage.paste(img, (0, 0))
    img_rotated = img.rotate(-90, expand=True)
    img_rotated.thumbnail((width, height))
    collage.paste(img_rotated, (width, 0))
    
    buffer = io.BytesIO()
    collage.save(buffer, format="JPEG", quality=85)
    img_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    memory = load_memory()
    memory_context = ""
    if memory:
        memory_context = "\nCRITICAL - LEARN FROM PAST MISTAKES:\n" + "\n".join([f"- {m}" for m in memory])
    
    system_prompt = f"""You are an expert medical OCR AI operating in a clinical environment.
{memory_context}
Suture Reference Gazetteer: Vicryl, Vicryl Rapide, Prolene, PDS II, Monocryl, Ethilon, Silk.

Analyse the image (which contains a standard view and a 90-degree rotated view to help you read vertical text).
Output ONLY a valid JSON object matching this schema. NO markdown formatting, NO extra text:
{{
  "Step1_Size_Reasoning": "Find the thread gauge (e.g., 2-0, 3-0, 4-0, 0, 1, 2). Explicitly reject thread lengths like 75cm, 45cm, 18in.",
  "Step2_Expiry_Reasoning": "Find all dates. If there are two dates (e.g. MFG and EXP), the Expiration Date is ALWAYS the later date.",
  "Brand": "string",
  "Material": "string",
  "Size": "string (thread gauge ONLY)",
  "Expiration_Date": "Format EXACTLY as YYYY-MM-DD or YYYY-MM. NO extra text."
}}"""

    try:
        response = client.chat.completions.create(
            model="local-model",
            max_tokens=400,
            temperature=0.0,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [
                    {"type": "text", "text": "Extract the suture data into JSON format according to the schema."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                ]}
            ]
        )
        output_text = response.choices[0].message.content
        ai_data = extract_json_from_text(output_text)
        
    except Exception as e:
        print(f"Error communicating with LM Studio: {e}")
        ai_data = {}
        
    processing_time = time.time() - start_time
    return ai_data, processing_time

def decrement_excel(brand, material, size, expiry):
    with file_lock:
        if not os.path.exists(EXCEL_FILE): return
        df = pd.read_excel(EXCEL_FILE)
        
        mask = (df['Brand'].astype(str).str.lower() == brand.lower()) & \
               (df['Material'].astype(str).str.lower() == material.lower()) & \
               (df['Size'].astype(str).str.lower() == size.lower()) & \
               (df['Expiration_Date'].astype(str).str.lower() == expiry.lower())
               
        if mask.any():
            if df.loc[mask, 'Count'].iloc[0] > 1:
                df.loc[mask, 'Count'] -= 1
            else:
                df = df[~mask] 
            df.to_excel(EXCEL_FILE, index=False)

def update_excel(ai_data):
    data = {k.lower().replace("_", ""): str(v) if v is not None else "Unknown" for k, v in ai_data.items()}
    def clean(v): return "Unknown" if v.lower() in ['none', 'null', 'nan', 'not visible', 'not specified'] else v
    
    brand = clean(data.get('brand', 'Unknown'))
    material = clean(data.get('material', 'Unknown'))
    size = clean(data.get('size', 'Unknown'))
    expiry = clean(data.get('expirationdate', 'Unknown'))
    
    with file_lock:
        cols = ['Brand', 'Material', 'Size', 'Expiration_Date', 'Count']
        df = pd.read_excel(EXCEL_FILE) if os.path.exists(EXCEL_FILE) else pd.DataFrame(columns=cols)
        
        mask = (df['Brand'].astype(str).str.lower() == brand.lower()) & \
               (df['Material'].astype(str).str.lower() == material.lower()) & \
               (df['Size'].astype(str).str.lower() == size.lower()) & \
               (df['Expiration_Date'].astype(str).str.lower() == expiry.lower())
               
        if mask.any():
            df.loc[mask, 'Count'] += 1
        else:
            new_row = pd.DataFrame([{'Brand': brand, 'Material': material, 'Size': size, 'Expiration_Date': expiry, 'Count': 1}])
            df = pd.concat([df, new_row], ignore_index=True)
            
        df.to_excel(EXCEL_FILE, index=False)
        
    return brand, material, size, expiry

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    with open(os.path.join(BASE_DIR, "index.html"), "r") as f: return f.read()

@app.post("/scan-suture/")
async def scan_suture(
    image: UploadFile = File(...),
    replace_last: bool = Form(False),
    last_brand: str = Form("Unknown"),
    last_material: str = Form("Unknown"),
    last_size: str = Form("Unknown"),
    last_expiry: str = Form("Unknown")
):
    contents = await image.read()
    
    if replace_last:
        decrement_excel(last_brand, last_material, last_size, last_expiry)
        
    ai_data, proc_time = await run_in_threadpool(process_image_lmstudio, contents)
    
    if ai_data:
        brand, material, size, expiry = update_excel(ai_data)
        missing_fields = [k for k, v in {"Brand": brand, "Material": material, "Size": size, "Expiration_Date": expiry}.items() if v == "Unknown"]
        
        log_metrics(proc_time, replace_last, len(missing_fields) > 0, missing_fields)
        
        return {
            "status": "success", 
            "processing_time": round(proc_time, 2),
            "has_missing": len(missing_fields) > 0,
            "data": {"Brand": brand, "Material": material, "Size": size, "Expiration_Date": expiry}
        }
        
    return {"status": "error"}

@app.post("/edit-suture/")
async def edit_suture(
    old_brand: str = Form(...), old_material: str = Form(...), old_size: str = Form(...), old_expiry: str = Form(...),
    new_brand: str = Form(...), new_material: str = Form(...), new_size: str = Form(...), new_expiry: str = Form(...)
):
    decrement_excel(old_brand, old_material, old_size, old_expiry)
    update_excel({"Brand": new_brand, "Material": new_material, "Size": new_size, "Expiration_Date": new_expiry})
    
    mistakes = []
    if old_brand != new_brand and old_brand != "Unknown": mistakes.append(f"For Brand, you previously guessed '{old_brand}'. The correct value was '{new_brand}'.")
    if old_material != new_material and old_material != "Unknown": mistakes.append(f"For Material, you previously guessed '{old_material}'. The correct value was '{new_material}'.")
    if old_size != new_size and old_size != "Unknown": mistakes.append(f"For Size, you previously guessed '{old_size}'. The correct value was '{new_size}'.")
    if old_expiry != new_expiry and old_expiry != "Unknown": mistakes.append(f"For Expiry, you previously guessed '{old_expiry}'. The correct value was '{new_expiry}'.")
    
    if mistakes:
        save_memory(" ".join(mistakes))
        
    return {
        "status": "success",
        "data": {"Brand": new_brand, "Material": new_material, "Size": new_size, "Expiration_Date": new_expiry}
    }

@app.post("/discard-suture/")
async def discard_suture(
    brand: str = Form(...), material: str = Form(...), 
    size: str = Form(...), expiry: str = Form(...)
):
    decrement_excel(brand, material, size, expiry)
    return {"status": "success"}