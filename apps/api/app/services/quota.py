from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.schemas import UsageEnvelope


@dataclass
class QuotaLease:
    user_id: str
    day: str
    minute_iso: str


@dataclass
class QuotaLimits:
    daily_requests: int
    daily_output_tokens: int
    minute_requests: int


class QuotaService:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def reserve(self, session: AsyncSession, user_id: str) -> tuple[QuotaLease, UsageEnvelope]:
        from app.services.providers import has_byok_provider
        has_byok = await has_byok_provider(session, user_id)
        limits = self._resolve_limits(user_id, has_byok=has_byok)
        now = datetime.now(UTC)
        day = now.date()
        minute = now.replace(second=0, microsecond=0)

        try:
            async with session.begin():
                inflight_insert = await session.execute(
                    text(
                        """
                        INSERT INTO inflight_requests (user_id, started_at)
                        VALUES (:user_id, :started_at)
                        ON CONFLICT (user_id) DO NOTHING
                        """
                    ),
                    {"user_id": user_id, "started_at": now},
                )
                if inflight_insert.rowcount == 0:
                    self._raise_quota("You already have a request in progress. Try again in a few seconds.", retry_after=5)

                daily_row = (
                    await session.execute(
                        text(
                            """
                            INSERT INTO usage_daily (user_id, day, req_count, token_in, token_out, last_seen_at)
                            VALUES (:user_id, :day, 1, 0, 0, :now)
                            ON CONFLICT (user_id, day)
                            DO UPDATE SET
                              req_count = usage_daily.req_count + 1,
                              last_seen_at = EXCLUDED.last_seen_at
                            RETURNING req_count, token_out
                            """
                        ),
                        {"user_id": user_id, "day": day, "now": now},
                    )
                ).mappings().first()

                minute_row = (
                    await session.execute(
                        text(
                            """
                            INSERT INTO usage_minute (user_id, minute_ts, req_count)
                            VALUES (:user_id, :minute_ts, 1)
                            ON CONFLICT (user_id, minute_ts)
                            DO UPDATE SET req_count = usage_minute.req_count + 1
                            RETURNING req_count
                            """
                        ),
                        {"user_id": user_id, "minute_ts": minute},
                    )
                ).mappings().first()

                if int(daily_row["req_count"]) > limits.daily_requests:
                    seconds_until_reset = self._seconds_until_midnight()
                    self._raise_quota("Daily request limit reached for this account.", retry_after=seconds_until_reset)
                if int(daily_row["token_out"]) >= limits.daily_output_tokens:
                    seconds_until_reset = self._seconds_until_midnight()
                    self._raise_quota("Daily output token budget reached for this account.", retry_after=seconds_until_reset)
                if int(minute_row["req_count"]) > limits.minute_requests:
                    self._raise_quota("Rate limit reached. Please wait a minute and retry.", retry_after=60)

            usage = UsageEnvelope(
                daily_requests_used=int(daily_row["req_count"]),
                daily_requests_remaining=max(0, limits.daily_requests - int(daily_row["req_count"])),
                minute_requests_used=int(minute_row["req_count"]),
                minute_requests_remaining=max(0, limits.minute_requests - int(minute_row["req_count"])),
                daily_output_tokens_used=int(daily_row["token_out"]),
                daily_output_tokens_remaining=max(0, limits.daily_output_tokens - int(daily_row["token_out"])),
            )
            return QuotaLease(user_id=user_id, day=str(day), minute_iso=minute.isoformat()), usage
        except HTTPException:
            await session.rollback()
            raise

    async def finalize(
        self,
        session: AsyncSession,
        lease: QuotaLease,
        token_in: int,
        token_out: int,
    ) -> UsageEnvelope:
        from app.services.providers import has_byok_provider
        has_byok = await has_byok_provider(session, lease.user_id)
        limits = self._resolve_limits(lease.user_id, has_byok=has_byok)
        async with session.begin():
            daily_row = (
                await session.execute(
                    text(
                        """
                        UPDATE usage_daily
                        SET token_in = token_in + :token_in,
                            token_out = token_out + :token_out,
                            last_seen_at = NOW()
                        WHERE user_id = :user_id
                          AND day = CAST(:day AS DATE)
                        RETURNING req_count, token_out
                        """
                    ),
                    {"token_in": token_in, "token_out": token_out, "user_id": lease.user_id, "day": date.fromisoformat(lease.day)},
                )
            ).mappings().first()

            minute_row = (
                await session.execute(
                    text(
                        """
                        SELECT req_count
                        FROM usage_minute
                        WHERE user_id = :user_id
                          AND minute_ts = CAST(:minute_ts AS TIMESTAMPTZ)
                        """
                    ),
                    {"user_id": lease.user_id, "minute_ts": datetime.fromisoformat(lease.minute_iso)},
                )
            ).mappings().first()

            await session.execute(
                text("DELETE FROM inflight_requests WHERE user_id = :user_id"),
                {"user_id": lease.user_id},
            )

        return UsageEnvelope(
            daily_requests_used=int(daily_row["req_count"]),
            daily_requests_remaining=max(0, limits.daily_requests - int(daily_row["req_count"])),
            minute_requests_used=int(minute_row["req_count"]) if minute_row else 0,
            minute_requests_remaining=max(
                0,
                limits.minute_requests - (int(minute_row["req_count"]) if minute_row else 0),
            ),
            daily_output_tokens_used=int(daily_row["token_out"]),
            daily_output_tokens_remaining=max(0, limits.daily_output_tokens - int(daily_row["token_out"])),
        )

    async def release(self, session: AsyncSession, user_id: str) -> None:
        async with session.begin():
            await session.execute(text("DELETE FROM inflight_requests WHERE user_id = :user_id"), {"user_id": user_id})

    @staticmethod
    def _seconds_until_midnight() -> int:
        now = datetime.now(UTC)
        midnight = (now.date() + timedelta(days=1))
        midnight_dt = datetime(midnight.year, midnight.month, midnight.day, tzinfo=UTC)
        return max(60, int((midnight_dt - now).total_seconds()))

    @staticmethod
    def _raise_quota(message: str, retry_after: int) -> None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"message": message, "retry_after_seconds": retry_after},
        )

    def _resolve_limits(self, user_id: str, has_byok: bool = False) -> QuotaLimits:
        if user_id.startswith("guest:"):
            return QuotaLimits(
                daily_requests=self.settings.guest_quota_daily_requests,
                daily_output_tokens=self.settings.guest_quota_daily_output_tokens,
                minute_requests=self.settings.guest_quota_minute_requests,
            )
        if has_byok:
            return QuotaLimits(
                daily_requests=self.settings.byok_quota_daily_requests,
                daily_output_tokens=self.settings.byok_quota_daily_output_tokens,
                minute_requests=self.settings.byok_quota_minute_requests,
            )
        return QuotaLimits(
            daily_requests=self.settings.quota_daily_requests,
            daily_output_tokens=self.settings.quota_daily_output_tokens,
            minute_requests=self.settings.quota_minute_requests,
        )
