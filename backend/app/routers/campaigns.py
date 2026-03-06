"""Campaign REST API (Phase 5.1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas.campaign import CampaignCreate, CampaignUpdate
from app.services import campaign_service

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.get("")
async def list_campaigns(
    status: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    return await campaign_service.list_campaigns(session, status=status)


@router.post("", status_code=201)
async def create_campaign(
    data: CampaignCreate,
    session: AsyncSession = Depends(get_session),
):
    campaign = await campaign_service.create_campaign(
        session, name=data.name, description=data.description,
    )
    await session.commit()
    return {
        "id": campaign.id,
        "name": campaign.name,
        "world_name": campaign.world_name,
        "description": campaign.description,
        "status": campaign.status,
        "session_count": 0,
        "created_at": campaign.created_at.isoformat() if campaign.created_at else None,
        "updated_at": campaign.updated_at.isoformat() if campaign.updated_at else None,
    }


@router.get("/{campaign_id}")
async def get_campaign(
    campaign_id: str,
    session: AsyncSession = Depends(get_session),
):
    detail = await campaign_service.get_campaign_detail(session, campaign_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return detail


@router.patch("/{campaign_id}")
async def update_campaign(
    campaign_id: str,
    data: CampaignUpdate,
    session: AsyncSession = Depends(get_session),
):
    campaign = await campaign_service.get_campaign(session, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if data.name is not None:
        campaign.name = data.name
    if data.description is not None:
        campaign.description = data.description
    if data.status is not None:
        campaign.status = data.status
    await session.commit()
    return {
        "id": campaign.id,
        "name": campaign.name,
        "world_name": campaign.world_name,
        "description": campaign.description,
        "status": campaign.status,
    }


@router.delete("/{campaign_id}", status_code=204)
async def delete_campaign(
    campaign_id: str,
    session: AsyncSession = Depends(get_session),
):
    campaign = await campaign_service.get_campaign(session, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    await session.delete(campaign)
    await session.commit()


@router.post("/{campaign_id}/continue")
async def continue_campaign(
    campaign_id: str,
    session: AsyncSession = Depends(get_session),
):
    try:
        result = await campaign_service.continue_campaign(session, campaign_id)
        await session.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
