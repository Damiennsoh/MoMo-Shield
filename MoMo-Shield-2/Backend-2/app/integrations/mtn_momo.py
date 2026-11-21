import base64
import time
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, Field, field_validator

from app.config import settings


class RequestToPay(BaseModel):
    amount: str = Field(pattern=r"^(?:0|[1-9]\d{0,9})(?:\.\d{1,2})?$", max_length=13)
    currency: str = Field(min_length=3, max_length=3)
    externalId: str = Field(min_length=1, max_length=64)
    payer: dict[str, str]
    payerMessage: str = Field(default="", max_length=160)
    payeeNote: str = Field(default="", max_length=160)

    @field_validator("amount")
    @classmethod
    def require_positive_amount(cls, value: str) -> str:
        try:
            if Decimal(value) <= 0:
                raise ValueError("amount must be greater than zero")
        except InvalidOperation as error:
            raise ValueError("amount must be a valid decimal") from error
        return value

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()

    @field_validator("payer")
    @classmethod
    def validate_payer(cls, value: dict[str, str]) -> dict[str, str]:
        if value.get("partyIdType") != "MSISDN":
            raise ValueError("payer.partyIdType must be MSISDN")
        msisdn = value.get("partyId", "")
        if not msisdn.isdigit() or not 8 <= len(msisdn) <= 15:
            raise ValueError("payer.partyId must be an international MSISDN without +")
        return value


_token: str | None = None
_token_expiry = 0.0


def configured() -> bool:
    return all((settings.mtn_momo_api_user, settings.mtn_momo_api_key, settings.mtn_momo_subscription_key))


def status() -> dict[str, Any]:
    return {
        "provider": "MTN MoMo",
        "environment": "sandbox",
        "configured": configured(),
        "requestApiEnabled": bool(settings.mtn_momo_request_api_key),
        "ready": configured() and bool(settings.mtn_momo_request_api_key),
        "operations": ["RequestToPay", "RequestToPay status"],
        "webhook": "Status callbacks must be publicly reachable over HTTPS; verify final transaction state with the provider status endpoint.",
    }


async def _access_token(client: httpx.AsyncClient) -> str:
    global _token, _token_expiry
    if _token and time.monotonic() < _token_expiry:
        return _token
    credentials = base64.b64encode(
        f"{settings.mtn_momo_api_user}:{settings.mtn_momo_api_key}".encode()
    ).decode()
    try:
        response = await client.post(
            f"{settings.mtn_momo_base_url.rstrip('/')}/collection/token/",
            headers={
                "Authorization": f"Basic {credentials}",
                "Ocp-Apim-Subscription-Key": settings.mtn_momo_subscription_key,
            },
        )
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail="MTN MoMo sandbox authentication unavailable") from error
    if response.is_error:
        raise HTTPException(status_code=502, detail="MTN MoMo sandbox authentication failed")
    try:
        data = response.json()
        _token = data["access_token"]
    except (ValueError, KeyError, TypeError) as error:
        raise HTTPException(status_code=502, detail="MTN MoMo sandbox returned an invalid token response") from error
    _token_expiry = time.monotonic() + max(1, int(data.get("expires_in", 3600)) - 30)
    return _token


async def request_to_pay(payload: RequestToPay, reference_id: UUID) -> dict[str, Any]:
    if not configured():
        raise HTTPException(status_code=503, detail="MTN MoMo sandbox credentials are not configured")
    if settings.mtn_momo_callback_url:
        callback = urlparse(settings.mtn_momo_callback_url)
        if callback.scheme != "https" or not callback.netloc:
            raise HTTPException(status_code=503, detail="MTN callback URL must be an absolute HTTPS URL")
    headers = {
        "Ocp-Apim-Subscription-Key": settings.mtn_momo_subscription_key,
        "X-Target-Environment": "sandbox",
        "X-Reference-Id": str(reference_id),
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        headers["Authorization"] = f"Bearer {await _access_token(client)}"
        if settings.mtn_momo_callback_url:
            headers["X-Callback-Url"] = settings.mtn_momo_callback_url
        response = await client.post(
            f"{settings.mtn_momo_base_url.rstrip('/')}/collection/v1_0/requesttopay",
            headers=headers,
            json=payload.model_dump(by_alias=True),
        )
    if response.status_code not in (200, 202):
        raise HTTPException(status_code=502, detail="MTN MoMo sandbox rejected the payment request")
    return {"referenceId": str(reference_id), "status": "PENDING", "environment": "sandbox"}


async def get_request_status(reference_id: UUID) -> dict[str, Any]:
    if not configured():
        raise HTTPException(status_code=503, detail="MTN MoMo sandbox credentials are not configured")
    async with httpx.AsyncClient(timeout=15.0) as client:
        token = await _access_token(client)
        response = await client.get(
            f"{settings.mtn_momo_base_url.rstrip('/')}/collection/v1_0/requesttopay/{reference_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "Ocp-Apim-Subscription-Key": settings.mtn_momo_subscription_key,
                "X-Target-Environment": "sandbox",
            },
        )
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="MTN MoMo transaction not found")
    if response.is_error:
        raise HTTPException(status_code=502, detail="MTN MoMo sandbox status lookup failed")
    return response.json()
