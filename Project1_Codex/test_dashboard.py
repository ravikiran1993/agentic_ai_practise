import unittest
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
