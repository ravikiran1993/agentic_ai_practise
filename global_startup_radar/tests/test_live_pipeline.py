import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))


class LivePipelineTests(unittest.TestCase):
    def test_build_pinecone_filter_uses_selected_metadata(self):
        from startup_radar.live_pipeline import build_pinecone_filter

        metadata_filter = build_pinecone_filter(
            sources=["product_hunt"],
            sectors=["Developer Tools", "AI"],
            regions=["Global"],
        )

        self.assertEqual(metadata_filter["source_type"], {"$in": ["product_hunt"]})
        self.assertEqual(metadata_filter["sector"], {"$in": ["Developer Tools", "AI"]})
        self.assertEqual(metadata_filter["region"], {"$in": ["Global"]})

    def test_evidence_to_chunks_preserves_text_and_metadata(self):
        from startup_radar.live_pipeline import evidence_to_chunks
        from startup_radar.models import RetrievedEvidence

        evidence = [
            RetrievedEvidence(
                chunk_id="abc",
                startup_name="OpsPilot",
                text="Startup: OpsPilot",
                source_url="https://example.com",
                source_type="product_hunt",
                similarity_score=0.72,
                metadata={"startup_name": "OpsPilot", "source_type": "product_hunt"},
            )
        ]

        chunks = evidence_to_chunks(evidence)

        self.assertEqual(chunks[0].id, "abc")
        self.assertEqual(chunks[0].startup_name, "OpsPilot")
        self.assertEqual(chunks[0].text, "Startup: OpsPilot")
        self.assertEqual(chunks[0].metadata["source_type"], "product_hunt")

    def test_index_and_search_uses_vector_store_helpers(self):
        from startup_radar.live_pipeline import index_evidence, search_indexed_evidence
        from startup_radar.models import RetrievedEvidence

        evidence = [
            RetrievedEvidence(
                chunk_id="abc",
                startup_name="OpsPilot",
                text="Startup: OpsPilot",
                source_url="https://example.com",
                source_type="product_hunt",
                similarity_score=0.72,
                metadata={"startup_name": "OpsPilot"},
            )
        ]
        store = MagicMock()

        with patch("startup_radar.live_pipeline.upsert_chunks") as upsert:
            count = index_evidence(store, evidence)

        self.assertEqual(count, 1)
        upsert.assert_called_once()

        with patch("startup_radar.live_pipeline.search_vector_store", return_value=evidence) as search:
            results = search_indexed_evidence(store, "AI tools", k=5, metadata_filter={"source_type": "product_hunt"})

        self.assertEqual(results, evidence)
        search.assert_called_once_with(store, "AI tools", k=5, filters={"source_type": "product_hunt"})


if __name__ == "__main__":
    unittest.main()
