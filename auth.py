import base64
import os
import secrets
from datetime import datetime, timedelta

import bcrypt
from fastapi import APIRouter, Body, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from webauthn import generate_registration_options, verify_registration_response
from webauthn import generate_authentication_options, verify_authentication_response
from webauthn.helpers.structs import AuthenticatorSelectionCriteria, ResidentKeyRequirement, UserVerificationRequirement

from db import get_db

DEFAULT_PASSWORD = os.environ.get("DEFAULT_MEMBER_PASSWORD", "changeme")
RP_ID = os.environ.get("RP_ID", "localhost")
RP_NAME = os.environ.get("RP_NAME", "Scoreboard App")
TOKEN_TTL_HOURS = int(os.environ.get("TOKEN_TTL_HOURS", "168"))

_SESSIONS = {}
_PASSKEY_CHALLENGES = {}


def _hash_password(plain):
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def _verify_password(plain, hashed):
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _create_token(name):
    raw = secrets.token_urlsafe(24)
    _SESSIONS[raw] = {
        "name": name,
        "expires": datetime.now().timestamp() + TOKEN_TTL_HOURS * 3600,
    }
    return raw


def _clear_expired_sessions():
    now = datetime.now().timestamp()
    expired = [t for t, v in _SESSIONS.items() if v["expires"] <= now]
    for t in expired:
        del _SESSIONS[t]


from fastapi import Body


def require_admin(request):
    name = require_auth(request)
    conn = get_db()
    row = conn.execute("SELECT role FROM members WHERE name = ?", (name,)).fetchone()
    conn.close()
    if not row or row["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return name


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(payload: dict = Body(...)):
    name = payload.get("name")
    password = payload.get("password")
    if not name or not password:
        raise HTTPException(status_code=400, detail="name and password required")

    conn = get_db()
    row = conn.execute(
        "SELECT name, password_hash FROM members WHERE name = ? AND active = 1",
        (name,),
    ).fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    stored_hash = row["password_hash"]
    if not stored_hash:
        if password != DEFAULT_PASSWORD:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        conn = get_db()
        conn.execute(
            "UPDATE members SET password_hash = ? WHERE name = ?",
            (_hash_password(password), row["name"]),
        )
        conn.commit()
        conn.close()
    elif not _verify_password(password, stored_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = _create_token(row["name"])
    resp = JSONResponse({"ok": True, "name": row["name"]})
    resp.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        max_age=TOKEN_TTL_HOURS * 3600,
        samesite="lax",
    )
    return resp


@router.post("/logout")
def logout(response: Response, request: Request):
    token = request.cookies.get("session_token")
    if token and token in _SESSIONS:
        del _SESSIONS[token]
    response.delete_cookie("session_token")
    return {"ok": True}


@router.get("/whoami")
def whoami(request: Request):
    token = request.cookies.get("session_token")
    _clear_expired_sessions()
    if token and token in _SESSIONS:
        name = _SESSIONS[token]["name"]
        role = "member"
        conn = get_db()
        row = conn.execute("SELECT role FROM members WHERE name = ?", (name,)).fetchone()
        conn.close()
        if row and row["role"]:
            role = row["role"]
        return {"logged_in": True, "name": name, "role": role}
    return {"logged_in": False, "name": None, "role": None}


def get_current_name(request: Request):
    token = request.cookies.get("session_token")
    _clear_expired_sessions()
    if token and token in _SESSIONS:
        return _SESSIONS[token]["name"]
    return None


def require_auth(request: Request):
    name = get_current_name(request)
    if not name:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return name


from webauthn.helpers.structs import AuthenticatorSelectionCriteria, ResidentKeyRequirement, UserVerificationRequirement


@router.post("/passkey/register/begin")
def passkey_register_begin(request: Request, payload: dict = Body(...)):
    name = require_auth(request)
    payload_name = payload.get("name")
    if payload_name and payload_name != name:
        raise HTTPException(status_code=403, detail="Can only register passkeys for yourself")
    
    conn = get_db()
    existing_rows = conn.execute(
        "SELECT credential_id FROM passkeys WHERE member_name = ?", (name,)
    ).fetchall()
    conn.close()

    exclude_credentials = [
        {"id": row["credential_id"], "type": "public-key"}
        for row in existing_rows
    ]

    options = generate_registration_options(
        rp_id=RP_ID,
        rp_name=RP_NAME,
        user_id=name.encode(),
        user_name=name,
        user_display_name=name,
        exclude_credentials=exclude_credentials,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED
        ),
    )

    _PASSKEY_CHALLENGES[name] = base64.b64encode(options.challenge).decode()

    return {
        "options": {
            "rp": options.rp,
            "user": {
                "id": base64.b64encode(options.user.id).decode(),
                "name": options.user.name,
                "displayName": options.user.display_name,
            },
            "challenge": base64.b64encode(options.challenge).decode(),
            "pubKeyCredParams": [{"type": p.type, "alg": p.alg} for p in options.pub_key_cred_params],
            "timeout": options.timeout,
            "excludeCredentials": [{"id": base64.b64encode(c.id).decode(), "type": c.type} for c in options.exclude_credentials] if options.exclude_credentials else [],
            "authenticatorSelection": {
                "residentKey": options.authenticator_selection.resident_key.value if options.authenticator_selection else "preferred",
                "userVerification": options.authenticator_selection.user_verification.value if options.authenticator_selection else "preferred",
            },
            "attestation": options.attestation.value,
        }
    }


