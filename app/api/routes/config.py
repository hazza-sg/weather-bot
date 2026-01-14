"""Configuration endpoints."""
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_session
from app.models.database_models import ConfigSetting
from app.models.api_models import ConfigResponse, ConfigUpdate
from app.config import (
    STRATEGY_CONFIG,
    POSITION_SIZING_CONFIG,
    RISK_LIMITS,
    DIVERSIFICATION_CONFIG,
)

router = APIRouter()


@router.get("", response_model=ConfigResponse)
async def get_config(
    session: AsyncSession = Depends(get_session),
) -> ConfigResponse:
    """Get current configuration."""
    # Get stored settings
    result = await session.execute(select(ConfigSetting))
    stored = {s.key: s.value for s in result.scalars().all()}

    # Merge with defaults
    strategy = {**STRATEGY_CONFIG}
    position_sizing = {**POSITION_SIZING_CONFIG}
    risk = {**RISK_LIMITS}
    diversification = {**DIVERSIFICATION_CONFIG}

    # Override with stored values
    for key, value in stored.items():
        if key.startswith("strategy."):
            strategy[key.replace("strategy.", "")] = value
        elif key.startswith("position_sizing."):
            position_sizing[key.replace("position_sizing.", "")] = value
        elif key.startswith("risk."):
            risk[key.replace("risk.", "")] = value
        elif key.startswith("diversification."):
            diversification[key.replace("diversification.", "")] = value

    return ConfigResponse(
        strategy=strategy,
        position_sizing=position_sizing,
        risk=risk,
        diversification=diversification,
        system={
            "server_port": 8741,
            "auto_start_browser": True,
            "desktop_notifications": True,
            "sound_alerts": False,
            "log_level": "INFO",
        },
    )


@router.put("")
async def update_config(
    update: ConfigUpdate,
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """Update configuration settings."""
    section = update.section
    settings = update.settings

    for key, value in settings.items():
        full_key = f"{section}.{key}"

        # Check if setting exists
        result = await session.execute(
            select(ConfigSetting).where(ConfigSetting.key == full_key)
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.value = value
        else:
            new_setting = ConfigSetting(
                key=full_key,
                value=value,
                category=section,
            )
            session.add(new_setting)

    await session.commit()

    return {
        "success": True,
        "message": f"Updated {len(settings)} settings in {section}",
    }


@router.post("/reset")
async def reset_config(
    section: str = None,
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """Reset configuration to defaults."""
    query = select(ConfigSetting)

    if section:
        query = query.where(ConfigSetting.category == section)

    result = await session.execute(query)
    settings = result.scalars().all()

    for setting in settings:
        await session.delete(setting)

    await session.commit()

    return {
        "success": True,
        "message": f"Reset {'all' if not section else section} settings to defaults",
    }
