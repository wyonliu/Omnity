"""Shared dependencies — JWT auth, Ome instance injection."""

from __future__ import annotations

import os
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from ome.core import Ome
from ome_server import ome_manager

SECRET_KEY = os.environ.get("OME_JWT_SECRET", "ome-dev-secret-change-in-prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30

security = HTTPBearer(auto_error=False)


def create_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": user_id, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> str:
    """Decode JWT and return user_id. Raises on invalid."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise JWTError("No sub")
        return user_id
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
        )


async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """Extract user_id from Bearer token."""
    if not creds:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return decode_token(creds.credentials)


async def get_ome(user_id: str = Depends(get_current_user)) -> Ome:
    """Inject the current user's Ome instance."""
    try:
        return ome_manager.get_ome(user_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Ome not found. Create one first.")
