"""OAuth 2.1 Authorization Server & Protected Resource Metadata Endpoints.

Implements RFC 8414 (OAuth 2.0 Authorization Server Metadata),
RFC 9728 (OAuth 2.0 Protected Resource Metadata) for MCP clients (Cursor,
Claude Desktop, Claude Code, Windsurf, CLI), along with PKCE authorization code exchange,
real browser login, and explicit human consent.
"""
from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import html
import hashlib
import json
import logging
import os
import secrets
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlencode, urlparse

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.agent_dependencies import create_agent_session
from app.api.dependencies import get_current_user_optional
from app.core.config import CANONICAL_PRODUCTION_API_URL, settings
from app.core.redis_service import redis_service
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.user import User
from app.models.user_session import UserSession

logger = logging.getLogger("sutra.oauth")

router = APIRouter(tags=["oauth"])


def verify_code_challenge(verifier: str, challenge: str, method: str = "S256") -> bool:
    """Verify PKCE code_verifier against stored code_challenge."""
    if method == "S256":
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        computed = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
        return secrets.compare_digest(computed, challenge)
    elif method in ("plain", ""):
        return secrets.compare_digest(verifier, challenge)
    return False


def resolve_client_name(client_id: str) -> str:
    """Resolve a human-readable client name from client_id or cached registration."""
    try:
        cached = redis_service.get(f"oauth_client:{client_id}")
        if cached and isinstance(cached, dict) and cached.get("client_name"):
            return cached["client_name"]
    except Exception:
        pass

    known = {
        "cursor": "Cursor",
        "claude-desktop": "Claude Desktop",
        "claude-code": "Claude Code",
        "claude": "Claude",
        "windsurf": "Windsurf",
        "sutra-mcp-client": "SUTRA MCP Client",
    }
    lowered = client_id.lower()
    for k, v in known.items():
        if k in lowered:
            return v
    return client_id


# =========================================================================
# RFC 8414 & RFC 9728 METADATA DISCOVERY
# =========================================================================

@router.get("/.well-known/oauth-authorization-server")
def get_oauth_authorization_server_metadata(request: Request) -> Dict[str, Any]:
    """RFC 8414: OAuth 2.0 Authorization Server Metadata."""
    base_url = settings.get_public_api_url(request)
    return {
        "issuer": base_url,
        "authorization_endpoint": f"{base_url}/oauth/authorize",
        "token_endpoint": f"{base_url}/oauth/token",
        "revocation_endpoint": f"{base_url}/oauth/revoke",
        "registration_endpoint": f"{base_url}/oauth/register",
        "token_endpoint_auth_methods_supported": ["client_secret_basic", "client_secret_post", "none"],
        "revocation_endpoint_auth_methods_supported": ["none", "client_secret_basic", "client_secret_post"],
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "scopes_supported": ["sutra:agent", "repo:read", "repo:write"],
        "service_documentation": f"{base_url}/docs",
        "logo_uri": f"{base_url}/icon.png",
        "client_id_metadata_document_supported": True,
        "authorization_response_iss_parameter_supported": True,
    }


@router.get("/.well-known/oauth-protected-resource")
@router.get("/.well-known/oauth-protected-resource/v1/mcp")
@router.get("/v1/mcp/.well-known/oauth-protected-resource")
def get_oauth_protected_resource_metadata(request: Request) -> Dict[str, Any]:
    """RFC 9728: OAuth 2.0 Protected Resource Metadata."""
    base_url = settings.get_public_api_url(request)
    return {
        "resource": f"{base_url}/v1/mcp",
        "authorization_servers": [base_url],
        "scopes_supported": ["sutra:agent"],
        "bearer_methods_supported": ["header"],
        "resource_documentation": f"{base_url}/docs",
        "logo_uri": f"{base_url}/icon.png",
        "resource_icon": f"{base_url}/icon.png",
    }


# =========================================================================
# RFC 7591 DYNAMIC CLIENT REGISTRATION (BACKWARD COMPATIBLE FALLBACK)
# =========================================================================

@router.post("/oauth/register", status_code=status.HTTP_201_CREATED)
async def register_client_endpoint(request: Request) -> JSONResponse:
    """RFC 7591 Dynamic Client Registration endpoint (fallback when CIMD is not used)."""
    try:
        data = await request.json()
    except Exception:
        data = {}

    client_id = f"sutra_client_{secrets.token_urlsafe(16)}"
    redirect_uris = data.get("redirect_uris", [])
    client_name = data.get("client_name", "MCP Coding Client")

    client_info = {
        "client_id": client_id,
        "client_name": client_name,
        "redirect_uris": redirect_uris,
        "token_endpoint_auth_method": data.get("token_endpoint_auth_method", "none"),
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
    }
    try:
        redis_service.set(f"oauth_client:{client_id}", client_info, ex=86400 * 90)
    except Exception as e:
        logger.warning(f"Failed to cache registered client: {e}")

    return JSONResponse(content=client_info, status_code=status.HTTP_201_CREATED)


