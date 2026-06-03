import unittest
from unittest.mock import Mock, patch

import pandas as pd

import main


class DashboardDataTests(unittest.TestCase):
    def test_empty_faostat_result_uses_demo_data(self):
        data, is_live, note = main.ensure_usable_data(
            pd.DataFrame(columns=["Area", "Item", "Year", "Value"]),
            True,
            "Live FAOSTAT QCL bulk download",
        )

        self.assertFalse(is_live)
        self.assertIn("Demo data", note)
        self.assertGreater(len(data["Area"].dropna().unique()), 0)

    def test_assistant_context_summarizes_selected_crop_data(self):
        data = pd.DataFrame(
            [
                ("Brazil", "Soybeans", 2022, 120701),
                ("Brazil", "Soybeans", 2023, 152145),
                ("Brazil", "Maize", 2023, 131947),
            ],
            columns=["Area", "Item", "Year", "Value"],
        )

        context = main.build_assistant_context(
            data=data,
            country="Brazil",
            selected_items=["Soybeans", "Maize"],
            year_range=(2022, 2023),
            comparison_year=2023,
            source_note="Test source",
        )

        self.assertIn("Brazil", context)
        self.assertIn("Soybeans", context)
        self.assertIn("2022-2023", context)
        self.assertIn("Test source", context)

    def test_normalize_faostat_data_keeps_production_tonnes_rows(self):
        raw = pd.DataFrame(
            [
                ("France", "Production", "Wheat", 2023, "tonnes", 35000000),
                ("France", "Area harvested", "Wheat", 2023, "ha", 4500000),
            ],
            columns=["Area", "Element", "Item", "Year", "Unit", "Value"],
        )

        normalized = main.normalize_faostat_data(raw)

        self.assertEqual(len(normalized), 1)
        self.assertEqual(normalized.iloc[0]["Area"], "France")
        self.assertEqual(normalized.iloc[0]["Item"], "Wheat")

    def test_normalize_owid_crop_data_uses_iso_country_rows(self):
        raw = pd.DataFrame(
            [
                ("France", "FRA", 2023, 35000000),
                ("World", "OWID_WRL", 2023, 799000000),
                ("Africa (FAO)", None, 2023, 120000000),
            ],
            columns=["Entity", "Code", "Year", "Wheat - Production (tonnes)"],
        )

        normalized = main.normalize_owid_crop_data(raw, "Wheat")

        self.assertEqual(len(normalized), 1)
        self.assertEqual(normalized.iloc[0]["Area"], "France")
        self.assertEqual(normalized.iloc[0]["Item"], "Wheat")

    def test_build_top_crop_map_data_selects_largest_crop_by_country(self):
        data = pd.DataFrame(
            [
                ("France", "Wheat", 2023, 10),
                ("France", "Maize", 2023, 15),
                ("Brazil", "Soybeans", 2023, 30),
                ("Brazil", "Wheat", 2022, 100),
            ],
            columns=["Area", "Item", "Year", "Value"],
        )

        map_data = main.build_top_crop_map_data(data, ["Wheat", "Maize", "Soybeans"], 2023)

        self.assertEqual(len(map_data), 2)
        france = map_data[map_data["Area"].eq("France")].iloc[0]
        self.assertEqual(france["Item"], "Maize")
        self.assertEqual(france["Value"], 15)

    def test_get_secret_value_uses_environment_fallback(self):
        with patch.dict("os.environ", {"GROQ_MODEL": "groq-test"}):
            self.assertEqual(main.get_secret_value("GROQ_MODEL"), "groq-test")

    def test_assistant_context_includes_countries_mentioned_in_question(self):
        data = pd.DataFrame(
            [
                ("India", "Rice", 2023, 204671),
                ("Japan", "Rice", 2023, 9810),
                ("India", "Wheat", 2023, 110554),
            ],
            columns=["Area", "Item", "Year", "Value"],
        )

        context = main.build_assistant_context(
            data=data,
            country="India",
            selected_items=["Rice"],
            year_range=(2023, 2023),
            comparison_year=2023,
            source_note="Test source",
            question="Is Japan growing more rice compared to India?",
        )

        self.assertIn("Japan", context)
        self.assertIn("India", context)
        self.assertIn("Rice", context)
        self.assertIn("9.8K t", context)

    def test_summarize_filter_state_is_compact_and_plain_english(self):
        summary = main.summarize_filter_state(
            country="Japan",
            selected_group="Cereals",
            selected_items=["Rice", "Wheat", "Maize"],
            year_range=(2000, 2024),
            is_live=True,
        )

        self.assertIn("Japan", summary)
        self.assertIn("3 crops", summary)
        self.assertIn("2000-2024", summary)
        self.assertNotIn("FAOSTAT live", summary)

    def test_build_crop_tile_options_keeps_selected_items_and_top_crops(self):
        data = pd.DataFrame(
            [
                ("Japan", "Rice", 2024, 100),
                ("Japan", "Wheat", 2024, 80),
                ("Japan", "Maize", 2024, 60),
                ("Japan", "Barley", 2024, 40),
            ],
            columns=["Area", "Item", "Year", "Value"],
        )

        options = main.build_crop_tile_options(data, ["Barley"], limit=2)

        self.assertEqual(options, ["Rice", "Wheat", "Barley"])

    def test_build_country_comparison_summarizes_two_country_crop_trends(self):
        data = pd.DataFrame(
            [
                ("India", "Rice", 2020, 100),
                ("India", "Rice", 2024, 150),
                ("Japan", "Rice", 2020, 80),
                ("Japan", "Rice", 2024, 60),
            ],
            columns=["Area", "Item", "Year", "Value"],
        )

        comparison = main.build_country_comparison(
            data=data,
            country_a="India",
            country_b="Japan",
            crop="Rice",
            year_range=(2020, 2024),
        )

        self.assertEqual(comparison["latest_year"], 2024)
        self.assertEqual(comparison["leaders"][0]["country"], "India")
        self.assertEqual(comparison["leaders"][0]["latest_value"], 150)
        self.assertEqual(comparison["leaders"][0]["growth_pct"], 50.0)
        self.assertEqual(comparison["leaders"][1]["growth_pct"], -25.0)
        self.assertEqual(comparison["gap"], 90)

    def test_build_executive_insights_returns_plain_english_takeaways(self):
        top_latest = pd.DataFrame(
            [
                {"Item": "Rice", "Value": 150},
                {"Item": "Wheat", "Value": 50},
            ]
        )
        country_totals = pd.DataFrame(
            [
                {"Area": "India", "Value": 1000},
                {"Area": "Japan", "Value": 100},
            ]
        )

        insights = main.build_executive_insights(
            country="India",
            latest_year=2024,
            top_latest=top_latest,
            total_latest=200,
            country_totals=country_totals,
            selected_items=["Rice", "Wheat"],
        )

        self.assertEqual(len(insights), 3)
        self.assertIn("Rice", insights[0])
        self.assertIn("India", insights[1])
        self.assertIn("200 t", insights[2])
        self.assertIn("India", insights[2])

    def test_build_executive_insights_uses_rank_share_and_growth(self):
        top_latest = pd.DataFrame(
            [
                {"Item": "Rice", "Value": 160},
                {"Item": "Wheat", "Value": 40},
            ]
        )
        country_totals = pd.DataFrame(
            [
                {"Area": "India", "Value": 1000},
                {"Area": "Japan", "Value": 200},
                {"Area": "Brazil", "Value": 100},
            ]
        )
        filtered = pd.DataFrame(
            [
                ("India", "Rice", 2020, 100),
                ("India", "Wheat", 2020, 20),
                ("India", "Rice", 2024, 160),
                ("India", "Wheat", 2024, 40),
            ],
            columns=["Area", "Item", "Year", "Value"],
        )

        insights = main.build_executive_insights(
            country="India",
            latest_year=2024,
            top_latest=top_latest,
            total_latest=200,
            country_totals=country_totals,
            selected_items=["Rice", "Wheat"],
            filtered=filtered,
            year_range=(2020, 2024),
        )

        combined = " ".join(insights)
        self.assertIn("80.0%", combined)
        self.assertIn("#1", combined)
        self.assertIn("+66.7%", combined)

    def test_build_suggested_questions_uses_selected_context(self):
        questions = main.build_suggested_questions("India", ["Rice", "Wheat"], (2000, 2024))

        self.assertEqual(len(questions), 4)
        self.assertTrue(any("India" in question for question in questions))
        self.assertTrue(any("Rice" in question for question in questions))

    def test_parse_llm_insights_limits_to_three_non_empty_items(self):
        parsed = main.parse_llm_insights(
            "1. Rice is the dependency risk.\n"
            "2. India is widening the gap.\n"
            "3. Growth is concentrated.\n"
            "4. Extra item should be ignored."
        )

        self.assertEqual(
            parsed,
            [
                "Rice is the dependency risk.",
                "India is widening the gap.",
                "Growth is concentrated.",
            ],
        )

    def test_generate_llm_insights_returns_fallback_without_key(self):
        fallback = ["fallback one", "fallback two", "fallback three"]

        self.assertEqual(
            main.generate_llm_insights({}, "", main.DEFAULT_GROQ_MODEL, fallback),
            fallback,
        )

    @patch("main.requests.post")
    def test_generate_llm_insights_uses_groq_response_when_available(self, mock_post):
        response = Mock()
        response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "1. Rice drives the story.\n2. Rank is strong.\n3. Growth is improving."
                    }
                }
            ]
        }
        response.raise_for_status.return_value = None
        mock_post.return_value = response

        insights = main.generate_llm_insights(
            {"country": "India"},
            "fake-key",
            "test-model",
            ["fallback one", "fallback two", "fallback three"],
        )

        self.assertEqual(insights[0], "Rice drives the story.")
        self.assertEqual(len(insights), 3)


if __name__ == "__main__":
    unittest.main()
