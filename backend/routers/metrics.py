"""
SaaS Metrics — KPIs for the super-admin dashboard.
MRR, ARR, Churn, LTV, Active Companies, etc.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timedelta
from decimal import Decimal
from auth import get_current_super_admin
from database import database

router = APIRouter(prefix="/api/saas-metrics", tags=["saas-metrics"])


@router.get("/dashboard")
async def saas_dashboard(current_user=Depends(get_current_super_admin)):
    """
    Complete SaaS dashboard metrics.
    Accessible to admin users only.
    """
    # Company counts by status
    status_counts = await database.fetch_all(
        """
        SELECT status, COUNT(*) as cnt
        FROM companies
        WHERE active = true
        GROUP BY status
        """
    )
    status_map = {r["status"]: r["cnt"] for r in status_counts}

    total = sum(status_map.values())
    active = status_map.get("active", 0)
    trial = status_map.get("trial", 0)
    suspended = status_map.get("suspended", 0)
    cancelled = status_map.get("cancelled", 0)

    # MRR (Monthly Recurring Revenue)
    mrr_row = await database.fetch_one(
        """
        SELECT COALESCE(SUM(p.price_monthly), 0) as mrr
        FROM subscriptions s
        JOIN plans p ON s.plan_id = p.id
        JOIN companies c ON s.company_id = c.id
        WHERE s.status = 'active' AND c.active = true
        """
    )
    mrr = mrr_row["mrr"] if mrr_row else Decimal(0)
    arr = mrr * 12

    # Total revenue (all time)
    revenue = await database.fetch_one(
        "SELECT COALESCE(SUM(amount), 0) as total FROM payments WHERE mercado_pago_status = 'approved'"
    )
    total_revenue = revenue["total"] if revenue else Decimal(0)

    # Total employees across all companies
    emp_count = await database.fetch_one(
        "SELECT COUNT(*) as cnt FROM employees WHERE active = true"
    )
    total_employees = emp_count["cnt"] if emp_count else 0

    # Plans distribution
    plans_dist = await database.fetch_all(
        """
        SELECT p.name, COUNT(c.id) as cnt
        FROM companies c
        JOIN plans p ON c.plan_id = p.id
        WHERE c.active = true
        GROUP BY p.name
        """
    )
    plans_distribution = {r["name"]: r["cnt"] for r in plans_dist}

    # Recent signups (last 7 days)
    recent = await database.fetch_one(
        "SELECT COUNT(*) as cnt FROM companies WHERE created_at >= NOW() - INTERVAL '7 days'"
    )
    recent_signups = recent["cnt"] if recent else 0

    # Expiring trials (next 3 days)
    expiring = await database.fetch_one(
        """
        SELECT COUNT(*) as cnt FROM companies
        WHERE status = 'trial' AND trial_ends_at BETWEEN NOW() AND NOW() + INTERVAL '3 days'
        """
    )
    expiring_trials = expiring["cnt"] if expiring else 0

    # Churn rate (cancellations this month / total at start of month)
    first_of_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    cancellations_this_month = await database.fetch_one(
        """
        SELECT COUNT(*) as cnt FROM companies
        WHERE status = 'cancelled' AND cancelled_at >= :dom
        """,
        {"dom": first_of_month}
    )
    total_start = await database.fetch_one(
        "SELECT COUNT(*) as cnt FROM companies WHERE created_at < :dom",
        {"dom": first_of_month}
    )
    canc = cancellations_this_month["cnt"] if cancellations_this_month else 0
    tot = total_start["cnt"] if total_start else 1
    churn_rate = round((canc / tot) * 100, 2) if tot > 0 else 0

    # Top companies by usage (most attendance logs this month)
    top_companies = await database.fetch_all(
        """
        SELECT c.name, c.slug, COUNT(al.id) as log_count
        FROM attendance_logs al
        JOIN companies c ON al.company_id = c.id
        WHERE al.created_at >= :dom
        GROUP BY c.id, c.name, c.slug
        ORDER BY log_count DESC
        LIMIT 10
        """,
        {"dom": first_of_month}
    )

    # Recent activity
    recent_activity = await database.fetch_all(
        """
        SELECT al.*, c.name as company_name
        FROM audit_logs al
        JOIN companies c ON al.company_id = c.id
        ORDER BY al.created_at DESC
        LIMIT 20
        """,
        {}
    )

    return {
        "companies": {
            "total": total,
            "active": active,
            "trial": trial,
            "suspended": suspended,
            "cancelled": cancelled,
        },
        "revenue": {
            "mrr": float(mrr),
            "arr": float(arr),
            "total_revenue": float(total_revenue),
            "churn_rate": churn_rate,
        },
        "usage": {
            "total_employees": total_employees,
            "plans_distribution": plans_distribution,
            "recent_signups": recent_signups,
            "expiring_trials": expiring_trials,
            "top_companies": [dict(r) for r in top_companies],
        },
        "recent_activity": [dict(r) for r in recent_activity],
    }


@router.get("/companies")
async def list_companies_metrics(current_user=Depends(get_current_super_admin)):
    """List all companies with key metrics for admin table"""
    rows = await database.fetch_all(
        """
        SELECT
            c.id, c.name, c.slug, c.admin_email, c.status, c.created_at,
            c.trial_ends_at, c.suspended_at, c.cancelled_at,
            p.name as plan_name, p.price_monthly as plan_price,
            (SELECT COUNT(*) FROM employees e WHERE e.company_id = c.id AND e.active = true) as active_employees,
            (SELECT COUNT(*) FROM attendance_logs al WHERE al.company_id = c.id AND DATE(al.timestamp) = CURRENT_DATE) as today_logs,
            (SELECT MAX(timestamp) FROM attendance_logs al WHERE al.company_id = c.id) as last_activity
        FROM companies c
        LEFT JOIN plans p ON c.plan_id = p.id
        WHERE c.active = true
        ORDER BY c.created_at DESC
        """
    )
    return [dict(r) for r in rows]


from pydantic import BaseModel

class SaasSettingsUpdate(BaseModel):
    apk_url: str
    ios_url: str

@router.get("/settings")
async def get_saas_settings(current_user=Depends(get_current_super_admin)):
    """Get global SaaS application download URLs"""
    apk_row = await database.fetch_one("SELECT value FROM saas_settings WHERE id = 'apk_url'")
    ios_row = await database.fetch_one("SELECT value FROM saas_settings WHERE id = 'ios_url'")
    return {
        "apk_url": apk_row["value"] if apk_row else "",
        "ios_url": ios_row["value"] if ios_row else ""
    }

@router.post("/settings")
async def update_saas_settings(payload: SaasSettingsUpdate, current_user=Depends(get_current_super_admin)):
    """Update global SaaS application download URLs"""
    await database.execute(
        "UPDATE saas_settings SET value = :val, updated_at = NOW() WHERE id = 'apk_url'",
        {"val": payload.apk_url}
    )
    await database.execute(
        "UPDATE saas_settings SET value = :val, updated_at = NOW() WHERE id = 'ios_url'",
        {"val": payload.ios_url}
    )
    return {"message": "Configuración global de descargas de App actualizada."}


# ─── SaaS Billing & Subscriptions Management ──────────────────────────────────

@router.get("/billing")
async def get_saas_billing(current_user=Depends(get_current_super_admin)):
    """
    Consolidated billing view for all companies.
    Provides payment status, next due date, days overdue, and global financial KPIs in USD.
    """
    companies = await database.fetch_all(
        """
        SELECT
            c.id, c.name, c.slug, c.admin_email, c.status, c.created_at,
            c.trial_ends_at, c.last_payment_at,
            p.id as plan_id, p.name as plan_name, COALESCE(p.price_monthly, 0) as plan_price,
            s.id as subscription_id, s.status as sub_status,
            s.current_period_start, s.current_period_end, s.trial_start, s.trial_end
        FROM companies c
        LEFT JOIN plans p ON c.plan_id = p.id
        LEFT JOIN subscriptions s ON c.id = s.company_id
        WHERE c.active = true
        ORDER BY c.created_at DESC
        """
    )

    now = datetime.now()
    billing_list = []
    total_mrr = 0.0
    total_pending = 0.0
    count_up_to_date = 0
    count_overdue = 0
    count_trial = 0

    for c in companies:
        cid = str(c["id"])
        # Fetch payment stats for this company
        pay_stats = await database.fetch_one(
            """
            SELECT
                COALESCE(SUM(amount), 0) as total_paid,
                COUNT(*) as payment_count
            FROM payments
            WHERE company_id = :cid AND mercado_pago_status = 'approved'
            """,
            {"cid": cid}
        )
        total_paid = float(pay_stats["total_paid"]) if pay_stats else 0.0
        payment_count = int(pay_stats["payment_count"]) if pay_stats else 0

        # Most recent payment
        last_pay = await database.fetch_one(
            """
            SELECT amount, method, created_at, mercado_pago_id
            FROM payments
            WHERE company_id = :cid AND mercado_pago_status = 'approved'
            ORDER BY created_at DESC LIMIT 1
            """,
            {"cid": cid}
        )

        plan_price = float(c["plan_price"])
        status = c["status"]
        trial_end = c["trial_end"] or c["trial_ends_at"]
        period_end = c["current_period_end"]

        # Calculate next due date and billing status
        billing_status = "up_to_date"
        days_overdue = 0
        next_due_date = None

        if status == "trial":
            billing_status = "trial"
            next_due_date = trial_end
            if trial_end:
                t_end = trial_end.replace(tzinfo=None) if hasattr(trial_end, 'tzinfo') and trial_end.tzinfo else trial_end
                diff_days = (t_end - now).days
                if diff_days < 0:
                    days_overdue = abs(diff_days)
                    billing_status = "overdue"
            count_trial += 1
        elif status == "cancelled":
            billing_status = "cancelled"
            next_due_date = period_end
        elif status == "suspended":
            billing_status = "suspended"
            next_due_date = period_end
            days_overdue = 1
            count_overdue += 1
            total_pending += plan_price
        else: # active or grace
            next_due_date = period_end or (c["created_at"] + timedelta(days=30))
            if next_due_date:
                p_end = next_due_date.replace(tzinfo=None) if hasattr(next_due_date, 'tzinfo') and next_due_date.tzinfo else next_due_date
                if p_end < now:
                    days_overdue = (now - p_end).days
                    billing_status = "overdue"
                    count_overdue += 1
                    total_pending += plan_price
                else:
                    billing_status = "up_to_date"
                    count_up_to_date += 1
                    total_mrr += plan_price
            else:
                billing_status = "up_to_date"
                count_up_to_date += 1
                total_mrr += plan_price

        billing_list.append({
            "company_id": cid,
            "company_name": c["name"],
            "company_slug": c["slug"],
            "admin_email": c["admin_email"],
            "plan_id": str(c["plan_id"]) if c["plan_id"] else None,
            "plan_name": c["plan_name"] or "Gratis",
            "plan_price": plan_price,
            "currency": "USD",
            "status": status,
            "billing_status": billing_status,
            "days_overdue": days_overdue,
            "next_due_date": next_due_date.isoformat() if next_due_date else None,
            "last_payment_at": last_pay["created_at"].isoformat() if last_pay else None,
            "last_payment_amount": float(last_pay["amount"]) if last_pay else 0.0,
            "last_payment_method": last_pay["method"] if last_pay else None,
            "total_paid": total_paid,
            "payment_count": payment_count,
        })

    # All-time total revenue
    rev_row = await database.fetch_one("SELECT COALESCE(SUM(amount), 0) as total FROM payments WHERE mercado_pago_status = 'approved'")
    total_revenue = float(rev_row["total"]) if rev_row else 0.0

    return {
        "companies": billing_list,
        "summary": {
            "total_companies": len(billing_list),
            "up_to_date": count_up_to_date,
            "overdue": count_overdue,
            "in_trial": count_trial,
            "mrr": round(total_mrr, 2),
            "total_collected": round(total_revenue, 2),
            "total_pending": round(total_pending, 2),
            "currency": "USD"
        }
    }


@router.get("/payments-history")
async def get_payments_history(
    search: str = "",
    limit: int = 50,
    offset: int = 0,
    current_user=Depends(get_current_super_admin)
):
    """
    Global payments history across all companies.
    """
    params = {"limit": limit, "offset": offset}
    where_clauses = ["1=1"]

    if search.strip():
        where_clauses.append("(c.name ILIKE :search OR c.slug ILIKE :search OR p.mercado_pago_id ILIKE :search OR p.method ILIKE :search)")
        params["search"] = f"%{search.strip()}%"

    where_sql = " AND ".join(where_clauses)

    total_row = await database.fetch_one(
        f"""
        SELECT COUNT(*) as count
        FROM payments p
        JOIN companies c ON p.company_id = c.id
        WHERE {where_sql}
        """,
        params if "search" in params else {}
    )
    total = total_row["count"] if total_row else 0

    rows = await database.fetch_all(
        f"""
        SELECT
            p.id, p.company_id, c.name as company_name, c.slug as company_slug,
            p.amount, COALESCE(p.currency, 'USD') as currency, p.method,
            p.mercado_pago_id, p.mercado_pago_status, p.notes, p.created_at,
            i.invoice_number
        FROM payments p
        JOIN companies c ON p.company_id = c.id
        LEFT JOIN invoices i ON p.invoice_id = i.id
        WHERE {where_sql}
        ORDER BY p.created_at DESC
        LIMIT :limit OFFSET :offset
        """,
        params
    )

    return {
        "payments": [
            {
                "id": str(r["id"]),
                "company_id": str(r["company_id"]),
                "company_name": r["company_name"],
                "company_slug": r["company_slug"],
                "amount": float(r["amount"]),
                "currency": r["currency"] or "USD",
                "method": r["method"] or "mercado_pago",
                "mercado_pago_id": r["mercado_pago_id"],
                "mercado_pago_status": r["mercado_pago_status"] or "approved",
                "notes": r["notes"],
                "invoice_number": r["invoice_number"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset
    }


class ManualPaymentRequest(BaseModel):
    company_id: str
    amount: float
    currency: str = "USD"
    method: str = "bank_transfer" # bank_transfer | cash | check | credit_card | crypto | other
    notes: Optional[str] = None
    days_to_add: int = 30


@router.post("/manual-payment")
async def register_manual_payment(
    payload: ManualPaymentRequest,
    current_user=Depends(get_current_super_admin)
):
    """
    Super-admin registers a manual payment (e.g. wire transfer, cash).
    Activates the company and advances subscription period.
    """
    company = await database.fetch_one(
        "SELECT id, name, slug FROM companies WHERE id = :cid",
        {"cid": payload.company_id}
    )
    if not company:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    # Generate an invoice number
    now = datetime.now()
    inv_num = f"INV-{now.strftime('%Y%m')}-{payload.company_id[:4].upper()}-{int(now.timestamp()) % 10000}"

    invoice_id = await database.execute(
        """
        INSERT INTO invoices (company_id, invoice_number, amount, currency, status, paid_at)
        VALUES (:cid, :inv_num, :amount, :currency, 'paid', NOW())
        RETURNING id
        """,
        {
            "cid": payload.company_id,
            "inv_num": inv_num,
            "amount": payload.amount,
            "currency": payload.currency,
        }
    )

    # Record payment
    payment_id = await database.execute(
        """
        INSERT INTO payments (company_id, invoice_id, amount, currency, method, mercado_pago_status, notes)
        VALUES (:cid, :inv_id, :amount, :currency, :method, 'approved', :notes)
        RETURNING id
        """,
        {
            "cid": payload.company_id,
            "inv_id": invoice_id,
            "amount": payload.amount,
            "currency": payload.currency,
            "method": payload.method,
            "notes": payload.notes,
        }
    )

    # Extend or activate subscription
    sub = await database.fetch_one(
        "SELECT id, current_period_end FROM subscriptions WHERE company_id = :cid",
        {"cid": payload.company_id}
    )

    if sub:
        # If current period is still in the future, extend from that date; else from NOW()
        curr_end = sub["current_period_end"]
        if curr_end and curr_end.replace(tzinfo=None) > now:
            new_end = curr_end.replace(tzinfo=None) + timedelta(days=payload.days_to_add)
        else:
            new_end = now + timedelta(days=payload.days_to_add)

        await database.execute(
            """
            UPDATE subscriptions SET
                status = 'active',
                current_period_start = NOW(),
                current_period_end = :nend,
                updated_at = NOW()
            WHERE company_id = :cid
            """,
            {"cid": payload.company_id, "nend": new_end}
        )
    else:
        new_end = now + timedelta(days=payload.days_to_add)
        await database.execute(
            """
            INSERT INTO subscriptions (company_id, status, current_period_start, current_period_end)
            VALUES (:cid, 'active', NOW(), :nend)
            """,
            {"cid": payload.company_id, "nend": new_end}
        )

    # Update company status
    await database.execute(
        """
        UPDATE companies SET
            status = 'active',
            last_payment_at = NOW(),
            updated_at = NOW()
        WHERE id = :cid
        """,
        {"cid": payload.company_id}
    )

    # Audit log
    await database.execute(
        """
        INSERT INTO audit_logs (company_id, user_id, action, resource, resource_id, details)
        VALUES (:cid, :uid, 'manual_payment_recorded', 'payment', :pid, :details)
        """,
        {
            "cid": payload.company_id,
            "uid": current_user["id"],
            "pid": payment_id,
            "details": json.dumps({
                "amount": payload.amount,
                "currency": payload.currency,
                "method": payload.method,
                "days_added": payload.days_to_add,
                "notes": payload.notes,
            })
        }
    )

    return {
        "message": f"Pago de ${payload.amount} {payload.currency} registrado con éxito para {company['name']}.",
        "payment_id": str(payment_id),
        "invoice_number": inv_num,
        "new_period_end": new_end.isoformat()
    }


class PaymentLinkRequest(BaseModel):
    company_id: str
    amount: float
    description: Optional[str] = "Suscripción mensual UruCheck IA SaaS"


@router.post("/create-payment-link")
async def create_company_payment_link(
    payload: PaymentLinkRequest,
    current_user=Depends(get_current_super_admin)
):
    """
    Generate a MercadoPago checkout preference link for a specific company in USD.
    """
    company = await database.fetch_one(
        "SELECT id, name, admin_email FROM companies WHERE id = :cid",
        {"cid": payload.company_id}
    )
    if not company:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    try:
        import httpx
        from mp_oauth import get_mp_access_token
        from config import settings

        mp_token = await get_mp_access_token()

        preference_data = {
            "items": [{
                "title": payload.description,
                "quantity": 1,
                "unit_price": payload.amount,
                "currency_id": "USD",
            }],
            "payer": {
                "name": company["name"],
                "email": company["admin_email"],
            },
            "external_reference": str(company["id"]),
            "metadata": {
                "company_id": str(company["id"])
            },
            "back_urls": {
                "success": f"{settings.FRONTEND_URL}/subscription/success",
                "failure": f"{settings.FRONTEND_URL}/subscription/failure",
                "pending": f"{settings.FRONTEND_URL}/subscription/pending",
            },
            "auto_return": "approved",
            "notification_url": f"{settings.FRONTEND_URL.replace('http://', 'https://').rstrip('/')}/api/payments/webhook",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.mercadopago.com/checkout/preferences",
                headers={
                    "Authorization": f"Bearer {mp_token}",
                    "Content-Type": "application/json",
                },
                json=preference_data,
                timeout=15.0
            )

        if response.status_code not in (200, 201):
            raise HTTPException(status_code=500, detail=f"Error en MercadoPago: {response.text}")

        res = response.json()
        return {
            "preference_id": res["id"],
            "init_point": res["init_point"],
            "sandbox_init_point": res.get("sandbox_init_point"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creando link de pago: {str(e)}")


# ─── MercadoPago Configuration & Health ───────────────────────────────────────

class MercadoPagoCredentialsUpdate(BaseModel):
    client_id: Optional[str] = ""
    client_secret: Optional[str] = ""
    access_token: Optional[str] = ""
    public_key: Optional[str] = ""


@router.get("/mercadopago/status")
async def get_mercadopago_status(current_user=Depends(get_current_super_admin)):
    """
    Get MercadoPago configuration state and health.
    Masks confidential tokens.
    """
    from mp_oauth import get_mp_credentials

    creds = await get_mp_credentials()
    has_token = bool(creds["access_token"])
    has_client_id = bool(creds["client_id"])
    has_client_secret = bool(creds["client_secret"])
    has_public_key = bool(creds["public_key"])

    # Check if we have token stored in mp_oauth_tokens table
    oauth_row = await database.fetch_one(
        "SELECT expires_at, created_at FROM mp_oauth_tokens ORDER BY id DESC LIMIT 1"
    )

    token_valid = None
    account_info = None

    if has_token:
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                res = await client.get(
                    "https://api.mercadopago.com/users/me",
                    headers={"Authorization": f"Bearer {creds['access_token']}"},
                    timeout=8.0
                )
                if res.status_code == 200:
                    token_valid = True
                    info = res.json()
                    account_info = {
                        "user_id": info.get("id"),
                        "email": info.get("email"),
                        "nickname": info.get("nickname"),
                        "site_id": info.get("site_id"),
                        "country_id": info.get("country_id"),
                    }
                else:
                    token_valid = False
        except Exception:
            token_valid = False

    return {
        "configured": has_token or (has_client_id and has_client_secret),
        "has_access_token": has_token,
        "has_client_id": has_client_id,
        "has_client_secret": has_client_secret,
        "has_public_key": has_public_key,
        "client_id": creds["client_id"],
        "public_key": creds["public_key"],
        "token_valid": token_valid,
        "account_info": account_info,
        "oauth_token_expires_at": oauth_row["expires_at"] if oauth_row else None,
        "currency": "USD"
    }


@router.post("/mercadopago/credentials")
async def update_mercadopago_credentials(
    payload: MercadoPagoCredentialsUpdate,
    current_user=Depends(get_current_super_admin)
):
    """
    Save or update MercadoPago credentials in saas_settings.
    """
    keys = {
        "mp_client_id": payload.client_id or "",
        "mp_client_secret": payload.client_secret or "",
        "mp_access_token": payload.access_token or "",
        "mp_public_key": payload.public_key or "",
    }

    for k, v in keys.items():
        # Only overwrite if provided, or if user explicitly sent non-null
        await database.execute(
            """
            INSERT INTO saas_settings (id, value, updated_at)
            VALUES (:id, :val, NOW())
            ON CONFLICT (id) DO UPDATE SET value = :val, updated_at = NOW()
            """,
            {"id": k, "val": v}
        )

    return {"message": "Credenciales de MercadoPago actualizadas con éxito."}


@router.post("/mercadopago/test")
async def test_mercadopago_connection(current_user=Depends(get_current_super_admin)):
    """
    Test connection to MercadoPago API using active access token.
    """
    from mp_oauth import get_mp_access_token
    import httpx

    try:
        token = await get_mp_access_token()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(
                "https://api.mercadopago.com/users/me",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0
            )

        if res.status_code != 200:
            raise HTTPException(
                status_code=400,
                detail=f"MercadoPago retornó código {res.status_code}: {res.text}"
            )

        data = res.json()
        return {
            "success": True,
            "message": "¡Conexión exitosa con MercadoPago!",
            "account": {
                "id": data.get("id"),
                "email": data.get("email"),
                "nickname": data.get("nickname"),
                "site_id": data.get("site_id"),
                "country_id": data.get("country_id"),
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error probando conexión: {str(e)}")


