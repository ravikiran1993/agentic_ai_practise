import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))


class CompanySiteTests(unittest.TestCase):
    def test_extract_readable_text_removes_scripts_and_collapses_whitespace(self):
        from startup_radar.ingestion.company_site import extract_readable_text

        html = """
        <html>
          <head><script>alert("x")</script><style>body {}</style></head>
          <body>
            <h1>OpsPilot</h1>
            <p>AI operations analyst for release teams.</p>
          </body>
        </html>
        """

        text = extract_readable_text(html)

        self.assertEqual(text, "OpsPilot AI operations analyst for release teams.")

    def test_fetch_company_site_to_evidence_returns_website_record(self):
        from startup_radar.ingestion.company_site import fetch_company_site_to_evidence

        response = MagicMock()
        response.text = "<html><body><h1>OpsPilot</h1><p>Automates incident reviews.</p></body></html>"
        response.raise_for_status.return_value = None

        with patch("startup_radar.ingestion.company_site.requests.get", return_value=response):
            evidence = fetch_company_site_to_evidence(
                startup_name="OpsPilot",
                url="https://opspilot.example",
                sector="Developer Tools",
                region="Global",
            )

        self.assertEqual(evidence.startup_name, "OpsPilot")
        self.assertEqual(evidence.source_type, "company_site")
        self.assertEqual(evidence.source_url, "https://opspilot.example")
        self.assertIn("Automates incident reviews", evidence.text)
        self.assertEqual(evidence.sector, "Developer Tools")


if __name__ == "__main__":
    unittest.main()