@router.get("/favicon.ico", include_in_schema=False)
def get_sutra_favicon():
    """Serve official SUTRA favicon.ico for browser tabs and clients."""
    static_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "static", "favicon.ico"))
    if os.path.exists(static_path):
        return FileResponse(static_path, media_type="image/x-icon")
    frontend_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "frontend", "public", "favicon.ico"))
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path, media_type="image/x-icon")
    return Response(status_code=404)


@router.get("/icon.png", include_in_schema=False)
@router.get("/static/icon.png", include_in_schema=False)
@router.get("/apple-touch-icon.png", include_in_schema=False)
@router.get("/logo-s.png", include_in_schema=False)
def get_sutra_icon():
    """Serve official SUTRA icon for OAuth login, consent, and metadata pages."""
    static_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "static", "icon.png"))
    if os.path.exists(static_path):
        return FileResponse(static_path, media_type="image/png")
    frontend_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "frontend", "public", "icon.png"))
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path, media_type="image/png")
    return Response(status_code=404)


# =========================================================================
# HTML UI TEMPLATES (LOGIN, CONSENT, CALLBACK)
# =========================================================================

_BASE_CSS = """
:root {
  --bg: #0B0B0F;
  --surface-1: #111418;
  --surface-2: #161B22;
  --surface-hover: #1C2128;
  --border: #202632;
  --border-subtle: #2D333B;
  --border-focus: #F97316;
  --text-primary: #F0F6FC;
  --text-secondary: #C9D1D9;
  --text-muted: #8B949E;
  --accent: #F97316;
  --accent-hover: #FB8C24;
  --accent-active: #EA580C;
  --blue: #3B82F6;
  --blue-subtle: rgba(59, 130, 246, 0.12);
  --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Inter", sans-serif;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: #0B0B0F radial-gradient(circle at 50% 25%, #181E28 0%, #0B0B0F 80%);
  color: var(--text-primary);
  font-family: var(--font);
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px 16px;
}
.card {
  width: 100%;
  max-width: 450px;
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 34px 30px;
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.7), 0 0 0 1px rgba(255, 255, 255, 0.04);
}
.auth-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 17px;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--text-primary);
  margin-bottom: 20px;
}
.badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 9px;
  border-radius: 4px;
  font-size: 10.5px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  background: rgba(249, 115, 22, 0.1);
  border: 1px solid rgba(249, 115, 22, 0.25);
  color: var(--accent);
  margin-bottom: 12px;
}
.badge.blue {
  background: rgba(59, 130, 246, 0.1);
  border: 1px solid rgba(59, 130, 246, 0.25);
  color: #60A5FA;
}
.badge-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
}
h1 { font-size: 21px; font-weight: 700; color: var(--text-primary); margin-bottom: 6px; letter-spacing: -0.02em; }
p.sub { font-size: 13px; color: var(--text-muted); line-height: 1.55; margin-bottom: 22px; }
p.sub strong { color: var(--text-primary); font-weight: 600; }
.field { margin-bottom: 16px; }
label {
  display: block;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  margin-bottom: 6px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
input {
  width: 100%;
  height: 42px;
  background: var(--surface-2);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 0 14px;
  color: var(--text-primary);
  font-size: 13.5px;
  font-family: inherit;
  outline: none;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
input:focus {
  border-color: var(--border-focus);
  box-shadow: 0 0 0 2px rgba(249, 115, 22, 0.2);
}
input:-webkit-autofill,
input:-webkit-autofill:hover, 
input:-webkit-autofill:focus,
input:-webkit-autofill:active {
  -webkit-text-fill-color: #F0F6FC !important;
  -webkit-box-shadow: 0 0 0px 1000px #161B22 inset !important;
  box-shadow: 0 0 0px 1000px #161B22 inset !important;
  transition: background-color 5000s ease-in-out 0s;
}
.password-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}
.password-wrapper input {
  padding-right: 40px;
}
.toggle-pw-btn {
  position: absolute;
  right: 10px;
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4px;
  border-radius: 4px;
  transition: color 0.15s ease;
}
.toggle-pw-btn:hover {
  color: var(--text-primary);
}
.error-box {
  background: rgba(249, 115, 22, 0.08);
  border: 1px solid rgba(249, 115, 22, 0.3);
  color: #FB923C;
  font-size: 12.5px;
  padding: 10px 14px;
  border-radius: 8px;
  margin-bottom: 18px;
  line-height: 1.5;
}
.scope-list {
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px 18px;
  margin-bottom: 24px;
}
.scope-item { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 14px; font-size: 13px; }
.scope-item:last-child { margin-bottom: 0; }
.scope-icon { color: var(--blue); font-weight: bold; margin-top: 1px; flex-shrink: 0; font-size: 14px; }
.scope-text strong { color: var(--text-primary); display: block; margin-bottom: 3px; font-size: 13px; font-weight: 600; }
.scope-text span { color: var(--text-muted); font-size: 12px; line-height: 1.5; display: block; }
.user-badge {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 8px;
  margin-bottom: 20px;
  font-size: 13px;
}
.user-avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: rgba(249, 115, 22, 0.12);
  border: 1px solid rgba(249, 115, 22, 0.28);
  color: var(--accent);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 13px;
  flex-shrink: 0;
}
.actions { display: flex; gap: 12px; }
.btn {
  flex: 1;
  height: 42px;
  border-radius: 8px;
  font-size: 13.5px;
  font-weight: 600;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
  user-select: none;
  text-decoration: none;
}
.btn-primary {
  background: var(--accent);
  color: #FFFFFF;
  border: 1px solid var(--accent-active);
  box-shadow: 0 2px 10px rgba(249, 115, 22, 0.25);
}
.btn-primary:hover {
  background: var(--accent-hover);
  box-shadow: 0 4px 14px rgba(249, 115, 22, 0.35);
  transform: translateY(-1px);
}
.btn-primary:active {
  transform: scale(0.99);
  background: var(--accent-active);
}
.btn-secondary {
  background: var(--surface-2);
  color: var(--text-secondary);
  border: 1px solid var(--border-subtle);
}
.btn-secondary:hover {
  background: var(--surface-hover);
  border-color: #38414D;
  color: #FFFFFF;
}
"""


