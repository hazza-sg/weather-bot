"""Alert and notification endpoints."""
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.alert_manager import (
    get_alert_manager,
    AlertLevel,
    AlertCategory,
)

router = APIRouter()


class AlertResponse(BaseModel):
    """Alert response model."""
    id: str
    level: str
    category: str
    title: str
    message: str
    timestamp: str
    data: Optional[Dict[str, Any]] = None
    read: bool
    dismissed: bool


class AlertListResponse(BaseModel):
    """List of alerts response."""
    alerts: List[AlertResponse]
    unread_count: int
    total_count: int


class AlertPreferencesUpdate(BaseModel):
    """Alert preferences update model."""
    enabled: Optional[bool] = None
    desktop_notifications: Optional[bool] = None
    sound_enabled: Optional[bool] = None
    trade_alerts: Optional[bool] = None
    risk_alerts: Optional[bool] = None
    system_alerts: Optional[bool] = None
    market_alerts: Optional[bool] = None
    position_alerts: Optional[bool] = None
    min_edge_for_alert: Optional[float] = None
    pnl_alert_threshold: Optional[float] = None
    position_alert_threshold: Optional[float] = None


class ActivityLogResponse(BaseModel):
    """Activity log entry response."""
    id: str
    action: str
    description: str
    timestamp: str
    category: str
    metadata: Optional[Dict[str, Any]] = None


@router.get("", response_model=AlertListResponse)
async def get_alerts(
    limit: int = Query(50, ge=1, le=200),
    unread_only: bool = Query(False),
    category: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
) -> AlertListResponse:
    """Get alerts with optional filtering."""
    manager = get_alert_manager()

    # Parse category and level if provided
    cat = None
    if category:
        try:
            cat = AlertCategory(category)
        except ValueError:
            pass

    lvl = None
    if level:
        try:
            lvl = AlertLevel(level)
        except ValueError:
            pass

    alerts = manager.get_alerts(
        limit=limit,
        unread_only=unread_only,
        category=cat,
        level=lvl,
    )

    return AlertListResponse(
        alerts=[AlertResponse(**a.to_dict()) for a in alerts],
        unread_count=manager.get_unread_count(),
        total_count=len(manager._alerts),
    )


@router.get("/preferences")
async def get_alert_preferences() -> Dict[str, Any]:
    """Get alert preferences."""
    manager = get_alert_manager()
    return manager.get_preferences().to_dict()


@router.put("/preferences")
async def update_alert_preferences(
    updates: AlertPreferencesUpdate,
) -> Dict[str, Any]:
    """Update alert preferences."""
    manager = get_alert_manager()

    # Convert to dict, excluding None values
    update_dict = {k: v for k, v in updates.dict().items() if v is not None}

    manager.update_preferences(update_dict)

    return {
        "success": True,
        "message": f"Updated {len(update_dict)} preferences",
        "preferences": manager.get_preferences().to_dict(),
    }


@router.post("/{alert_id}/read")
async def mark_alert_read(alert_id: str) -> Dict[str, Any]:
    """Mark an alert as read."""
    manager = get_alert_manager()

    if manager.mark_read(alert_id):
        return {"success": True, "message": "Alert marked as read"}

    raise HTTPException(status_code=404, detail="Alert not found")


@router.post("/read-all")
async def mark_all_alerts_read() -> Dict[str, Any]:
    """Mark all alerts as read."""
    manager = get_alert_manager()
    count = manager.mark_all_read()

    return {
        "success": True,
        "message": f"Marked {count} alerts as read",
    }


@router.post("/{alert_id}/dismiss")
async def dismiss_alert(alert_id: str) -> Dict[str, Any]:
    """Dismiss an alert."""
    manager = get_alert_manager()

    if manager.dismiss_alert(alert_id):
        return {"success": True, "message": "Alert dismissed"}

    raise HTTPException(status_code=404, detail="Alert not found")


@router.delete("")
async def clear_alerts(
    older_than_hours: int = Query(0, ge=0),
) -> Dict[str, Any]:
    """Clear alerts."""
    manager = get_alert_manager()
    count = manager.clear_alerts(older_than_hours)

    return {
        "success": True,
        "message": f"Cleared {count} alerts",
    }


@router.get("/activity", response_model=List[ActivityLogResponse])
async def get_activity_log(
    limit: int = Query(100, ge=1, le=500),
    category: Optional[str] = Query(None),
) -> List[ActivityLogResponse]:
    """Get activity log."""
    manager = get_alert_manager()
    entries = manager.get_activity_log(limit=limit, category=category)

    return [ActivityLogResponse(**e.to_dict()) for e in entries]


@router.delete("/activity")
async def clear_activity_log() -> Dict[str, Any]:
    """Clear activity log."""
    manager = get_alert_manager()
    count = manager.clear_activity_log()

    return {
        "success": True,
        "message": f"Cleared {count} activity log entries",
    }


@router.post("/test")
async def create_test_alert(
    level: str = Query("info"),
    title: str = Query("Test Alert"),
    message: str = Query("This is a test alert"),
) -> Dict[str, Any]:
    """Create a test alert (for debugging)."""
    manager = get_alert_manager()

    try:
        alert_level = AlertLevel(level)
    except ValueError:
        alert_level = AlertLevel.INFO

    alert = await manager.create_alert(
        level=alert_level,
        category=AlertCategory.SYSTEM,
        title=title,
        message=message,
    )

    if alert:
        return {
            "success": True,
            "alert": alert.to_dict(),
        }

    return {
        "success": False,
        "message": "Alert not created (may be disabled)",
    }
