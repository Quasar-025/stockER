"""Tests for the SEC EDGAR client."""

import pytest
import httpx
from unittest.mock import patch, AsyncMock

from app.ingestion.sec_edgar import SecEdgarClient


@pytest.mark.asyncio
async def test_sec_edgar_client_user_agent():
    """Test that the client uses the required User-Agent header."""
    client = SecEdgarClient(user_agent="TestAgent/1.0 (test@example.com)")
    assert client.client.headers["user-agent"] == "TestAgent/1.0 (test@example.com)"
    await client.close()


@pytest.mark.asyncio
async def test_get_latest_filings():
    """Test fetching filings via RSS."""
    client = SecEdgarClient()
    
    # Mock XML response (Atom feed format)
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
    
    mock_response = httpx.Response(200, text=mock_xml)
    
    with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        
        with patch("app.ingestion.sec_edgar.rate_limiter.acquire", new_callable=AsyncMock):
            filings = await client.get_latest_filings("AAPL", "8-K")
            
            assert len(filings) == 1
            assert filings[0]["title"] == "8-K - Current report"
            assert filings[0]["link"] == "https://example.com/8k.htm"
            assert "8-K" in filings[0]["summary"]

    await client.close()
