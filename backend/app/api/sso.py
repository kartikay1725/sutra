from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.dependencies import get_current_user
from app.models.user import User

router = APIRouter(tags=["sso"])

class SSOProvider(BaseModel):
    id: str
    name: str
    type: str  # e.g., "saml", "oidc"
    domain: str
    is_active: bool

class SSOCallbackRequest(BaseModel):
    provider_id: str
    code: str
    state: str

class SSOCallbackResponse(BaseModel):
    token: str
    user_id: str

def _mock_sso_providers() -> List[SSOProvider]:
    return [
        SSOProvider(
            id="sso-1",
            name="Okta Workforce",
            type="oidc",
            domain="acme.okta.com",
            is_active=True,
        ),
        SSOProvider(
            id="sso-2",
            name="Azure AD",
            type="saml",
            domain="login.microsoftonline.com",
            is_active=False,
        ),
    ]

@router.get("/v1/organizations/{org_id}/sso/providers", response_model=List[SSOProvider])
def get_sso_providers(
    org_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Fetch configured SSO providers for an organization.
    """
    return _mock_sso_providers()

@router.post("/v1/auth/sso/callback", response_model=SSOCallbackResponse)
def handle_sso_callback(
    payload: SSOCallbackRequest,
):
    """
    Handle the callback from an external IdP (Identity Provider).
    SSO is disabled for Beta and marked Coming Soon.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Single Sign-On (SSO) is coming soon for Beta.",
    )
