import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))


class SuggestionTests(unittest.TestCase):
    def test_get_suggested_questions_returns_demo_ready_questions(self):
        from startup_radar.suggestions import get_suggested_questions

        questions = get_suggested_questions()

        self.assertGreaterEqual(len(questions), 5)
        self.assertIn("Which startups are trending right now and what evidence supports them?", questions)
        self.assertIn("What themes are emerging from the latest Product Hunt launches?", questions)


if __name__ == "__main__":
    unittest.main()
