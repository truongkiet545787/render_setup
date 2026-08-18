from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional, List
import logging

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from ..database import get_db
from .. import models, schemas
from ..config import settings

logger = logging.getLogger("uvicorn.error")
router = APIRouter(
    prefix="/chat",
    tags=["Chatbot"]
)

from ..groq_pool import groq_pool

def get_llm(api_key: Optional[str] = None):
    key = api_key or groq_pool.get_next_key()
    if not key:
        return None
    try:
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=settings.groq_model or "openai/gpt-oss-120b",
            groq_api_key=key,
            temperature=0.7
        )
    except Exception as e:
        logger.error(f"Failed to initialize Groq LLM for chat: {e}")
        return None

def invoke_llm_with_fallback(messages) -> str:
    """Invokes ChatGroq with automatic key rotation on rate limits / errors."""
    groq_keys = groq_pool.get_ordered_keys()
    if not groq_keys:
        raise Exception("No valid Groq API keys available.")
    
    last_error = None
    for attempt_idx, key in enumerate(groq_keys):
        try:
            logger.info(f"[Chat] Invoking Groq (Key #{attempt_idx + 1} / {len(groq_keys)})...")
            llm = get_llm(key)
            if not llm:
                continue
            response = llm.invoke(messages)
            return response.content.strip()
        except Exception as e:
            last_error = e
            logger.warning(f"[Chat] Groq key #{attempt_idx + 1} error: {e}. Rotating to next key...")
            continue
    raise last_error or Exception("All Groq keys failed.")

@router.post("", response_model=schemas.ChatResponse)
def chat_with_assistant(payload: schemas.ChatRequest, db: Session = Depends(get_db)):
    llm = get_llm()
    if not llm:
        # Fallback response if Groq is not configured
        fallback_reply = f"[Offline Demo] Chào bạn! Cảm ơn câu hỏi '{payload.message}'. Để trò chuyện thực tế cùng AI, vui lòng nhập GROQ_API_KEY vào file .env."
        
        # Save user message
        user_msg = models.ChatMessage(session_id=payload.session_id, role="user", content=payload.message)
        db.add(user_msg)
        db.commit()
        
        # Save AI reply
        ai_msg = models.ChatMessage(session_id=payload.session_id, role="assistant", content=fallback_reply)
        db.add(ai_msg)
        db.commit()
        
        # Retrieve history
        history = db.query(models.ChatMessage).filter(models.ChatMessage.session_id == payload.session_id).order_by(models.ChatMessage.time_created.asc()).all()
        return schemas.ChatResponse(
            reply=fallback_reply,
            history=[schemas.ChatMessageResponse.model_validate(h) for h in history]
        )

    # 1. Fetch Chat History from PostgreSQL
    db_history = db.query(models.ChatMessage).filter(
        models.ChatMessage.session_id == payload.session_id
    ).order_by(models.ChatMessage.time_created.asc()).all()

    # 2. Build LangChain Messages list
    messages = []
    
    # 2a. Construct System Message (Base Persona)
    system_instruction = (
        "Bạn là trợ lý dinh dưỡng AI (AI Assistant) thân thiện, chuyên nghiệp cho ứng dụng di động AR.\n"
        "Nhiệm vụ của bạn là giải đáp thắc mắc về sức khỏe, thực phẩm và dinh dưỡng cho người dùng.\n"
        "Hãy viết câu trả lời ngắn gọn, trực quan, dễ đọc trên màn hình điện thoại (khoảng 2-4 câu, chia dòng rõ ràng nếu cần).\n"
        "Luôn trả lời bằng Tiếng Việt với giọng điệu thân thiện, khuyến khích."
    )

    # 2b. Append active product context if present
    if payload.product_name:
        product_name_lower = payload.product_name.strip().lower()
        # Query product info
        product = db.query(models.Product).filter(models.Product.name == product_name_lower).first()
        if product:
            nutrition = product.nutrition
            nutr_info = ""
            if nutrition:
                nutr_info = (
                    f"Calories: {nutrition.calories} kcal, "
                    f"Carbohydrates: {nutrition.carbohydrate}g (Đường: {nutrition.sugar}g), "
                    f"Protein: {nutrition.protein}g, "
                    f"Chất béo: {nutrition.fat}g, "
                    f"Chất xơ: {nutrition.fiber}g, "
                    f"Kali: {nutrition.potassium}mg, "
                    f"Vitamin C: {nutrition.vitamin_c}mg."
                )
            
            ingredients = ", ".join([i.name for i in product.ingredients]) if product.ingredients else "không rõ"
            allergens = ", ".join([a.name for a in product.allergens]) if product.allergens else "không có"
            brand_str = product.brand if product.brand else "Không có thương hiệu"

            product_context_prompt = (
                f"\n\n[Ngữ cảnh hiện tại]: Người dùng vừa quét hoặc đang xem thông tin món ăn: **{product.name.upper()}**.\n"
                f"Thông số dinh dưỡng trên 100g: {nutr_info}\n"
                f"Thương hiệu: {brand_str}. Thành phần nguyên liệu: {ingredients}.\n"
                f"Chất dễ gây dị ứng: {allergens}.\n"
                f"Khi người dùng nói các từ đại từ chỉ định như 'món này', 'sản phẩm này', 'nó', 'loại này', "
                f"hãy tự hiểu và trả lời dựa trên thông số của món **{product.name}**."
            )
            system_instruction += product_context_prompt

    messages.append(SystemMessage(content=system_instruction))

    # 2c. Add DB History to Messages list
    for msg in db_history:
        if msg.role == "user":
            messages.append(HumanMessage(content=msg.content))
        else:
            messages.append(AIMessage(content=msg.content))

    # 2d. Add current message
    messages.append(HumanMessage(content=payload.message))

    # 3. Call LLM with rotation
    try:
        ai_reply = invoke_llm_with_fallback(messages)

        # 4. Save messages to Database
        user_message_record = models.ChatMessage(
            session_id=payload.session_id,
            role="user",
            content=payload.message
        )
        ai_message_record = models.ChatMessage(
            session_id=payload.session_id,
            role="assistant",
            content=ai_reply
        )
        db.add(user_message_record)
        db.add(ai_message_record)
        db.commit()

        # 5. Fetch updated history to return
        updated_history = db.query(models.ChatMessage).filter(
            models.ChatMessage.session_id == payload.session_id
        ).order_by(models.ChatMessage.time_created.asc()).all()

        return schemas.ChatResponse(
            reply=ai_reply,
            history=[schemas.ChatMessageResponse.model_validate(h) for h in updated_history]
        )
    except Exception as e:
        logger.error(f"Error calling LLM or saving to database: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing chat: {str(e)}"
        )
