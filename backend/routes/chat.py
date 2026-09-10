"""
backend/routes/chat.py

REST API endpoint for the SocialIQ Grounded AI Chat Assistant.
Handles conversational inquiries about the dashboard and platform analytics.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from backend.schemas import ChatRequest, ChatResponse
from backend.services.ai_chat_service import process_chat_message
from backend.services.ai_model_manager import get_model_status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["ai_chat"])


@router.post("/message", response_model=ChatResponse)
def send_chat_message(req: ChatRequest) -> ChatResponse:
    """Process a user query using controlled SocialIQ analytics tools and grounded RAG knowledge."""
    return process_chat_message(req)


@router.get("/status")
def get_ai_status():
    """Return local AI model and inference engine readiness."""
    return get_model_status()
