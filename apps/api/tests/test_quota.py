import pytest
from fastapi import HTTPException

from app.config import Settings
from app.services.quota import QuotaService


class _FakeBegin:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeResult:
    def __init__(self, rowcount=1, row=None):
        self.rowcount = rowcount
        self._row = row

    def mappings(self):
        return self

    def first(self):
        return self._row


class _FakeSession:
    def begin(self):
        return _FakeBegin()

    async def execute(self, statement, params=None):
        sql = str(statement)
        if "inflight_requests" in sql:
            return _FakeResult(rowcount=0)
        return _FakeResult(row={"req_count": 1, "token_out": 0})

    async def rollback(self):
        return None


@pytest.mark.asyncio
async def test_quota_blocks_parallel_inflight():
    settings = Settings(quota_daily_requests=25, quota_daily_output_tokens=2000, quota_minute_requests=10)
    service = QuotaService(settings)

    with pytest.raises(HTTPException) as exc_info:
        await service.reserve(_FakeSession(), user_id="user-1")

    assert exc_info.value.status_code == 429
