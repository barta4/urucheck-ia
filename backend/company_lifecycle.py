"""
Company lifecycle management.
Handles trial expiration, grace periods, suspension, cancellation.
"""
import json
from datetime import datetime, timedelta
from database import database


async def process_lifecycle_events():
    """
    Main lifecycle processor. Call from scheduler.
    - Expire trials → suspend or activate
    - Grace period → suspend if no payment
    - Suspended too long → cancel
    """
    now = datetime.now()
    print(f"[Lifecycle] Procesando eventos a {now}...")

    # 1. Expire trials
    await _expire_trials()

    # 2. Grace period expired → suspend
    await _expire_grace()

    # 3. Suspended too long → cancel (30 days)
    await _cancel_long_suspended()

    print("[Lifecycle] Procesamiento completado.")


async def _expire_trials():
    """Move companies with expired trials to 'grace' status"""
    expired = await database.fetch_all(
        """
        SELECT id, name, slug FROM companies
        WHERE status = 'trial' AND active = true
        AND trial_ends_at < NOW()
        """
    )

    for company in expired:
        cid = str(company["id"])
        print(f"[Lifecycle] Trial expirado: {company['name']} ({company['slug']})")

        await database.execute(
            """
            UPDATE companies SET status = 'grace', updated_at = NOW()
            WHERE id = :cid
            """,
            {"cid": cid}
        )

        await database.execute(
            """
            UPDATE subscriptions SET status = 'trial_expired', updated_at = NOW()
            WHERE company_id = :cid
            """,
            {"cid": cid}
        )

        # Log
        await database.execute(
            """
            INSERT INTO audit_logs (company_id, action, resource, details)
            VALUES (:cid, 'trial_expired', 'company', :details)
            """,
            {"cid": cid, "details": json.dumps({"name": company["name"], "slug": company["slug"]})}
        )


async def _expire_grace():
    """Suspend companies that exceeded grace period (3 days)"""
    grace_expired = await database.fetch_all(
        """
        SELECT id, name, slug FROM companies
        WHERE status = 'grace' AND active = true
        AND trial_ends_at < NOW() - INTERVAL '3 days'
        """
    )

    for company in grace_expired:
        cid = str(company["id"])
        print(f"[Lifecycle] Suspendiendo: {company['name']} ({company['slug']})")

        await database.execute(
            """
            UPDATE companies SET status = 'suspended', suspended_at = NOW(), updated_at = NOW()
            WHERE id = :cid
            """,
            {"cid": cid}
        )

        await database.execute(
            """
            UPDATE subscriptions SET status = 'suspended', updated_at = NOW()
            WHERE company_id = :cid
            """,
            {"cid": cid}
        )

        await database.execute(
            """
            INSERT INTO audit_logs (company_id, action, resource, details)
            VALUES (:cid, 'company_suspended', 'company', :details)
            """,
            {"cid": cid, "details": json.dumps({"name": company["name"], "reason": "grace_period_expired"})}
        )


async def _cancel_long_suspended():
    """Cancel companies suspended for more than 30 days"""
    long_suspended = await database.fetch_all(
        """
        SELECT id, name, slug FROM companies
        WHERE status = 'suspended' AND active = true
        AND suspended_at < NOW() - INTERVAL '30 days'
        """
    )

    for company in long_suspended:
        cid = str(company["id"])
        print(f"[Lifecycle] Cancelando: {company['name']} ({company['slug']})")

        await database.execute(
            """
            UPDATE companies SET
                status = 'cancelled',
                cancelled_at = NOW(),
                updated_at = NOW()
            WHERE id = :cid
            """,
            {"cid": cid}
        )

        await database.execute(
            """
            INSERT INTO audit_logs (company_id, action, resource, details)
            VALUES (:cid, 'company_cancelled', 'company', :details)
            """,
            {"cid": cid, "details": json.dumps({"name": company["name"], "reason": "suspended_30_days"})}
        )


async def get_company_lifecycle_status(company_id: str) -> dict:
    """Get detailed lifecycle info for a company"""
    company = await database.fetch_one(
        """
        SELECT id, name, slug, status, trial_ends_at, subscription_ends_at,
               suspended_at, cancelled_at, created_at,
               CASE
                   WHEN status = 'trial' AND trial_ends_at IS NOT NULL
                   THEN GREATEST(0, EXTRACT(DAY FROM (trial_ends_at - NOW())))
                   ELSE 0
               END as trial_days_remaining
        FROM companies
        WHERE id = :cid
        """,
        {"cid": company_id}
    )

    if not company:
        return {}

    result = dict(company)

    if company["status"] == "trial" and company["trial_ends_at"]:
        remaining = int(result["trial_days_remaining"])
        result["trial_message"] = f"Quedan {remaining} días de prueba" if remaining > 0 else "Tu prueba ha expirado"
        result["trial_urgent"] = remaining <= 3

    return result
