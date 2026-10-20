import logging
from fastapi import APIRouter, Depends, HTTPException
from database import database
from auth import get_current_user
from pydantic import BaseModel
import httpx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])

_EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
_EXPO_BATCH_SIZE = 100
# Expo ticket errors meaning the token is permanently unusable — the device
# uninstalled the app or the registration is invalid. Safe to purge.
_DEAD_TOKEN_ERRORS = {"DeviceNotRegistered", "InvalidRegistration"}


class PushTokenRequest(BaseModel):
    token: str


@router.put("/push-token")
async def update_push_token(data: PushTokenRequest, current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # expo_push_token column is VARCHAR(255) — validate format/length to
    # avoid raw 500s and junk values.
    token = (data.token or "").strip()
    if not token.startswith("ExponentPushToken") or not (10 <= len(token) <= 255):
        raise HTTPException(status_code=400, detail="Token de notificaciones inválido.")

    await database.execute(
        "UPDATE employees SET expo_push_token = :token WHERE id = :id AND company_id = :cid",
        {"token": token, "id": user_id, "cid": current_user.get("company_id")}
    )
    return {"message": "Push token updated successfully"}


def extract_dead_tickets(messages, tickets):
    """
    Parse an Expo push API response into (dead_tokens, ok_count, failed_count).

    Expo returns HTTP 200 even when individual messages fail — the per-ticket
    status must be inspected. "error" tickets with DeviceNotRegistered /
    InvalidRegistration mean the token is dead and should be purged.
    Pure function (unit tested).
    """
    dead_tokens = []
    ok = 0
    failed = 0
    for msg, ticket in zip(messages, tickets):
        if not isinstance(ticket, dict):
            failed += 1
            continue
        if ticket.get("status") == "ok":
            ok += 1
            continue
        failed += 1
        details = ticket.get("details") or {}
        if details.get("error") in _DEAD_TOKEN_ERRORS:
            to = msg.get("to") if isinstance(msg, dict) else None
            if to:
                dead_tokens.append(to)
    return dead_tokens, ok, failed


async def _purge_dead_token(token: str) -> None:
    """Remove an Expo push token that the push service reported as dead."""
    try:
        await database.execute(
            "UPDATE employees SET expo_push_token = NULL WHERE expo_push_token = :t",
            {"t": token},
        )
        logger.info("[Push] Token purgado (dispositivo ya no registrado): %s…", token[:20])
    except Exception as e:
        logger.warning("[Push] Fallo al purgar token muerto: %s", e)


async def send_push_notifications_batch(messages):
    """
    Send a batch of push notifications through the Expo API.

    Args:
        messages: list of {to, title, body, data?} dicts.

    Expo accepts up to 100 messages per request — batching turns N HTTP
    requests into ceil(N/100). Dead tokens reported by Expo are purged so
    they stop being retried on every scheduler tick.

    Returns: {"sent": int, "failed": int, "purged": int}
    """
    if not messages:
        return {"sent": 0, "failed": 0, "purged": 0}

    sent = 0
    failed = 0
    purged = 0

    async with httpx.AsyncClient() as client:
        for i in range(0, len(messages), _EXPO_BATCH_SIZE):
            chunk = messages[i:i + _EXPO_BATCH_SIZE]
            payload = []
            for m in chunk:
                item = {
                    "to": m["to"],
                    "title": m["title"],
                    "body": m["body"],
                    "sound": "default",
                }
                if m.get("data"):
                    item["data"] = m["data"]
                payload.append(item)

            try:
                response = await client.post(_EXPO_PUSH_URL, json=payload, timeout=10.0)
            except Exception as exc:
                logger.error("[Push] Error de red enviando lote a Expo: %s", exc)
                failed += len(chunk)
                continue

            if response.status_code != 200:
                logger.warning("[Push] Expo respondió HTTP %s: %s", response.status_code, response.text[:200])
                failed += len(chunk)
                continue

            try:
                tickets = response.json().get("data", [])
            except Exception:
                failed += len(chunk)
                continue

            dead, ok, fail = extract_dead_tickets(payload, tickets)
            sent += ok
            failed += fail
            for token in dead:
                await _purge_dead_token(token)
                purged += 1

    if sent or failed or purged:
        logger.info("[Push] Lote: %d enviados, %d fallidos, %d tokens purgados", sent, failed, purged)
    return {"sent": sent, "failed": failed, "purged": purged}


async def send_push_notification(to: str, title: str, body: str, data: dict = None) -> bool:
    """
    Sends a single push notification via Expo's push service.

    Args:
        to: Expo push token (must start with 'ExponentPushToken').
        title: Notification title.
        body: Notification body text.
        data: Optional extra data payload.

    Returns:
        True if Expo accepted the message for delivery, False otherwise.
    """
    if not to or not to.startswith("ExponentPushToken"):
        logger.warning("Invalid Expo Push Token (skipped): %s", to[:20] if to else "None")
        return False

    result = await send_push_notifications_batch(
        [{"to": to, "title": title, "body": body, "data": data}]
    )
    return result["sent"] > 0


async def try_acquire_push_slot(employee_id, kind: str, dedup_key: str) -> bool:
    """
    Idempotency slot for scheduled pushes.

    Returns True only for the FIRST caller of a given dedup_key. Prevents
    duplicate reminders when a time window overlaps several cron ticks
    (e.g. shift reminders) and repeated absences nudges across hourly runs.
    Fails OPEN (returns True) if the registry is unavailable — losing a
    dedup is better than losing a reminder.
    """
    try:
        row = await database.fetch_one(
            """
            INSERT INTO push_notifications_log (employee_id, kind, dedup_key)
            VALUES (:eid, :kind, :dk)
            ON CONFLICT (dedup_key) DO NOTHING
            RETURNING id
            """,
            {"eid": employee_id, "kind": kind, "dk": dedup_key},
        )
        return row is not None
    except Exception as e:
        logger.warning("[Push dedup] Registro no disponible (fail-open): %s", e)
        return True
