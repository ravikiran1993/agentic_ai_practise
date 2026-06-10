from __future__ import annotations

import os
from typing import Any

import requests

from startup_radar.models import StartupEvidence


PRODUCT_HUNT_GRAPHQL_URL = "https://api.producthunt.com/v2/api/graphql"


RECENT_POSTS_QUERY = """
query RecentPosts($postedAfter: DateTime, $first: Int!) {
  posts(first: $first, postedAfter: $postedAfter, order: VOTES) {
    edges {
      node {
        name
        tagline
        description
        url
        website
        createdAt
        votesCount
        commentsCount
        topics {
          edges {
            node {
              name
            }
          }
        }
      }
    }
  }
}
"""


def fetch_recent_product_hunt_posts(
    token: str | None = None,
    posted_after: str | None = None,
    first: int = 25,
) -> list[dict[str, Any]]:
    """Fetch recent Product Hunt posts using a developer token."""
    access_token = token or os.getenv("PRODUCT_HUNT_TOKEN")
    if not access_token:
        raise RuntimeError("PRODUCT_HUNT_TOKEN is required to fetch live Product Hunt data.")

    response = requests.post(
        PRODUCT_HUNT_GRAPHQL_URL,
        json={"query": RECENT_POSTS_QUERY, "variables": {"postedAfter": posted_after, "first": first}},
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("errors"):
        raise RuntimeError(f"Product Hunt API returned errors: {payload['errors']}")
    edges = payload.get("data", {}).get("posts", {}).get("edges", [])
    return [edge["node"] for edge in edges if edge.get("node")]


def product_hunt_post_to_evidence(post: dict[str, Any]) -> StartupEvidence:
    """Normalize a Product Hunt post into a StartupEvidence record."""
    topics = _extract_topics(post.get("topics"))
    tagline = post.get("tagline") or ""
    description = post.get("description") or ""
    text = " ".join(part for part in [tagline, description] if part).strip()
    return StartupEvidence(
        startup_name=post.get("name", "Unknown Product"),
        source_type="product_hunt",
        source_name="Product Hunt",
        source_url=post.get("url") or "",
        title=post.get("name", "Product Hunt launch"),
        text=text,
        published_at=(post.get("createdAt") or "")[:10] or None,
        topics=topics,
        sector=topics[0] if topics else None,
        region="Global",
        product_url=post.get("website"),
        product_hunt_votes=int(post.get("votesCount") or 0),
        product_hunt_comments=int(post.get("commentsCount") or 0),
        metadata={"raw_source": "product_hunt"},
    )


def _extract_topics(topics_payload: Any) -> list[str]:
    if isinstance(topics_payload, list):
        return [str(topic) for topic in topics_payload]
    edges = (topics_payload or {}).get("edges", [])
    names = []
    for edge in edges:
        name = edge.get("node", {}).get("name")
        if name:
            names.append(name)
    return names