def _render_login_html(
    client_id: str,
    client_name: str,
    redirect_uri: str,
    code_challenge: str,
    code_challenge_method: str,
    state: Optional[str],
    scope: str,
    error: Optional[str] = None,
) -> str:
    err_html = f'<div class="error-box">{html.escape(error)}</div>' if error else ""
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Sign in to SUTRA</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" type="image/png" href="/icon.png">
  <link rel="shortcut icon" href="/favicon.ico">
  <link rel="apple-touch-icon" href="/icon.png">
  <style>{_BASE_CSS}</style>
</head>
<body>
  <div class="card">
    <div class="auth-brand">
      <img src="/icon.png" alt="SUTRA" width="32" height="32" style="width: 32px; height: 32px; object-fit: contain; border-radius: 8px; flex-shrink: 0; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);">
      <span>SUTRA</span>
    </div>
    <div class="badge"><span class="badge-dot"></span>SUTRA Governance Control Plane</div>
    <h1>Sign In to Authorize</h1>
    <p class="sub"><strong>{html.escape(client_name)}</strong> is requesting connection to SUTRA. Please sign in to approve access.</p>
    {err_html}
    <form method="POST" action="/oauth/authorize">
      <input type="hidden" name="login_action" value="login">
      <input type="hidden" name="client_id" value="{html.escape(client_id)}">
      <input type="hidden" name="redirect_uri" value="{html.escape(redirect_uri)}">
      <input type="hidden" name="response_type" value="code">
      <input type="hidden" name="code_challenge" value="{html.escape(code_challenge)}">
      <input type="hidden" name="code_challenge_method" value="{html.escape(code_challenge_method)}">
      <input type="hidden" name="scope" value="{html.escape(scope)}">
      <input type="hidden" name="state" value="{html.escape(state or '')}">

      <div class="field">
        <label>Username or Email</label>
        <input type="text" name="login" required autofocus autocomplete="username" placeholder="developer@example.com">
      </div>
      <div class="field">
        <label>Password</label>
        <div class="password-wrapper">
          <input type="password" id="password-input" name="password" required autocomplete="current-password" placeholder="••••••••••••">
          <button type="button" class="toggle-pw-btn" onclick="togglePassword()" aria-label="Toggle password visibility">
            <svg id="eye-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
              <circle cx="12" cy="12" r="3"></circle>
            </svg>
          </button>
        </div>
      </div>
      <div style="margin-top: 24px;">
        <button type="submit" class="btn btn-primary" style="width: 100%;">Sign In & Continue</button>
      </div>
    </form>
  </div>
  <script>
    function togglePassword() {{
      var input = document.getElementById('password-input');
      var icon = document.getElementById('eye-icon');
      if (input.type === 'password') {{
        input.type = 'text';
        icon.innerHTML = '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line>';
      }} else {{
        input.type = 'password';
        icon.innerHTML = '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle>';
      }}
    }}
  </script>
