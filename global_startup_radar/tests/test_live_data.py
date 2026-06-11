import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))


class LiveDataTests(unittest.TestCase):
    def test_load_product_hunt_evidence_fetches_and_converts_posts(self):
        from startup_radar.live_data import load_product_hunt_evidence

        post = {
            "name": "OpsPilot",
            "tagline": "AI operations analyst",
            "description": "OpsPilot summarizes incidents and release risk.",
            "url": "https://www.producthunt.com/posts/opspilot",
            "website": "https://opspilot.example",
            "createdAt": "2026-06-09T10:00:00Z",
            "votesCount": 600,
            "commentsCount": 75,
            "topics": {"edges": [{"node": {"name": "Developer Tools"}}]},
        }

        with patch("startup_radar.live_data.fetch_recent_product_hunt_posts", return_value=[post]):
            evidence = load_product_hunt_evidence(first=1, posted_after="2026-06-01")

        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0].startup_name, "OpsPilot")
        self.assertEqual(evidence[0].source_type, "product_hunt")
        self.assertIn("AI operations analyst", evidence[0].text)
        self.assertEqual(evidence[0].metadata["product_hunt_votes"], 600)

    def test_enrich_with_company_sites_appends_website_evidence(self):
        from startup_radar.live_data import enrich_with_company_sites
        from startup_radar.models import RetrievedEvidence, StartupEvidence

        product_hunt_evidence = [
            RetrievedEvidence(
                chunk_id="ph-1",
                startup_name="OpsPilot",
                text="Startup: OpsPilot",
                source_url="https://www.producthunt.com/posts/opspilot",
                source_type="product_hunt",
                similarity_score=0.72,
                metadata={
                    "startup_name": "OpsPilot",
                    "product_url": "https://opspilot.example",
                    "sector": "Developer Tools",
                    "region": "Global",
                },
            )
        ]
        website_record = StartupEvidence(
            startup_name="OpsPilot",
            source_type="company_site",
            source_name="Company Website",
            source_url="https://opspilot.example",
            title="OpsPilot website",
            text="OpsPilot automates incident reviews.",
            sector="Developer Tools",
            region="Global",
        )

        with patch("startup_radar.live_data.fetch_company_site_to_evidence", return_value=website_record):
            enriched = enrich_with_company_sites(product_hunt_evidence, limit=1)

        self.assertEqual(len(enriched), 2)
        self.assertEqual(enriched[1].source_type, "company_site")
        self.assertIn("incident reviews", enriched[1].text)


if __name__ == "__main__":
    unittest.main()
