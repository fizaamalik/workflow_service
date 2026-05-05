from fastapi import Header, HTTPException
from jose import JWTError, jwt

from app.core.config import settings


def _is_local_auth_disabled() -> bool:
    return settings.APP_ENV.lower() in {"dev", "local"}


def decode_token(token: str) -> dict:
    if _is_local_auth_disabled():
        # Local/Postman-friendly shortcut:
        # - `Authorization: Bearer dev` is accepted
        # - callers can also omit Authorization entirely (see `get_current_user`)
        return {"sub": "1", "org": "1", "roles": [], "perms": {}}
    try:
        return jwt.decode(
            token,
            settings.JWT_PUBLIC_KEY,
            algorithms=["RS256"],
            options={"verify_exp": True},
        )
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid or expired token: {str(e)}")
    except Exception:
        raise HTTPException(status_code=401, detail="Token validation failed")


async def get_current_user(
    authorization: str | None = Header(None),
    x_user_id: str | None = Header(None, alias="X-User-Id"),
    x_org_id: str | None = Header(None, alias="X-Org-Id"),
) -> dict:
    """
    Auth dependency.

    Prod:
      - Requires `Authorization: Bearer <jwt>` (RS256) with claims: sub, org

    Dev/local:
      - No JWT required
      - Optionally impersonate by sending `X-User-Id` / `X-Org-Id`
    """

    if _is_local_auth_disabled() and (x_user_id or x_org_id):
        try:
            user_id = int(x_user_id or "1")
            org_id = int(x_org_id or "1")
        except ValueError:
            raise HTTPException(status_code=400, detail="X-User-Id and X-Org-Id must be integers")
        return {
            "user_id": user_id,
            "org_id": org_id,
            "roles": [],
            "perms": {},
            "jti": None,
            "raw_token": authorization or "",
        }

    if not authorization:
        if _is_local_auth_disabled():
            claims = decode_token("dev")
            return {
                "user_id": int(claims["sub"]),
                "org_id": int(claims["org"]),
                "roles": claims.get("roles", []),
                "perms": claims.get("perms", {}),
                "jti": claims.get("jti"),
                "raw_token": "",
            }
        raise HTTPException(status_code=401, detail="Authorization header is missing")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header format")

    token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Token is missing")

    claims = decode_token(token)
    sub = claims.get("sub")
    org = claims.get("org")
    if sub is None or org is None:
        raise HTTPException(status_code=401, detail="Token missing required claims: sub, org")

    return {
        "user_id": int(sub),
        "org_id": int(org),
        "roles": claims.get("roles", []),
        "perms": claims.get("perms", {}),
        "jti": claims.get("jti"),
        "raw_token": authorization,
    }

