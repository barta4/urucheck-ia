import logging
from fastapi import APIRouter, Depends, HTTPException
from database import database
from auth import get_current_user
from pydantic import BaseModel
import httpx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


class PushTokenRequest(BaseModel):
    token: str


@router.put("/push-token")
async def update_push_token(data: PushTokenRequest, current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    await database.execute(
        "UPDATE employees SET expo_push_token = :token WHERE id = :id AND company_id = :cid",
        {"token": data.token, "id": user_id, "cid": current_user.get("company_id")}
    )
    return {"message": "Push token updated successfully"}


async def send_push_notification(to: str, title: str, body: str, data: dict = None) -> bool:
    """
    Sends a push notification via Expo's push service.

    Args:
        to: Expo push token (must start with 'ExponentPushToken').
        title: Notification title.
        body: Notification body text.
        data: Optional extra data payload.

    Returns:
        True if the notification was sent successfully, False otherwise.
    """
    if not to or not to.startswith("ExponentPushToken"):
        logger.warning("Invalid Expo Push Token (skipped): %s", to[:20] if to else "None")
        return False

    payload = {
        "to": to,
        "title": title,
        "body": body,
        "sound": "default",
    }
    if data:
        payload["data"] = data

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "https://exp.host/--/api/v2/push/send",
                json=payload,
                timeout=5.0,
            )
            if response.status_code == 200:
                logger.info("Push notification sent: %s", title)
                return True
            else:
                logger.warning("Push notification failed (HTTP %s): %s", response.status_code, response.text[:200])
                return False
        except Exception as exc:
            logger.error("Exception sending push notification: %s", exc)
            return False