</body>
</html>"""


def _render_consent_html(
    client_id: str,
    client_name: str,
    redirect_uri: str,
    code_challenge: str,
    code_challenge_method: str,
    state: Optional[str],
    scope: str,
    username: str,
    email: str,
) -> str:
    initial = (username[:1] or "U").upper()
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Connect {html.escape(client_name)} to SUTRA</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" type="image/png" href="/icon.png">
  <link rel="shortcut icon" href="/favicon.ico">
  <link rel="apple-touch-icon" href="/icon.png">
  <style>{_BASE_CSS}</style>
</head>
<body>
  <div class="card">
    <div class="auth-brand">
      <img src="/icon.png" alt="SUTRA" width="32" height="32" style="width: 32px; height: 32px; object-fit: contain; border-radius: 8px; flex-shrink: 0; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);">
      <span>SUTRA</span>
    </div>
    <div class="badge blue"><span class="badge-dot"></span>Model Context Protocol · OAuth 2.1</div>
    <h1>Connect {html.escape(client_name)}</h1>
    <p class="sub">Authorize <strong>{html.escape(client_name)}</strong> to act as an autonomous coding agent governed by your SUTRA control plane.</p>

    <div class="user-badge">
      <div class="user-avatar">{html.escape(initial)}</div>
      <div>
        <div style="font-weight: 700; color: var(--text-primary);">{html.escape(username)}</div>
        <div style="font-size: 12px; color: var(--text-muted);">{html.escape(email)}</div>
      </div>
    </div>

    <div class="scope-list">
      <div class="scope-item">
        <div class="scope-icon">✓</div>
        <div class="scope-text">
          <strong>Autonomous Agent Identity</strong>
          <span>Provisions a lease-bound coding identity strictly owned by your account.</span>
        </div>
      </div>
      <div class="scope-item">
        <div class="scope-icon">✓</div>
        <div class="scope-text">
          <strong>Zero-Access Default Boundary</strong>
          <span>Starts with 0 repository grants. You must explicitly authorize repositories.</span>
        </div>
      </div>
      <div class="scope-item">
        <div class="scope-icon">✓</div>
        <div class="scope-text">
          <strong>SUTRA 4-Pillar Governance</strong>
          <span>All terminal pushes, changes, and PRs require cryptographic provenance and human approval.</span>
        </div>
      </div>
    </div>

    <form method="POST" action="/oauth/authorize">
      <input type="hidden" name="client_id" value="{html.escape(client_id)}">
      <input type="hidden" name="redirect_uri" value="{html.escape(redirect_uri)}">
      <input type="hidden" name="response_type" value="code">
      <input type="hidden" name="code_challenge" value="{html.escape(code_challenge)}">
      <input type="hidden" name="code_challenge_method" value="{html.escape(code_challenge_method)}">
      <input type="hidden" name="scope" value="{html.escape(scope)}">
      <input type="hidden" name="state" value="{html.escape(state or '')}">

      <div class="actions">
        <button type="submit" name="action" value="cancel" class="btn btn-secondary">Cancel</button>
        <button type="submit" name="action" value="approve" class="btn btn-primary">Approve</button>
      </div>
    </form>
  </div>
</body>
</html>"""


def _render_callback_html(
    title: str,
    message: str,
    is_success: bool = True,
    client_name: Optional[str] = None,
) -> str:
    badge_class = "badge blue" if is_success else "badge"
    badge_label = "Connected · OAuth 2.1" if is_success else ("Cancelled" if "Denied" in title or "Cancel" in title else "OAuth Error")

    if is_success:
        icon_svg = """<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#60A5FA" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
          <polyline points="22 4 12 14.01 9 11.01"></polyline>
        </svg>"""
        icon_bg = "rgba(59, 130, 246, 0.12)"
        icon_border = "rgba(59, 130, 246, 0.3)"
    else:
        icon_svg = """<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#F97316" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="15" y1="9" x2="9" y2="15"></line>
          <line x1="9" y1="9" x2="15" y2="15"></line>
        </svg>"""
        icon_bg = "rgba(249, 115, 22, 0.12)"
        icon_border = "rgba(249, 115, 22, 0.3)"

    client_chip = (
        f'<div style="display: inline-flex; align-items: center; gap: 8px; padding: 6px 12px; border-radius: 6px; background: var(--surface-2); border: 1px solid var(--border); margin-bottom: 16px; font-size: 12.5px; color: var(--text-primary);">'
        f'<span style="width: 6px; height: 6px; border-radius: 50%; background: #60A5FA;"></span>'
        f'<span><strong>{html.escape(client_name)}</strong> authorization code issued</span>'
        f'</div>'
    ) if client_name else ""

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)} — SUTRA</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" type="image/png" href="/icon.png">
  <link rel="shortcut icon" href="/favicon.ico">
  <link rel="apple-touch-icon" href="/icon.png">
  <style>{_BASE_CSS}</style>
