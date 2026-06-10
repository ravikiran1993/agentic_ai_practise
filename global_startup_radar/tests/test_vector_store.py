import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))


class VectorStoreTests(unittest.TestCase):
    def test_create_pinecone_vector_store_uses_gemini_embeddings(self):
        from startup_radar.vector_store import create_pinecone_vector_store

        embeddings_class = MagicMock(return_value="embedding-client")
        vector_store_class = MagicMock(return_value="vector-store")
        google_module = types.SimpleNamespace(GoogleGenerativeAIEmbeddings=embeddings_class)
        pinecone_module = types.SimpleNamespace(PineconeVectorStore=vector_store_class)

        with patch.dict(
            sys.modules,
            {
                "langchain_google_genai": google_module,
                "langchain_pinecone": pinecone_module,
            },
        ):
            store = create_pinecone_vector_store(index_name="global-startup-radar")

        self.assertEqual(store, "vector-store")
        embeddings_class.assert_called_once_with(model="models/text-embedding-004")
        vector_store_class.assert_called_once_with(index_name="global-startup-radar", embedding="embedding-client")


if __name__ == "__main__":
    unittest.main()