@router.post("/passkey/register/finish")
def passkey_register_finish(request: Request, payload: dict = Body(...)):
    auth_name = require_auth(request)
    name = payload.get("name")
    credential = payload.get("credential")
    if not name or not credential:
        raise HTTPException(status_code=400, detail="name and credential required")
    if name != auth_name:
        raise HTTPException(status_code=403, detail="Can only register passkeys for yourself")

    challenge = _PASSKEY_CHALLENGES.pop(name, None)
    if challenge is None:
        raise HTTPException(status_code=400, detail="No pending registration challenge")
    
    credential = payload.get("credential")
    if not credential:
        raise HTTPException(status_code=400, detail="credential required")
    
    try:
        result = verify_registration_response(
            credential=credential,
            expected_challenge=base64.b64decode(challenge),
            expected_rp_id=RP_ID,
            expected_origin=f"https://{RP_ID}" if RP_ID != "localhost" else "http://localhost:8000",
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Registration verification failed: {exc}")

    conn = get_db()
    conn.execute(
        """
        INSERT INTO passkeys (
            member_name, credential_id, public_key, sign_count,
            transports, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            credential.get("id", ""),
            result.credential_public_key.hex(),
            result.sign_count,
            ",".join(credential.get("transports", [])),
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.post("/passkey/auth/begin")
def passkey_auth_begin(payload: dict = Body(...)):
    name = payload.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name required")

    conn = get_db()
    rows = conn.execute(
        "SELECT credential_id FROM passkeys WHERE member_name = ?", (name,)
    ).fetchall()
    conn.close()

    if not rows:
        raise HTTPException(status_code=404, detail="No passkeys found for member")

    allow_credentials = [
        {"id": row["credential_id"], "type": "public-key"} for row in rows
    ]

    options = generate_authentication_options(
        rp_id=RP_ID,
        allow_credentials=allow_credentials,
        user_verification=UserVerificationRequirement.PREFERRED,
    )

    _PASSKEY_CHALLENGES[name] = base64.b64encode(options.challenge).decode()

    return {
        "options": {
            "challenge": base64.b64encode(options.challenge).decode(),
            "timeout": options.timeout,
            "rpId": options.rp_id,
            "allowCredentials": [{"id": c.id, "type": c.type} for c in options.allow_credentials] if options.allow_credentials else [],
            "userVerification": options.user_verification.value,
        }
    }


@router.post("/passkey/auth/finish")
def passkey_auth_finish(request: Request, payload: dict = Body(...)):
    name = payload.get("name")
    credential = payload.get("credential")
    if not name or not credential:
        raise HTTPException(status_code=400, detail="name and credential required")

    challenge = _PASSKEY_CHALLENGES.pop(name, None)
    if challenge is None:
        raise HTTPException(status_code=400, detail="No pending authentication challenge")

    credential_id = credential.get("id", "")
    conn = get_db()
    row = conn.execute(
        """
        SELECT credential_id, public_key, sign_count
        FROM passkeys
        WHERE member_name = ? AND credential_id = ?
        """,
        (name, credential_id),
    ).fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Passkey not found")

    try:
        result = verify_authentication_response(
            credential=credential,
            expected_challenge=base64.b64decode(challenge),
            expected_rp_id=RP_ID,
            expected_origin=f"https://{RP_ID}" if RP_ID != "localhost" else "http://localhost:8000",
            credential_public_key=bytes.fromhex(row["public_key"]),
            credential_current_sign_count=row["sign_count"],
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Authentication verification failed: {exc}")

    conn = get_db()
    conn.execute(
        "UPDATE passkeys SET sign_count = ?, last_used_at = ? WHERE credential_id = ?",
        (result.new_sign_count, datetime.now().isoformat(), row["credential_id"]),
    )
    conn.commit()
    conn.close()

    token = _create_token(name)
    resp = JSONResponse({"ok": True, "name": name})
    resp.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        max_age=TOKEN_TTL_HOURS * 3600,
        samesite="lax",
    )
    return resp


@router.post("/reset-password")
def reset_password(request: Request, payload: dict = Body(...)):
    name = require_auth(request)
    old_password = payload.get("old_password")
    new_password = payload.get("new_password")
    if not old_password or not new_password or len(new_password) < 6:
        raise HTTPException(status_code=400, detail="old_password and new_password (min 6 chars) required")

    conn = get_db()
    row = conn.execute(
        "SELECT password_hash FROM members WHERE name = ?", (name,)
    ).fetchone()
    conn.close()

    if row and row["password_hash"]:
        if not _verify_password(old_password, row["password_hash"]):
            raise HTTPException(status_code=403, detail="Old password incorrect")
    else:
        if old_password != DEFAULT_PASSWORD:
            raise HTTPException(status_code=403, detail="Old password incorrect")

    conn = get_db()
    conn.execute(
        "UPDATE members SET password_hash = ? WHERE name = ?",
        (_hash_password(new_password), name),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/passkeys")
def list_passkeys(request: Request, member_name: Optional[str] = None):
    name = require_auth(request)
    if member_name and member_name != name:
        require_admin(request)
        name = member_name
    conn = get_db()
    rows = conn.execute(
        "SELECT id, credential_id, sign_count, transports, created_at, last_used_at FROM passkeys WHERE member_name = ? ORDER BY created_at DESC",
        (name,)
    ).fetchall()
    conn.close()
    return {"passkeys": [dict(r) for r in rows]}


@router.delete("/passkeys/{passkey_id}")
def delete_passkey(request: Request, passkey_id: int):
    name = require_auth(request)
    conn = get_db()
    row = conn.execute(
        "SELECT member_name FROM passkeys WHERE id = ?", (passkey_id,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Passkey not found")
    if row["member_name"] != name:
        conn.close()
        raise HTTPException(status_code=403, detail="Can only delete your own passkeys")
    conn.execute("DELETE FROM passkeys WHERE id = ?", (passkey_id,))
    conn.commit()
    conn.close()
    return {"ok": True}