</head>
<body>
  <div class="card" style="text-align: center;">
    <div class="auth-brand" style="justify-content: center; margin-bottom: 22px;">
      <img src="/icon.png" alt="SUTRA" width="32" height="32" style="width: 32px; height: 32px; object-fit: contain; border-radius: 8px; flex-shrink: 0; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);">
      <span>SUTRA</span>
    </div>

    <div style="width: 56px; height: 56px; border-radius: 50%; background: {icon_bg}; border: 1px solid {icon_border}; display: flex; align-items: center; justify-content: center; margin: 0 auto 16px auto;">
      {icon_svg}
    </div>

    <div class="{badge_class}"><span class="badge-dot"></span>{badge_label}</div>

    <h1 style="margin-top: 4px; margin-bottom: 10px;">{html.escape(title)}</h1>
    {client_chip}
    <p class="sub" style="margin-bottom: 24px;">{html.escape(message)}</p>

    <div style="padding: 14px 16px; border-radius: 8px; background: var(--surface-2); border: 1px solid var(--border); margin-bottom: 24px; font-size: 12.5px; color: var(--text-secondary); line-height: 1.5;">
      You can now safely close this browser tab and return to your IDE or terminal.
    </div>

    <div class="actions">
      <button type="button" onclick="window.close()" class="btn btn-secondary">Close Tab</button>
      <a href="https://sutra.sudarshanai.com/" class="btn btn-primary" style="text-decoration: none;">Return to SUTRA</a>
    </div>
  </div>
