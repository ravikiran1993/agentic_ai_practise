import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))


class IngestionAndRagTests(unittest.TestCase):
    def test_sample_loader_returns_evidence_records(self):
        from startup_radar.ingestion.sample_data import load_sample_records

        with tempfile.TemporaryDirectory() as tmpdir:
            sample_path = Path(tmpdir) / "sample.json"
            sample_path.write_text(
                """[
                  {
                    "startup_name": "OrbitalOps",
                    "source_type": "news",
                    "source_name": "Example Startup News",
                    "source_url": "https://example.com/orbitalops",
                    "title": "OrbitalOps raises seed round",
                    "text": "OrbitalOps builds logistics software for satellite operators.",
                    "published_at": "2026-05-01",
                    "topics": ["Space", "Logistics"],
                    "sector": "Space",
                    "region": "Global"
                  }
                ]""",
                encoding="utf-8",
            )

            records = load_sample_records(sample_path)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].startup_name, "OrbitalOps")
        self.assertEqual(records[0].topics, ["Space", "Logistics"])

    def test_product_hunt_post_normalizes_to_evidence(self):
        from startup_radar.ingestion.product_hunt import product_hunt_post_to_evidence

        post = {
            "name": "CarePilot",
            "tagline": "AI admin assistant for clinics",
            "description": "CarePilot automates intake, scheduling, and follow-up workflows.",
            "url": "https://www.producthunt.com/posts/carepilot",
            "website": "https://carepilot.example",
            "createdAt": "2026-06-08T10:00:00Z",
            "votesCount": 720,
            "commentsCount": 88,
            "topics": {"edges": [{"node": {"name": "Artificial Intelligence"}}, {"node": {"name": "Health"}}]},
        }

        evidence = product_hunt_post_to_evidence(post)

        self.assertEqual(evidence.startup_name, "CarePilot")
        self.assertEqual(evidence.source_type, "product_hunt")
        self.assertEqual(evidence.product_hunt_votes, 720)
        self.assertIn("Artificial Intelligence", evidence.topics)
        self.assertIn("automates intake", evidence.text)

    def test_build_cited_context_limits_and_labels_evidence(self):
        from startup_radar.models import RetrievedEvidence
        from startup_radar.rag import build_cited_context

        evidence = [
            RetrievedEvidence(
                chunk_id="a",
                startup_name="CarePilot",
                text="CarePilot automates clinic admin workflows.",
                source_url="https://example.com/a",
                source_type="product_hunt",
                similarity_score=0.9,
                rerank_score=0.88,
                trend_score=82,
            ),
            RetrievedEvidence(
                chunk_id="b",
                startup_name="GridBloom",
                text="GridBloom forecasts energy demand for distributed grids.",
                source_url="https://example.com/b",
                source_type="news",
                similarity_score=0.85,
                rerank_score=0.81,
                trend_score=76,
            ),
        ]

        context = build_cited_context(evidence, limit=1)

        self.assertIn("[1] CarePilot", context)
        self.assertIn("https://example.com/a", context)
        self.assertNotIn("GridBloom", context)


if __name__ == "__main__":
    unittest.main()
