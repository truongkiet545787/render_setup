import base64
import httpx
import logging
import re
from .config import settings

logger = logging.getLogger("uvicorn.error")

def extract_food_name_from_vlm_text(text: str) -> str:
    """
    Robustly extracts the concise Vietnamese food name from VLM output,
    handling <think> reasoning blocks, markdown quotes, and unclosed thinking loops.
    """
    if not text:
        return "Món ăn"

    # 1. If thinking block is properly closed with </think>, use the final conclusion
    if "</think>" in text:
        parts = text.split("</think>")
        if len(parts) > 1 and parts[-1].strip():
            ans = parts[-1].strip()
            ans = re.sub(r"^[\*\-\#\>\s]+", "", ans)
            ans = ans.replace('"', '').replace("'", "").strip()
            # If conclusion is clean and concise
            if ans and len(ans) <= 60 and not ans.lower().startswith("the "):
                return ans

    # 2. Extract explicit conclusion markers from within the text
    patterns = [
        r'Vietnamese name:\s*[\"\'\*]*([^\"\'\n\r\*]+)',
        r'Vietnamese product name[^:]*:\s*[\"\'\*]*([^\"\'\n\r\*]+)',
        r'Tên món ăn:\s*[\"\'\*]*([^\"\'\n\r\*]+)',
        r'Tên sản phẩm:\s*[\"\'\*]*([^\"\'\n\r\*]+)',
        r'main product name is\s*[\"\'\*]*([^\"\'\n\r\*]+)',
        r'The text says\s*[\"\'\*]+([^\"\'\n\r\*]+)[\"\'\*]+',
        r'Translates to\s*[\"\'\*]+([^\"\'\n\r\*]+)[\"\'\*]+',
    ]

    stop_words = ["vinamilk", "most", "the", "logo", "brand", "packaging", "beverage", "snack", "image", "food"]

    for pattern in patterns:
        matches = re.finditer(pattern, text, flags=re.IGNORECASE)
        for m in matches:
            cand = m.group(1).strip().replace('"', '').replace("'", "").strip()
            cand = re.split(r'[\.\,\(\;\:]', cand)[0].strip()
            if len(cand) >= 2 and cand.lower() not in stop_words and not cand.lower().startswith("the "):
                return cand

    # 3. Quoted search in earlier section of text for Vietnamese phrases
    quotes = re.findall(r'["\']([^"\']{2,40})["\']', text)
    vietnamese_chars = "àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ"
    for q in quotes:
        cand = q.strip()
        if any(c in cand.lower() for c in vietnamese_chars) and cand.lower() not in stop_words:
            return cand

    # 4. Fallback: clean lines
    lines = [l.strip().lstrip("*- ").strip() for l in text.split("\n") if l.strip()]
    for line in lines:
        if 2 <= len(line) <= 50 and not line.startswith("<") and not line.lower().startswith("let") and not line.lower().startswith("the") and line.lower() not in stop_words:
            return line

    return "Thực phẩm"

def identify_food_from_image(image_bytes: bytes) -> str:
    """
    Sends the image bytes to a VLM (Gemini or Groq Qwen Vision)
    to identify the food item name.
    """
    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    
    # 1. Try Gemini if API key is present
    if settings.gemini_api_key and settings.gemini_api_key != "your_gemini_api_key_here":
        logger.info("[VLM] Using Gemini API for image recognition...")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={settings.gemini_api_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": "Nhìn vào ảnh này và xác định tên món ăn (Việt Nam hoặc nước ngoài), đồ uống, hoa quả, hoặc bao bì thực phẩm chính trong ảnh. Trả về DUY NHẤT tên gọi phổ biến nhất bằng tiếng Việt (ví dụ: 'Thạch trái cây', 'Bánh mì', 'Phở bò', 'Nước ngọt 7Up'). Không thêm bất kỳ từ giải thích nào khác."
                        },
                        {
                            "inlineData": {
                                "mimeType": "image/jpeg",
                                "data": base64_image
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 30
            }
        }
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(url, json=payload)
                if response.status_code == 200:
                    result = response.json()
                    text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
                    logger.info(f"[VLM] Gemini identified food: {text}")
                    return extract_food_name_from_vlm_text(text)
                else:
                    logger.error(f"[VLM] Gemini API error: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"[VLM] Gemini API call failed: {e}")

    # 2. Fallback to Groq Vision with Key Rotation
    from .groq_pool import groq_pool
    groq_keys = groq_pool.get_ordered_keys()

    if groq_keys:
        url = "https://api.groq.com/openai/v1/chat/completions"
        payload = {
            "model": "qwen/qwen3.6-27b",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a Vietnamese food and grocery recognition expert. Output ONLY the concise Vietnamese name of the food, beverage, snack, fruit, or packaged grocery item in the image (1 to 4 words, e.g., 'Thạch trái cây', 'Bánh mì', 'Phở bò', 'Sữa chua'). Do NOT output reasoning or explanations."
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Identify the main food, drink, or packaged grocery product in this image. What is its exact Vietnamese name?"
                        },
                        {
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            },
                            "type": "image_url"
                        }
                    ]
                }
            ],
            "temperature": 0.1,
            "max_tokens": 1024
        }

        for attempt_idx, current_key in enumerate(groq_keys):
            headers = {
                "Authorization": f"Bearer {current_key}",
                "Content-Type": "application/json"
            }
            logger.info(f"[VLM] Trying Groq Vision (Key #{attempt_idx + 1} / {len(groq_keys)})...")

            try:
                with httpx.Client(timeout=30.0) as client:
                    response = client.post(url, headers=headers, json=payload)
                    if response.status_code == 200:
                        result = response.json()
                        text = result["choices"][0]["message"]["content"].strip()
                        logger.info(f"[VLM] Raw response: {repr(text)}")
                        
                        cleaned_text = extract_food_name_from_vlm_text(text)
                        logger.info(f"[VLM] Groq identified food: {cleaned_text}")
                        return cleaned_text
                    elif response.status_code in (429, 401, 503):
                        logger.warning(f"[VLM] Groq key #{attempt_idx + 1} rate-limited or error ({response.status_code}). Rotating to next key...")
                        continue
                    else:
                        logger.error(f"[VLM] Groq API error ({response.status_code}): {response.text}")
            except Exception as e:
                logger.error(f"[VLM] Groq API call failed on key #{attempt_idx + 1}: {e}")

    # 3. Raise error if no API key is available or both failed
    raise Exception("No active VLM provider configured or all providers/keys failed.")


