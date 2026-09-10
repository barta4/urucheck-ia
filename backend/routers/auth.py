from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from schemas import LoginRequest, TokenResponse
from auth import verify_password, create_access_token, oauth2_scheme, revoke_token
from database import database
from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter(prefix="/api/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)

@router.post("/login")
@limiter.limit("20/minute")
async def login(request: Request, data: LoginRequest):
    clean_email = data.email.strip() if data.email else ""
    
    # Fetch all active accounts with this email to check for multi-tenant duplicate emails
    users = await database.fetch_all(
        """
        SELECT e.*, c.name as company_name, c.slug as company_slug, c.status as company_status
        FROM employees e
        JOIN companies c ON e.company_id = c.id
        WHERE LOWER(e.email) = LOWER(:email) AND e.active = true AND c.active = true
        AND c.status NOT IN ('suspended', 'cancelled')
        """,
        {"email": clean_email}
    )

    if not users:
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")

    user = None
    if len(users) > 1:
        if not data.company_slug:
            raise HTTPException(
                status_code=400,
                detail="multiple_companies"
            )
        # Find matching company slug
        for u in users:
            if u["company_slug"].lower() == data.company_slug.strip().lower():
                user = u
                break
        if not user:
            raise HTTPException(status_code=401, detail="Email o contraseña incorrectos para la empresa especificada")
    else:
        # Only one company matches this email
        single_user = users[0]
        if data.company_slug:
            if single_user["company_slug"].lower() != data.company_slug.strip().lower():
                raise HTTPException(status_code=401, detail="El email no está registrado en la empresa especificada")
        user = single_user

    if not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")

    user_dict = dict(user)

    if data.device_id and user_dict["role"] != "admin": # Allow admins to login from anywhere if desired, or maybe apply to everyone. The prompt said "empleado". Usually admins can use web. But the web doesn't send device_id.
        # Actually, let's just apply it if device_id is sent. Web login won't send it.
        stored_device_id = user_dict.get("device_id")
        if not stored_device_id:
            await database.execute(
                "UPDATE employees SET device_id = :device_id WHERE id = :id",
                {"device_id": data.device_id, "id": user_dict["id"]}
            )
        elif stored_device_id != data.device_id:
            raise HTTPException(
                status_code=403, 
                detail="Dispositivo no autorizado. Ya tienes una cuenta vinculada a otro equipo. Contacta a RRHH."
            )

    token_data = {
        "sub": str(user_dict["id"]),
        "company_id": str(user_dict["company_id"]),
        "company_slug": user_dict["company_slug"],
        "is_super_admin": user_dict.get("is_super_admin", False),
    }
    token = create_access_token(token_data)

    return TokenResponse(
        access_token=token,
        user_id=str(user_dict["id"]),
        name=user_dict["name"],
        role=user_dict["role"],
        company_id=str(user_dict["company_id"]),
        company_name=user_dict["company_name"],
        company_slug=user_dict["company_slug"],
        company_status=user_dict["company_status"],
        is_super_admin=user_dict.get("is_super_admin", False),
    )


@router.post("/logout")
async def logout(token: str = Depends(oauth2_scheme)):
    """
    Revokes the current JWT access token so it cannot be used again.
    """
    revoked = await revoke_token(token)
    return {"status": "ok", "message": "Sesión cerrada correctamente", "revoked": revoked}
