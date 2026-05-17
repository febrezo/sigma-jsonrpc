import unittest

from app.config import _csv_to_set
from app.engine import _parse_identifier_table, _parse_plugin_table


class TransformationsTests(unittest.TestCase):
    def test_csv_to_set_normalizes_values(self) -> None:
        self.assertEqual(_csv_to_set(" Splunk, eql, , SPLUNK "), {"splunk", "eql"})

    def test_parse_identifier_table_from_box_drawing_table(self) -> None:
        stdout = (
            "┌────────────┬─────────────┐\n"
            "│ identifier │ description │\n"
            "├────────────┼─────────────┤\n"
            "│ splunk     │ Splunk SIEM │\n"
            "│ eql        │ Elastic EQL │\n"
            "└────────────┴─────────────┘\n"
        )
        self.assertEqual(_parse_identifier_table(stdout), ["eql", "splunk"])

    def test_parse_plugin_table_with_headers_and_compatibility(self) -> None:
        stdout = (
            "| type     | identifier | compatible | description   |\n"
            "|----------|------------|------------|---------------|\n"
            "| backend  | splunk     | true       | Splunk target |\n"
            "| pipeline | windows    | false      | Win pipeline  |\n"
            "| backend  | splunk     | true       | Duplicate row |\n"
        )
        plugins = _parse_plugin_table(stdout)

        self.assertEqual(len(plugins), 2)
        self.assertEqual({p.plugin_type for p in plugins}, {"backend", "pipeline"})
        identifiers = {p.identifier for p in plugins}
        self.assertEqual(identifiers, {"splunk", "windows"})

    def test_parse_plugin_table_fallback_parser(self) -> None:
        stdout = "Backend    splunk\nPipeline   windows\nValidator  sigmahq\n"
        plugins = _parse_plugin_table(stdout)
        self.assertEqual(
            {p.plugin_type for p in plugins}, {"backend", "pipeline", "validator"}
        )


if __name__ == "__main__":
    unittest.main()
