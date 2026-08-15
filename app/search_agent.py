import json
import httpx
import logging
from .config import settings

logger = logging.getLogger("uvicorn.error")

def search_tavily(query: str) -> str:
    """
    Queries Tavily Search API for food nutritional info.
    """
    if not settings.tavily_api_key or settings.tavily_api_key == "your_tavily_api_key_here":
        logger.warning("[Search] Tavily API key is missing. Skipping web search...")
        return ""
    
    url = "https://api.tavily.com/search"
    payload = {
        "api_key": settings.tavily_api_key,
        "query": query,
        "search_depth": "basic",
        "include_answer": True,
        "max_results": 3
    }
    
    try:
        with httpx.Client(timeout=8.0) as client:
            response = client.post(url, json=payload)
            if response.status_code == 200:
                result = response.json()
                logger.info(f"[Search] Tavily search completed for query: {query}")
                
                # Combine raw results and the synthesized answer
                search_data = []
                if "answer" in result and result["answer"]:
                    search_data.append(f"Synthesized Answer: {result['answer']}")
                
                for idx, res in enumerate(result.get("results", [])):
                    search_data.append(f"Result {idx+1}: {res.get('title')} - {res.get('content')}")
                
                return "\n".join(search_data)
            else:
                logger.error(f"[Search] Tavily API error: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"[Search] Tavily API call failed: {e}")
    return ""

def call_llm_json(prompt: str, system_instruction: str) -> dict:
    """
    Calls Gemini or Groq to extract structured JSON data.
    """
    # 1. Try Gemini
    if settings.gemini_api_key and settings.gemini_api_key != "your_gemini_api_key_here":
        logger.info("[Search LLM] Calling Gemini API for structured extraction...")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={settings.gemini_api_key}"
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"{system_instruction}\n\nInput Context:\n{prompt}"}]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json"
            }
        }
        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.post(url, json=payload)
                if response.status_code == 200:
                    res_json = response.json()
                    raw_text = res_json["candidates"][0]["content"]["parts"][0]["text"].strip()
                    return json.loads(raw_text)
                else:
                    logger.error(f"[Search LLM] Gemini extraction failed: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"[Search LLM] Gemini call failed: {e}")

    # 2. Try Groq with Key Rotation
    from .groq_pool import groq_pool
    groq_keys = groq_pool.get_ordered_keys()

    if groq_keys:
        url = "https://api.groq.com/openai/v1/chat/completions"
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"}
        }

        for attempt_idx, current_key in enumerate(groq_keys):
            headers = {
                "Authorization": f"Bearer {current_key}",
                "Content-Type": "application/json"
            }
            logger.info(f"[Search LLM] Calling Groq API (Key #{attempt_idx + 1} / {len(groq_keys)})...")
            try:
                with httpx.Client(timeout=15.0) as client:
                    response = client.post(url, headers=headers, json=payload)
                    if response.status_code == 200:
                        res_json = response.json()
                        raw_text = res_json["choices"][0]["message"]["content"].strip()
                        return json.loads(raw_text)
                    elif response.status_code in (429, 401, 503):
                        logger.warning(f"[Search LLM] Groq key #{attempt_idx + 1} rate-limited or error ({response.status_code}). Rotating to next key...")
                        continue
                    else:
                        logger.error(f"[Search LLM] Groq extraction error ({response.status_code}): {response.text}")
            except Exception as e:
                logger.error(f"[Search LLM] Groq call failed on key #{attempt_idx + 1}: {e}")
            
    raise Exception("No active LLM provider configured or all providers/keys failed for extraction.")

def query_nutrition_for_food(food_name: str) -> dict:
    """
    Agent Search function: queries Tavily for nutritional info of a food item,
    then uses LLM to parse and return structured JSON nutrition details.
    """
    search_query = f"thông tin dinh dưỡng bảng calo protein carbohydrate fat sugar chất xơ nguyên liệu dị ứng của món ăn {food_name} 100g"
    search_results = search_tavily(search_query)
    
    if search_results:
        prompt = f"Food item: {food_name}\n\nSearch Results Context:\n{search_results}"
    else:
        prompt = f"Food item: {food_name}\n\n(No web search context available. Use your internal knowledge base to estimate nutrition details.)"
        
    system_instruction = (
        "Bạn là chuyên gia dinh dưỡng và khoa học thực phẩm.\n"
        "Dựa trên các kết quả tìm kiếm web (hoặc dựa trên kiến thức sâu rộng của bạn nếu không có kết quả tìm kiếm), "
        "hãy phân tích và trả về thông tin dinh dưỡng trung bình trên 100g của món ăn được yêu cầu.\n"
        "Yêu cầu bắt buộc trả về định dạng JSON duy nhất, khớp chính xác cấu trúc dưới đây:\n"
        "{\n"
        "  \"calories\": <float, lượng calo tính bằng kcal>,\n"
        "  \"protein\": <float, lượng đạm tính bằng g>,\n"
        "  \"fat\": <float, lượng chất béo tính bằng g>,\n"
        "  \"carbohydrate\": <float, lượng tinh bột tính bằng g>,\n"
        "  \"sugar\": <float, lượng đường tính bằng g>,\n"
        "  \"fiber\": <float, lượng chất xơ tính bằng g>,\n"
        "  \"potassium\": <float, lượng kali tính bằng mg, mặc định 100.0 nếu không có>,\n"
        "  \"vitamin_c\": <float, lượng vitamin C tính bằng mg, mặc định 0.0 nếu không có>,\n"
        "  \"brand\": <string hoặc null, thương hiệu sản phẩm nếu có>,\n"
        "  \"ingredients\": [<danh sách chuỗi tên các nguyên liệu chính, ví dụ: 'Thịt heo', 'Đường'>],\n"
        "  \"allergens\": [<danh sách chuỗi chất dễ gây dị ứng nếu có, ví dụ: 'Gluten', 'Sữa'>]\n"
        "}\n"
        "Lưu ý: Chỉ trả về chuỗi JSON hợp lệ, không bọc trong ```json ... ```, không có văn bản giải thích thừa."
    )
    
    try:
        extracted_data = call_llm_json(prompt, system_instruction)
        logger.info(f"[Search Agent] Successfully extracted nutrition data for {food_name}: {extracted_data}")
        return extracted_data
    except Exception as e:
        logger.error(f"[Search Agent] Failed to run search agent: {e}")
        # Return fallback default values
        return {
            "calories": 150.0,
            "protein": 5.0,
            "fat": 5.0,
            "carbohydrate": 20.0,
            "sugar": 2.0,
            "fiber": 1.0,
            "potassium": 100.0,
            "vitamin_c": 0.0,
            "brand": None,
            "ingredients": ["Thành phần cơ bản"],
            "allergens": []
        }
