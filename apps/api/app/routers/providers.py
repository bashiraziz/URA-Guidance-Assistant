"""CRUD endpoints for user LLM provider keys (BYOK)."""
from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user_id
from app.config import Settings, get_settings
from app.db import get_session
from app.services.providers import encrypt_api_key, decrypt_api_key

router = APIRouter(prefix="/v1/user/providers", tags=["providers"])

VALID_PROVIDERS = {"gemini", "anthropic", "openai"}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ProviderOut(BaseModel):
    provider: str
    masked_key: str
    model_name: str | None = None


class ProviderSaveRequest(BaseModel):
    api_key: str = Field(min_length=1, max_length=512)
    model_name: str | None = None


class ProviderTestResult(BaseModel):
    ok: bool
    detail: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mask_key(raw: str) -> str:
    if len(raw) <= 8:
        return raw[:2] + "..." + raw[-2:]
    return raw[:4] + "..." + raw[-4:]


def _validate_provider_name(name: str) -> None:
    if name not in VALID_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid provider '{name}'. Must be one of: {', '.join(sorted(VALID_PROVIDERS))}",
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=list[ProviderOut])
async def list_providers(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> list[ProviderOut]:
    if user_id.startswith("guest:"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Guests cannot configure providers.")

    rows = (
        await session.execute(
            text("SELECT provider, api_key_encrypted, model_name FROM user_providers WHERE user_id = :user_id ORDER BY provider"),
            {"user_id": user_id},
        )
    ).mappings().all()

    result: list[ProviderOut] = []
    for row in rows:
        try:
            raw_key = decrypt_api_key(settings, row["api_key_encrypted"])
            masked = _mask_key(raw_key)
        except Exception:
            masked = "***"
        result.append(ProviderOut(provider=row["provider"], masked_key=masked, model_name=row["model_name"]))
    return result


@router.put("/{name}", response_model=ProviderOut)
async def save_provider(
    name: str,
    body: ProviderSaveRequest,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> ProviderOut:
    _validate_provider_name(name)
    if user_id.startswith("guest:"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Guests cannot configure providers.")

    encrypted = encrypt_api_key(settings, body.api_key)
    async with session.begin():
        await session.execute(
            text(
                """
                INSERT INTO user_providers (user_id, provider, api_key_encrypted, model_name)
                VALUES (:user_id, :provider, :api_key_encrypted, :model_name)
                ON CONFLICT (user_id, provider) DO UPDATE SET
                  api_key_encrypted = EXCLUDED.api_key_encrypted,
                  model_name = EXCLUDED.model_name,
                  updated_at = NOW()
                """
            ),
            {
                "user_id": user_id,
                "provider": name,
                "api_key_encrypted": encrypted,
                "model_name": body.model_name,
            },
        )
    await session.commit()
    return ProviderOut(provider=name, masked_key=_mask_key(body.api_key), model_name=body.model_name)


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_provider(
    name: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> None:
    _validate_provider_name(name)
    if user_id.startswith("guest:"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Guests cannot configure providers.")

    async with session.begin():
        result = await session.execute(
            text("DELETE FROM user_providers WHERE user_id = :user_id AND provider = :provider"),
            {"user_id": user_id, "provider": name},
        )
    await session.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found.")


@router.post("/{name}/test", response_model=ProviderTestResult)
async def test_provider(
    name: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> ProviderTestResult:
    _validate_provider_name(name)
    if user_id.startswith("guest:"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Guests cannot configure providers.")

    row = (
        await session.execute(
            text("SELECT api_key_encrypted, model_name FROM user_providers WHERE user_id = :user_id AND provider = :provider"),
            {"user_id": user_id, "provider": name},
        )
    ).mappings().first()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found. Save a key first.")

    try:
        api_key = decrypt_api_key(settings, row["api_key_encrypted"])
    except Exception:
        return ProviderTestResult(ok=False, detail="Could not decrypt stored key. Re-save it.")

    model_name = row["model_name"]
    test_prompt = "Reply with exactly: OK"

    try:
        if name == "gemini":
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            m = genai.GenerativeModel(model_name or "gemini-1.5-flash")
            resp = m.generate_content(test_prompt)
            if resp.text:
                return ProviderTestResult(ok=True, detail="Gemini key is valid.")
            return ProviderTestResult(ok=False, detail="Gemini returned empty response.")

        elif name == "anthropic":
            from anthropic import AsyncAnthropic
            client = AsyncAnthropic(api_key=api_key)
            resp = await client.messages.create(
                model=model_name or "claude-sonnet-4-5-20250929",
                max_tokens=10,
                messages=[{"role": "user", "content": test_prompt}],
            )
            if resp.content:
                return ProviderTestResult(ok=True, detail="Anthropic key is valid.")
            return ProviderTestResult(ok=False, detail="Anthropic returned empty response.")

        elif name == "openai":
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=api_key)
            resp = await client.chat.completions.create(
                model=model_name or "gpt-4o-mini",
                max_tokens=10,
                messages=[{"role": "user", "content": test_prompt}],
            )
            if resp.choices:
                return ProviderTestResult(ok=True, detail="OpenAI key is valid.")
            return ProviderTestResult(ok=False, detail="OpenAI returned empty response.")

    except Exception as exc:
        return ProviderTestResult(ok=False, detail=f"Key validation failed: {exc}")

    return ProviderTestResult(ok=False, detail="Unknown provider.")
