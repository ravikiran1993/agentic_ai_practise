import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))


class PipelineCoreTests(unittest.TestCase):
    def test_product_hunt_record_creates_source_aware_chunk(self):
        from startup_radar.chunking import chunk_evidence_record
        from startup_radar.models import StartupEvidence

        record = StartupEvidence(
            startup_name="Synthflow",
            source_type="product_hunt",
            source_name="Product Hunt",
            source_url="https://www.producthunt.com/posts/synthflow",
            title="Synthflow",
            text="Build voice AI agents for business workflows.",
            published_at="2026-05-20",
            topics=["AI", "Productivity"],
            sector="AI",
            region="Europe",
            country="Germany",
            product_url="https://synthflow.example",
            product_hunt_votes=840,
            product_hunt_comments=95,
        )

        chunks = chunk_evidence_record(record)

        self.assertEqual(len(chunks), 1)
        chunk = chunks[0]
        self.assertIn("Synthflow", chunk.text)
        self.assertIn("Build voice AI agents", chunk.text)
        self.assertEqual(chunk.metadata["startup_name"], "Synthflow")
        self.assertEqual(chunk.metadata["source_type"], "product_hunt")
        self.assertEqual(chunk.metadata["product_hunt_votes"], 840)

    def test_trend_score_is_normalized_to_100(self):
        from startup_radar.models import RetrievedEvidence
        from startup_radar.scoring import compute_trend_score

        evidence = RetrievedEvidence(
            chunk_id="chunk-1",
            startup_name="Climatix",
            text="Carbon accounting software for manufacturers.",
            source_url="https://example.com/climatix",
            source_type="product_hunt",
            similarity_score=0.82,
            metadata={
                "product_hunt_votes": 500,
                "product_hunt_comments": 50,
                "published_at": "2026-06-01",
                "topics": ["Climate", "SaaS"],
                "sector": "Climate",
                "region": "Global",
            },
        )

        score = compute_trend_score(
            evidence,
            query="global climate startups",
            today="2026-06-10",
            source_diversity=0.5,
            evidence_count=3,
        )

        self.assertGreaterEqual(score.total, 0)
        self.assertLessEqual(score.total, 100)
        self.assertGreater(score.components["semantic_relevance"], 0)
        self.assertGreater(score.components["launch_recency"], 0)
        self.assertGreater(score.components["product_hunt_votes"], 0)

    def test_reranking_combines_similarity_and_trend_signals(self):
        from startup_radar.models import RetrievedEvidence
        from startup_radar.reranking import rerank_evidence

        older_high_similarity = RetrievedEvidence(
            chunk_id="old",
            startup_name="OldAI",
            text="Enterprise AI notes app.",
            source_url="https://example.com/old",
            source_type="news",
            similarity_score=0.91,
            metadata={"published_at": "2025-01-01", "product_hunt_votes": 10},
        )
        fresh_trending = RetrievedEvidence(
            chunk_id="fresh",
            startup_name="FreshAI",
            text="AI operating system for clinics.",
            source_url="https://example.com/fresh",
            source_type="product_hunt",
            similarity_score=0.86,
            metadata={
                "published_at": "2026-06-08",
                "product_hunt_votes": 900,
                "product_hunt_comments": 120,
                "topics": ["AI", "Healthcare"],
            },
        )

        ranked = rerank_evidence(
            [older_high_similarity, fresh_trending],
            query="AI healthcare startups",
            today="2026-06-10",
        )

        self.assertEqual(ranked[0].startup_name, "FreshAI")
        self.assertGreater(ranked[0].rerank_score, ranked[1].rerank_score)


if __name__ == "__main__":
    unittest.main()
