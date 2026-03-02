from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.setting import Setting

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    settings: dict[str, str]


@router.get("")
async def get_settings(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Setting))
    settings_list = result.scalars().all()
    return {s.key: s.value for s in settings_list}


@router.put("")
async def update_settings(
    data: SettingsUpdate,
    session: AsyncSession = Depends(get_session),
):
    for key, value in data.settings.items():
        result = await session.execute(select(Setting).where(Setting.key == key))
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = value
        else:
            session.add(Setting(key=key, value=value))

    await session.commit()
    return {"status": "ok"}