</body>
</html>"""



# =========================================================================
# OAUTH AUTHORIZATION FLOW (PKCE + BROWSER LOGIN & CONSENT)
# =========================================================================

@router.get("/oauth/authorize")
@router.post("/oauth/authorize")
async def authorize_endpoint(
    request: Request,
    response: Response,
    client_id: Optional[str] = Query(None),
    redirect_uri: Optional[str] = Query(None),
    response_type: Optional[str] = Query(None),
    code_challenge: Optional[str] = Query(None),
    code_challenge_method: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    scope: Optional[str] = Query(None),
    resource: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    agent_id: Optional[str] = Query(None),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """
    OAuth 2.1 PKCE Authorize Endpoint.
    Enforces real browser authentication and explicit human consent.
    Never falls back to arbitrary or global agents.
    """
    form_data = {}
    if request.method == "POST":
        try:
            form_data = dict(await request.form())
        except Exception:
            try:
                form_data = await request.json()
            except Exception:
                form_data = {}

    # Merge form data with query params (form data takes precedence on POST)
    client_id = form_data.get("client_id") or client_id
    redirect_uri = form_data.get("redirect_uri") or redirect_uri
    response_type = form_data.get("response_type") or response_type or "code"
    code_challenge = form_data.get("code_challenge") or code_challenge
    code_challenge_method = form_data.get("code_challenge_method") or code_challenge_method or "S256"
    state = form_data.get("state") or state
    scope = form_data.get("scope") or scope or "sutra:agent"
    resource = form_data.get("resource") or resource
    agent_id = form_data.get("agent_id") or agent_id
    submitted_action = form_data.get("action") or action
    login_action = form_data.get("login_action")

    # Validate required OAuth params
    if not client_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing client_id")
    # Default redirect_uri to canonical production callback if omitted
    if not redirect_uri:
        redirect_uri = f"{CANONICAL_PRODUCTION_API_URL}/oauth/callback"
    if not code_challenge:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing code_challenge")
    if response_type != "code":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported response_type. Only 'code' is supported.")
    if code_challenge_method != "S256":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported code_challenge_method. Only 'S256' is permitted under OAuth 2.1.")

    if not redirect_uri.startswith("http://") and not redirect_uri.startswith("https://"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid redirect_uri. Must be an HTTP or HTTPS URI.")

    client_name = resolve_client_name(client_id)

    # 1. Handle Login Form Submission
    if login_action == "login":
        login_val = (form_data.get("login") or "").strip()
        password_val = form_data.get("password") or ""
        user = db.scalar(
            select(User).where(or_(User.username == login_val, User.email == login_val.lower()))
        )
        if not user or not verify_password(password_val, user.password_hash):
            html_content = _render_login_html(
                client_id=client_id,
                client_name=client_name,
                redirect_uri=redirect_uri,
                code_challenge=code_challenge,
                code_challenge_method=code_challenge_method,
                state=state,
                scope=scope,
                error="Invalid username/email or password.",
            )
            return HTMLResponse(content=html_content, status_code=401)

        if not user.email_verified:
            html_content = _render_login_html(
                client_id=client_id,
                client_name=client_name,
                redirect_uri=redirect_uri,
                code_challenge=code_challenge,
                code_challenge_method=code_challenge_method,
                state=state,
                scope=scope,
                error="Please verify your email address before continuing.",
            )
            return HTMLResponse(content=html_content, status_code=403)

        # Create session and set cookie
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
        user_session = UserSession(user_id=user.id, expires_at=expires_at)
        db.add(user_session)
        db.commit()
        db.refresh(user_session)

        raw_token = create_access_token(user.id, user_session.id)
        consent_html = _render_consent_html(
            client_id=client_id,
            client_name=client_name,
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            state=state,
            scope=scope,
            username=user.username,
            email=user.email,
        )
        resp = HTMLResponse(content=consent_html)
        resp.set_cookie(
            key="sutra_session",
            value=raw_token,
            httponly=True,
            samesite="lax",
            secure=False if settings.debug and settings.app_env == "development" else True,
            max_age=settings.access_token_expire_minutes * 60,
            path="/",
        )
        return resp

    # 2. If User is NOT Authenticated -> Render SUTRA Login Page
    if not current_user:
        html_content = _render_login_html(
            client_id=client_id,
            client_name=client_name,
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            state=state,
            scope=scope,
        )
        return HTMLResponse(content=html_content)

    # 3. User is Authenticated -> Handle Explicit Actions (Cancel vs Approve)
    if submitted_action == "cancel":
        # RFC 6749 Access Denied
        params = {"error": "access_denied", "error_description": "User cancelled authorization"}
        if state:
            params["state"] = state
        target_url = f"{redirect_uri}{'&' if '?' in redirect_uri else '?'}{urlencode(params)}"
        return RedirectResponse(url=target_url, status_code=status.HTTP_302_FOUND)

    if submitted_action == "approve":
        # Resolve Agent belonging strictly and exclusively to current_user
        agent = None
        if agent_id:
            # If client/user specified an agent, it MUST belong to current_user and be active
            agent = db.scalar(
                select(Agent).where(
                    Agent.id == agent_id,
                    Agent.owner_id == current_user.id,
                    Agent.is_active.is_(True),
                    Agent.status == "active",
                )
            )
            if not agent:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Requested agent does not exist or does not belong to the authenticated user.",
                )

        if not agent:
            # Deterministically create or reuse an Agent belonging exclusively to current_user
            agent_name = f"MCP ({client_name})"
            agent = db.scalar(
                select(Agent).where(
                    Agent.owner_id == current_user.id,
                    Agent.name == agent_name,
                    Agent.is_active.is_(True),
                    Agent.status == "active",
                )
            )
            if not agent:
                raw_token = f"sutra_agent_{secrets.token_urlsafe(32)}"
                agent = Agent(
                    owner_id=current_user.id,
                    name=agent_name,
                    description=f"Auto-provisioned agent for {client_name} MCP integration",
                    token_hash=hash_password(raw_token),
                    token_prefix=raw_token[:16],
                    status="active",
                    is_active=True,
                )
                db.add(agent)
                db.flush()

                actor = Actor(
                    id=agent.id,
                    owner_id=current_user.id,
                    type="agent",
                    name=agent.name,
                    capabilities=json.dumps([
                        "repository.read",
                        "repository.write",
                        "change.create",
                        "change.commit",
                        "change.conflict.read",
                        "knowledge_graph.read",
                    ]),
                )
                db.add(actor)
                db.commit()
                db.refresh(agent)

        # Issue authorization code bound strictly to the human user and their agent
        code = f"sutra_auth_code_{secrets.token_urlsafe(32)}"
        code_data = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method,
            "scope": scope,
            "resource": resource,
            "agent_id": agent.id,
            "user_id": current_user.id,
            "state": state,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            redis_service.set(f"oauth_code:{code}", code_data, ex=600)
        except Exception as e:
            logger.warning(f"Failed to store auth code in Redis: {e}")

        # Build redirect URL with RFC 9207 iss parameter
        base_url = settings.get_public_api_url(request)
        params = {"code": code, "iss": base_url}
        if state:
            params["state"] = state

        target_url = f"{redirect_uri}{'&' if '?' in redirect_uri else '?'}{urlencode(params)}"
        return RedirectResponse(url=target_url, status_code=status.HTTP_302_FOUND)

    # 4. User is Authenticated, no action submitted yet -> Display Consent Screen
    consent_html = _render_consent_html(
        client_id=client_id,
        client_name=client_name,
        redirect_uri=redirect_uri,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
        state=state,
        scope=scope,
        username=current_user.username,
        email=current_user.email,
    )
    return HTMLResponse(content=consent_html)


# =========================================================================
# TOKEN EXCHANGE (AUTHORIZATION CODE & REFRESH TOKEN)
# =========================================================================

@router.post("/oauth/token")
async def token_endpoint(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    OAuth 2.1 Token Exchange Endpoint.
    Exchanges authorization code for an authoritative SUTRA MCP Access Token.
    Strictly verifies user ownership. Never falls back to arbitrary agents.
    """
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        data = await request.json()
    else:
        form = await request.form()
        data = dict(form)

    grant_type = data.get("grant_type")

    # 1. Authorization Code Grant
    if grant_type == "authorization_code":
        code = data.get("code")
        code_verifier = data.get("code_verifier")
        req_client_id = data.get("client_id")
        req_redirect_uri = data.get("redirect_uri")

        if not code or not code_verifier:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing 'code' or 'code_verifier' in request",
            )

        cached_code = None
        try:
            cached_code = redis_service.get(f"oauth_code:{code}")
        except Exception as e:
            logger.warning(f"Redis get failed: {e}")

        if not cached_code or not isinstance(cached_code, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired authorization code",
            )

        # Enforce client_id consistency if provided
        if req_client_id and req_client_id != cached_code.get("client_id"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Client ID mismatch for authorization code",
            )

        # Enforce redirect_uri consistency if provided
        if req_redirect_uri and req_redirect_uri != cached_code.get("redirect_uri"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="redirect_uri mismatch for authorization code",
            )

        # Verify PKCE
        stored_challenge = cached_code.get("code_challenge", "")
        stored_method = cached_code.get("code_challenge_method", "S256")
        if not verify_code_challenge(code_verifier, stored_challenge, stored_method):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="PKCE code_verifier verification failed",
            )

        # Invalidate code immediately (single use)
        try:
            redis_service.delete(f"oauth_code:{code}")
        except Exception:
            pass

        # Strictly resolve agent and user bound to authorization code (FAIL CLOSED)
        agent_id = cached_code.get("agent_id")
        user_id = cached_code.get("user_id")
        if not agent_id or not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Authorization code has no bound agent or user identity",
            )

        agent = db.scalar(
            select(Agent).where(
                Agent.id == agent_id,
                Agent.owner_id == user_id,
                Agent.is_active.is_(True),
                Agent.status == "active",
            )
        )
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Agent bound to authorization code is inactive, revoked, or not owned by authorizing user",
            )

        # Create authoritative SUTRA AgentSession
        session, raw_session_token = create_agent_session(agent, db)

        # Generate OAuth Access Token and Refresh Token
        access_token = f"sutra_mcp_at_{secrets.token_urlsafe(32)}"
        refresh_token = f"sutra_mcp_rt_{secrets.token_urlsafe(32)}"

        # Cache token binding in Redis
        token_prefix = access_token[:32]
        token_data = {
            "agent_id": agent.id,
            "user_id": user_id,
            "session_id": session.id,
            "raw_session_token": raw_session_token,
            "scope": cached_code.get("scope", "sutra:agent"),
            "resource": cached_code.get("resource"),
            "client_id": cached_code.get("client_id"),
        }
        rt_data = {
            "agent_id": agent.id,
            "user_id": user_id,
            "scope": cached_code.get("scope", "sutra:agent"),
            "resource": cached_code.get("resource"),
            "client_id": cached_code.get("client_id"),
        }

        try:
            redis_service.set(f"mcp_oauth:{token_prefix}", token_data, ex=900)
            redis_service.set(f"mcp_oauth_rt:{refresh_token}", rt_data, ex=86400 * 30)
        except Exception as e:
            logger.warning(f"Failed to cache OAuth token in Redis: {e}")

        return {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 900,
            "refresh_token": refresh_token,
            "scope": cached_code.get("scope", "sutra:agent"),
        }

    # 2. Refresh Token Grant
    elif grant_type == "refresh_token":
        rt = data.get("refresh_token")
        if not rt:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing 'refresh_token' parameter",
            )

        rt_data = None
        try:
            rt_data = redis_service.get(f"mcp_oauth_rt:{rt}")
        except Exception as e:
            logger.warning(f"Redis get failed for refresh token: {e}")

        if not rt_data or not isinstance(rt_data, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired refresh token",
            )

        agent_id = rt_data.get("agent_id")
        user_id = rt_data.get("user_id")
        agent = db.scalar(
            select(Agent).where(
                Agent.id == agent_id,
                Agent.owner_id == user_id,
                Agent.is_active.is_(True),
                Agent.status == "active",
            )
        )
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Agent associated with refresh token is inactive or revoked",
            )

        session, raw_session_token = create_agent_session(agent, db)
        new_access_token = f"sutra_mcp_at_{secrets.token_urlsafe(32)}"
        token_prefix = new_access_token[:32]

        token_data = {
            "agent_id": agent.id,
            "user_id": user_id,
            "session_id": session.id,
            "raw_session_token": raw_session_token,
            "scope": rt_data.get("scope", "sutra:agent"),
            "resource": rt_data.get("resource"),
            "client_id": rt_data.get("client_id"),
        }

        try:
            redis_service.set(f"mcp_oauth:{token_prefix}", token_data, ex=900)
        except Exception as e:
            logger.warning(f"Failed to cache rotated OAuth token: {e}")

        return {
            "access_token": new_access_token,
            "token_type": "Bearer",
            "expires_in": 900,
            "scope": rt_data.get("scope", "sutra:agent"),
        }

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported grant_type '{grant_type}'. Only 'authorization_code' and 'refresh_token' are supported.",
        )


