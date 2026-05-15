# backend/chat/router.py
"""
Sarvam AI Chat Router - Integrated into main backend
"""

from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from openai import OpenAI
import os
import time
import logging

# Load environment variables
load_dotenv()

# Setup logging
logger = logging.getLogger(__name__)

# Get API key
raw_key = os.getenv("SARVAM_API_KEY")
if raw_key:
    SARVAM_API_KEY = raw_key.strip().strip('"').strip("'")
    logger.info("SARVAM_API_KEY found")
else:
    SARVAM_API_KEY = None
    logger.warning("SARVAM_API_KEY not set")

# Initialize Sarvam client
try:
    client = OpenAI(api_key=SARVAM_API_KEY, base_url="https://api.sarvam.ai/v1") if SARVAM_API_KEY else None
    logger.info("Initialized Sarvam AI client")
except Exception as e:
    logger.exception(f"Failed to initialize Sarvam client: {e}")
    client = None

# Create router
router = APIRouter(prefix="/chat", tags=["Chat AI Assistant"])

# System prompts
SYSTEM_PROMPTS = {
    "en": """You are an agricultural assistant for coconut farming. 
    Answer farmers' questions about coconut crops, soil, disease, pests, and weather in clear, concise English. 
    Provide practical and easy-to-follow guidance.""",

    "kn": """ನೀವು ತೆಂಗಿನಕಾಯಿ ಕೃಷಿಗಾಗಿ ಕೃಷಿ ಸಹಾಯಕರು. ತೆಂಗಿನಕಾಯಿ ಬೆಳೆಗಳು, ಮಣ್ಣು, ರೋಗ, ಕೀಟಗಳು ಮತ್ತು ಹವಾಮಾನ ಕುರಿತ ಪ್ರಶ್ನೆಗಳಿಗೆ 
    ಸರಳ, ಸ್ಪಷ್ಟ ಮತ್ತು ಸಹಾಯಕ ಉತ್ತರಗಳನ್ನು ಕನ್ನಡದಲ್ಲಿ ನೀಡಿ."""
}


@router.get("/health")
async def chat_health():
    """Health check for chat service"""
    return JSONResponse(content={
        "status": "healthy",
        "sarvam_api_key_present": bool(SARVAM_API_KEY),
        "client_initialized": bool(client)
    })


@router.post("/llm")
async def generate_response(prompt: str = Form(...), lang: str = Form("en")):
    """
    Generate AI chat response using Sarvam AI
    
    Args:
        prompt: User question/message
        lang: Language code (en or kn)
    
    Returns:
        AI generated response
    """
    try:
        if client is None:
            raise HTTPException(
                status_code=503,
                detail="Sarvam AI service not available. API key not configured."
            )

        system_prompt = SYSTEM_PROMPTS.get(lang.lower(), SYSTEM_PROMPTS["en"])

        # Retry logic for API calls
        retries = 2
        for attempt in range(retries):
            try:
                response = client.chat.completions.create(
                    model="sarvam-m",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ]
                )
                ai_response = response.choices[0].message.content
                
                logger.info(f"Chat response generated for prompt: {prompt[:50]}...")
                
                return JSONResponse(content={
                    "response": ai_response,
                    "language": lang
                })
                
            except Exception as inner_e:
                logger.exception(f"Sarvam API call failed (attempt {attempt + 1}): {inner_e}")
                if attempt < retries - 1:
                    time.sleep(1)
                    continue
                raise inner_e

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Chat service error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Chat service error: {str(e)}"
        )


@router.get("/history")
async def get_chat_history():
    """Get chat history (placeholder for future implementation)"""
    return JSONResponse(content={
        "history": [],
        "message": "Chat history feature coming soon"
    })
