"""Tests for the SEC EDGAR client."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.ingestion.sec_edgar import SecEdgarClient


def _mock_response(status_code: int = 200, text_data: str = "") -> httpx.Response:
    request = httpx.Request("GET", "https://test.example.com")
    return httpx.Response(status_code, text=text_data, request=request)


@pytest.mark.asyncio
async def test_sec_edgar_client_user_agent():
    client = SecEdgarClient(user_agent="TestAgent/1.0 (test@example.com)")
    assert client.client.headers["user-agent"] == "TestAgent/1.0 (test@example.com)"
    await client.close()


@pytest.mark.asyncio
async def test_get_latest_filings():
    client = SecEdgarClient()

    mock_xml = """<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <title>EDGAR Search Results</title>
      <entry>
        <title>8-K - Current report</title>
        <link rel="alternate" type="text/html" href="https://example.com/8k.htm"/>
        <summary type="html">&lt;b&gt;8-K&lt;/b&gt;</summary>
        <updated>2024-01-01T12:00:00-05:00</updated>
      </entry>
    </feed>
    """

    mock_resp = _mock_response(text_data=mock_xml)

    with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        with patch("app.ingestion.sec_edgar.rate_limiter.acquire", new_callable=AsyncMock):
            filings = await client.get_latest_filings("AAPL", "8-K")
            assert len(filings) == 1
            assert filings[0]["title"] == "8-K - Current report"

    await client.close()
