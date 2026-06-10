import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))


class ChatTests(unittest.TestCase):
    def test_create_chat_turn_stores_question_answer_and_evidence(self):
        from startup_radar.chat import create_chat_turn
        from startup_radar.models import RetrievedEvidence

        evidence = [
            RetrievedEvidence(
                chunk_id="a",
                startup_name="CarePilot",
                text="CarePilot automates clinic workflows.",
                source_url="https://example.com/a",
                source_type="product_hunt",
                similarity_score=0.9,
                trend_score=82,
                rerank_score=0.88,
            )
        ]

        turn = create_chat_turn(
            question="Which health AI startups are trending?",
            answer="CarePilot is showing strong launch traction [1].",
            evidence=evidence,
            mode="Live Gemini call",
        )

        self.assertEqual(turn["question"], "Which health AI startups are trending?")
        self.assertEqual(turn["answer"], "CarePilot is showing strong launch traction [1].")
        self.assertEqual(turn["mode"], "Live Gemini call")
        self.assertEqual(turn["evidence"][0].startup_name, "CarePilot")

    def test_append_chat_turn_keeps_existing_history(self):
        from startup_radar.chat import append_chat_turn

        history = [{"question": "First", "answer": "Answer", "evidence": [], "mode": "Prompt preview"}]
        updated = append_chat_turn(
            history,
            {"question": "Second", "answer": "Another answer", "evidence": [], "mode": "Prompt preview"},
        )

        self.assertEqual(len(updated), 2)
        self.assertEqual(history[0]["question"], "First")
        self.assertEqual(updated[1]["question"], "Second")


if __name__ == "__main__":
    unittest.main()
