import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))


class TraceTests(unittest.TestCase):
    def test_build_trace_captures_chunks_ranking_and_prompt(self):
        from startup_radar.models import RetrievedEvidence
        from startup_radar.trace import build_rag_trace

        candidates = [
            RetrievedEvidence(
                chunk_id="older",
                startup_name="OlderAI",
                text="OlderAI builds AI workflow tools.",
                source_url="https://example.com/older",
                source_type="news",
                similarity_score=0.91,
                metadata={"published_at": "2025-01-01", "product_hunt_votes": 10},
            ),
            RetrievedEvidence(
                chunk_id="fresh",
                startup_name="FreshAI",
                text="FreshAI builds AI assistants for clinics.",
                source_url="https://example.com/fresh",
                source_type="product_hunt",
                similarity_score=0.86,
                metadata={"published_at": "2026-06-08", "product_hunt_votes": 900},
            ),
        ]
        reranked = [
            RetrievedEvidence(
                chunk_id="fresh",
                startup_name="FreshAI",
                text="FreshAI builds AI assistants for clinics.",
                source_url="https://example.com/fresh",
                source_type="product_hunt",
                similarity_score=0.86,
                trend_score=84,
                rerank_score=0.851,
                metadata={"published_at": "2026-06-08", "product_hunt_votes": 900},
            )
        ]

        trace = build_rag_trace(
            query="Which AI healthcare startups are trending?",
            source_chunks=candidates,
            pinecone_results=candidates,
            reranked=reranked,
            final_prompt="Question: Which AI healthcare startups are trending?",
            pinecone_filter={"source_type": {"$in": ["product_hunt"]}},
            pinecone_top_k=20,
        )

        self.assertEqual(trace["query"], "Which AI healthcare startups are trending?")
        self.assertEqual(trace["source_chunks"][0]["chunk_id"], "older")
        self.assertEqual(trace["pinecone_query"]["top_k"], 20)
        self.assertEqual(trace["pinecone_query"]["filter"], {"source_type": {"$in": ["product_hunt"]}})
        self.assertEqual(trace["pinecone_results_before_rerank"][0]["chunk_id"], "older")
        self.assertEqual(trace["reranked_chunks"][0]["startup_name"], "FreshAI")
        self.assertEqual(trace["llm_prompt"], "Question: Which AI healthcare startups are trending?")


if __name__ == "__main__":
    unittest.main()
