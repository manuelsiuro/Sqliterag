from __future__ import annotations

import pypdf
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.database import get_session
from app.dependencies import get_chat_service
from app.exceptions import NotFoundError
from app.models.conversation import Conversation
from app.schemas.message import MessageCreate
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/{conversation_id}")
async def chat(
    conversation_id: str,
    data: MessageCreate,
    session: AsyncSession = Depends(get_session),
    chat_service: ChatService = Depends(get_chat_service),
):
    # Verify conversation exists
    result = await session.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = result.scalar_one_or_none()
    if not conv:
        raise NotFoundError("Conversation", conversation_id)

    # Build options dict from parameters, excluding None values
    options = {}
    if data.parameters:
        opts = {k: v for k, v in data.parameters.model_dump().items() if v is not None}
        if opts:
            options = opts
            
    if data.images:
        options["images"] = data.images

    async def event_generator():
        async for event in chat_service.stream_chat(
            session=session,
            conversation_id=conversation_id,
            model=conv.model,
            user_message=data.message,
            options=options,
        ):
            yield event

    return EventSourceResponse(event_generator(), media_type="text/event-stream")


@router.post("/extract-pdf")
async def extract_pdf(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    try:
        reader = pypdf.PdfReader(file.file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return {"text": text.strip()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {str(e)}")
