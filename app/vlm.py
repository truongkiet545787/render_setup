import base64
import httpx
import logging
from .config import settings

logger = logging.getLogger("uvicorn.error")

def identify_food_from_image(image_bytes: bytes) -> str:
    """
    Sends the image bytes to a VLM (Gemini 2.5 Flash or Groq Llama 3.2 Vision)
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
                            "text": "Nhìn vào ảnh này và xác định tên món ăn (Việt Nam hoặc nước ngoài, đồ ăn nhanh), các loại rau củ hoa quả, các loại đồ uống, hoặc sản phẩm đóng gói (như snack, bánh kẹo) chính trong ảnh. Trả về DUY NHẤT tên gọi phổ biến nhất của sản phẩm/món ăn bằng tiếng Việt (ví dụ: 'Bánh Oreo', 'Nước ngọt Coca-Cola', 'Quả táo', 'Bún bò Huế', 'Hamburger'). Dịch thật chính xác tên các loại quả (ví dụ: Blueberry là 'Quả việt quất' hoặc 'Việt quất', KHÔNG dịch là 'Quất'). Không thêm bất kỳ từ giải thích nào khác, không có dấu chấm câu."
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
                "maxOutputTokens": 20
            }
        }
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(url, json=payload)
                if response.status_code == 200:
                    result = response.json()
                    text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
                    logger.info(f"[VLM] Gemini identified food: {text}")
                    return text
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
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Identify the main food dish (Vietnamese or international, fast food), vegetable, fruit, beverage, or packaged item (like snacks, biscuits) in this image. Return ONLY the name in Vietnamese (e.g., 'Bánh Oreo', 'Nước ngọt Coca-Cola', 'Quả táo', 'Bún bò Huế', 'Hamburger'). Ensure highly accurate translation (e.g., Blueberry is 'Việt quất' or 'Quả việt quất', NOT 'Quất'). Do not include any other explanation, text or punctuation."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
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
                with httpx.Client(timeout=10.0) as client:
                    response = client.post(url, headers=headers, json=payload)
                    if response.status_code == 200:
                        result = response.json()
                        text = result["choices"][0]["message"]["content"].strip()
                        logger.info(f"[VLM] Raw response: {repr(text)}")
                        
                        # Remove <think>...</think> blocks
                        import re
                        cleaned_text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
                        
                        # If the thinking block wasn't closed or cleaned_text is empty, split it
                        if not cleaned_text or "<think>" in text:
                            parts = text.split("</think>")
                            if len(parts) > 1 and parts[-1].strip():
                                cleaned_text = parts[-1].strip()
                            else:
                                raw_lower = text.lower()
                                foods = [
                                    "phở bò", "phở gà", "phở", "bánh mì", "bún chả", "cơm tấm", "gỏi cuốn",
                                    "bún bò huế", "bún đậu mắm tôm", "bánh bao", "bánh chưng", "bánh tét",
                                    "bánh tráng nướng", "bánh trung thu", "rau muống xào", "thịt kho tàu",
                                    "xôi xéo", "nui xào", "ốc bươu hấp", "cơm chiên", "com chien", "cơm lam", 
                                    "gà giòn", "gà rán", "khoai tây chiên", "pizza", "burger", "donut", "hot dog",
                                    "bánh oreo", "oreo", "táo", "cam", "chuối", "sữa", "coca", "pepsi", "snack", "bia"
                                ]
                                matched = None
                                for food in foods:
                                    if food in raw_lower:
                                        matched = food
                                        break
                                
                                if matched:
                                    cleaned_text = matched.title()
                                else:
                                    cleaned_text = "Phở bò"
                        
                        # Clean up quotes
                        cleaned_text = cleaned_text.replace('"', '').replace("'", "")
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

