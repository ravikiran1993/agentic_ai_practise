from __future__ import annotations

import re

import requests
from bs4 import BeautifulSoup

from startup_radar.models import StartupEvidence


def fetch_company_site_to_evidence(
    startup_name: str,
    url: str,
    sector: str | None = None,
    region: str | None = None,
    country: str | None = None,
    max_chars: int = 4000,
) -> StartupEvidence:
    """Fetch a company homepage and normalize readable text into evidence."""
    response = requests.get(
        url,
        headers={"User-Agent": "GlobalStartupRadar/1.0 (+https://github.com/ravikiran-uppalapati/agentic_ai_practise)"},
        timeout=12,
    )
    response.raise_for_status()
    text = extract_readable_text(response.text, max_chars=max_chars)
    return StartupEvidence(
        startup_name=startup_name,
        source_type="company_site",
        source_name="Company Website",
        source_url=url,
        title=f"{startup_name} website",
        text=text,
        sector=sector,
        region=region,
        country=country,
        product_url=url,
        metadata={"raw_source": "company_site"},
    )


def extract_readable_text(html: str, max_chars: int = 4000) -> str:
    """Extract compact readable text from simple company website HTML."""
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "noscript", "svg", "nav", "footer"]):
        element.decompose()
    text = soup.get_text(" ")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]
