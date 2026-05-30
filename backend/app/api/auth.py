from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session
from redis.asyncio import Redis

from app.deps import get_db, get_redis, get_current_user
from app.db.models import User
from app.schemas.auth import (
    LoginRequest, MfaRequestRequest, MfaVerifyRequest,
    RegisterRequest, RegisterVerifyRequest,
)
from app.services import auth as auth_svc

router = APIRouter(prefix="/auth")


@router.post("/register")
async def register(
    request: Request,
    body: RegisterRequest,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    return await auth_svc.register_flow(request, body, db, redis)


@router.post("/register/verify")
async def register_verify(
    request: Request,
    response: Response,
    body: RegisterVerifyRequest,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    return await auth_svc.register_verify_flow(request, response, body, db, redis)


@router.post("/login")
async def login(
    request: Request,
    response: Response,
    body: LoginRequest,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    return await auth_svc.login_flow(request, response, body, db, redis)


@router.post("/mfa/verify")
async def mfa_verify(
    request: Request,
    response: Response,
    body: MfaVerifyRequest,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    return await auth_svc.mfa_verify_flow(request, response, body, db, redis)


@router.post("/mfa/request")
async def mfa_request(
    request: Request,
    body: MfaRequestRequest,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    return await auth_svc.mfa_request_flow(request, body, db, redis)


@router.get("/security/confirm")
async def confirm_was_me(
    token: str = Query(...),
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    return await auth_svc.confirm_was_me_flow(token, db, redis)


@router.get("/security/deny")
async def deny_was_me(
    token: str = Query(...),
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    return await auth_svc.deny_was_me_flow(token, db, redis)


@router.post("/refresh")
async def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    return await auth_svc.refresh_flow(request, response, db)


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    return await auth_svc.logout_flow(request, response, db)


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {
        "uuid": str(user.uuid),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value if hasattr(user.role, "value") else user.role,
        "is_verified": user.is_verified,
    }