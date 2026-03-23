"""Auth routes — register (with anon migration), login."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ome_server import ome_manager
from ome_server.deps import create_token

router = APIRouter()


class RegisterRequest(BaseModel):
    user_id: str
    password: str
    name: str = ""
    traits: Optional[list[str]] = None
    style: str = ""
    values: Optional[list[str]] = None
    session_id: Optional[str] = None  # Migrate anonymous session


class LoginRequest(BaseModel):
    user_id: str
    password: str


class TokenResponse(BaseModel):
    token: str
    user_id: str
    name: str


@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest):
    """Create a new user and their Ome.

    If session_id is provided, migrates the anonymous chat history
    so nothing from the first conversation is lost.
    """
    try:
        ome = ome_manager.register_user(
            user_id=req.user_id,
            password=req.password,
            name=req.name or req.user_id,
            traits=req.traits,
            style=req.style,
            values=req.values,
            session_id=req.session_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    token = create_token(req.user_id)
    return TokenResponse(token=token, user_id=req.user_id, name=ome.name)


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    """Login and get JWT token."""
    if not ome_manager.authenticate(req.user_id, req.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    ome = ome_manager.get_ome(req.user_id)
    token = create_token(req.user_id)
    return TokenResponse(token=token, user_id=req.user_id, name=ome.name)
