import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))


class LlmProviderTests(unittest.TestCase):
    def test_create_chat_model_uses_gemini_provider(self):
        from startup_radar.rag import create_chat_model

        chat_google = MagicMock()
        fake_module = types.SimpleNamespace(ChatGoogleGenerativeAI=chat_google)
        with patch.dict(sys.modules, {"langchain_google_genai": fake_module}):
            create_chat_model(provider="gemini", model="gemini-2.5-flash")

        chat_google.assert_called_once_with(model="gemini-2.5-flash", temperature=0.2)

    def test_generate_answer_invokes_selected_provider(self):
        from startup_radar.models import RetrievedEvidence
        from startup_radar.rag import generate_answer

        fake_model = MagicMock()
        fake_model.invoke.return_value.content = "CarePilot is trending [1]."
        evidence = [
            RetrievedEvidence(
                chunk_id="a",
                startup_name="CarePilot",
                text="CarePilot automates clinic admin workflows.",
                source_url="https://example.com/a",
                source_type="product_hunt",
                similarity_score=0.9,
            )
        ]

        with patch("startup_radar.rag.create_chat_model", return_value=fake_model):
            answer = generate_answer("Which startups are trending?", evidence, provider="gemini")

        self.assertEqual(answer, "CarePilot is trending [1].")
        fake_model.invoke.assert_called_once()


if __name__ == "__main__":
    unittest.main()
