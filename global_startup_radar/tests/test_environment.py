import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))


class EnvironmentTests(unittest.TestCase):
    def test_load_environment_reads_local_dotenv_file(self):
        from startup_radar.environment import load_environment

        with tempfile.TemporaryDirectory() as tmpdir:
            dotenv_path = Path(tmpdir) / ".env"
            dotenv_path.write_text("OPENAI_API_KEY=test-key\n", encoding="utf-8")

            with patch.dict(os.environ, {}, clear=True):
                load_environment(dotenv_path)

                self.assertEqual(os.environ["OPENAI_API_KEY"], "test-key")


if __name__ == "__main__":
    unittest.main()