# =========================================================================
# OAUTH BROWSER CALLBACK LANDING
# =========================================================================

@router.get("/oauth/callback")
def oauth_callback_endpoint(
    request: Request,
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
):
    """
    Browser landing page for OAuth redirects.
    Validates state and code existence without falsely claiming MCP connection completion.
    """
    if error:
        desc = error_description or "The authorization request was cancelled or failed."
        html_content = _render_callback_html(
            title="Authorization Denied",
            message=desc,
            is_success=False,
        )
        return HTMLResponse(content=html_content, status_code=200)

    if not code:
        html_content = _render_callback_html(
            title="OAuth Error",
            message="Missing required authorization code parameter.",
            is_success=False,
        )
        return HTMLResponse(content=html_content, status_code=400)

    if not state:
        html_content = _render_callback_html(
            title="OAuth Error",
            message="Missing required state parameter. Authorization request cannot be verified.",
            is_success=False,
        )
        return HTMLResponse(content=html_content, status_code=400)

    # Validate that code actually exists in Redis (issued by SUTRA)
    code_data = None
    try:
        code_data = redis_service.get(f"oauth_code:{code}")
    except Exception as e:
        logger.warning(f"Error querying redis for oauth code: {e}")

    if not code_data or not isinstance(code_data, dict):
        html_content = _render_callback_html(
            title="Invalid or Expired Code",
            message="The authorization code is invalid, expired, or has already been used.",
            is_success=False,
        )
        return HTMLResponse(content=html_content, status_code=400)

    # Validate state matches the state issued with this authorization code
    expected_state = code_data.get("state")
    if expected_state and state != expected_state:
        html_content = _render_callback_html(
            title="State Validation Failed",
            message="State parameter does not match the authorization request.",
            is_success=False,
        )
        return HTMLResponse(content=html_content, status_code=400)

    client_name = resolve_client_name(code_data.get("client_id", ""))
    html_content = _render_callback_html(
        title="Authorization Granted",
        message=f"An authorization code was successfully granted for {client_name}. To complete connection, your MCP coding client must exchange this code with /oauth/token using its PKCE verifier.",
        is_success=True,
        client_name=client_name,
    )
    return HTMLResponse(content=html_content, status_code=200)


# =========================================================================
# RFC 7009 TOKEN REVOCATION
# =========================================================================

@router.post("/oauth/revoke")
async def revoke_token_endpoint(
    request: Request,
):
    """RFC 7009 OAuth 2.0 Token Revocation."""
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        data = await request.json()
    else:
        form = await request.form()
        data = dict(form)

    token = data.get("token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing 'token' parameter to revoke",
        )

    try:
        if token.startswith("sutra_mcp_at_"):
            redis_service.delete(f"mcp_oauth:{token[:32]}")
        elif token.startswith("sutra_mcp_rt_"):
            redis_service.delete(f"mcp_oauth_rt:{token}")
    except Exception as e:
        logger.warning(f"Error during token revocation: {e}")

    return {"status": "revoked"}
