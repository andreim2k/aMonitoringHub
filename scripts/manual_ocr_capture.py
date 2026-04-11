#!/usr/bin/env python3
import requests
import json
import os
import base64
import time
import hashlib
from datetime import datetime

# Load environment variables from backend/.env
env_path = os.path.join(os.path.dirname(__file__), '..', 'backend', '.env')
if os.path.exists(env_path):
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

# Load config from backend/config.json
config_path = os.path.join(os.path.dirname(__file__), '..', 'backend', 'config.json')
with open(config_path, 'r') as f:
    config = json.load(f)

webcam_url = config.get('webcam', {}).get('url', 'http://192.168.50.3/snapshot')
requesty_config = config['ocr']['engines']['requesty']
api_key = os.environ.get('REQUESTY_API_KEY')
model = requesty_config.get('model', 'google/gemini-2.5-flash-lite')
base_url = requesty_config.get('base_url', 'https://router.requesty.ai/v1')
prompt = requesty_config.get('prompt', 'Extract only the numbers from this image.')

print(f"📸 Step 1: Capturing snapshot from {webcam_url}...")

# Prepare the exact payload as used in backend/app.py
payload = {
    "resolution": "UXGA",
    "flash": True,
    "brightness": 0,
    "contrast": 0,
    "saturation": 0,
    "exposure": 300,
    "gain": 8,
    "special_effect": 1,
    "wb_mode": 0,
    "hmirror": False,
    "vflip": False,
    "timestamp": datetime.now().astimezone().isoformat(),
    "api_endpoint": webcam_url,
    "method": "POST",
    "content_type": "application/json"
}

try:
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'image/jpeg',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
        'Connection': 'close'
    }
    response = requests.post(webcam_url, json=payload, headers=headers, timeout=20)
    response.raise_for_status()

    image_data = response.content
    md5 = hashlib.md5(image_data).hexdigest()
    image_base64 = base64.b64encode(image_data).decode('utf-8')
    
    # Save image for inspection
    with open('manual_snapshot.jpg', 'wb') as f:
        f.write(image_data)

    print(f"✅ Snapshot captured! Size: {len(image_data)//1024}KB, MD5: {md5}")
    print(f"   Saved to: manual_snapshot.jpg")

except Exception as e:
    print(f"❌ Failed to capture: {e}")
    exit(1)

print(f"\n🚀 Step 2: Sending to Gemini OCR...")
print(f"   Model: {model}")

# Prepare OCR request
ocr_payload = {
    "model": model,
    "messages": [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
            ]
        }
    ],
    "max_tokens": 100
}

try:
    ocr_response = requests.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=ocr_payload,
        timeout=30
    )
    ocr_response.raise_for_status()

    result = ocr_response.json()
    ocr_text = result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()

    print(f"\n✅ OCR Response:")
    print(f"   Result: {ocr_text}")

except requests.exceptions.RequestException as e:
    print(f"\n❌ OCR Request failed: {e}")
    try:
        print(f"   Response: {ocr_response.text}")
    except:
        pass
    exit(1)
