from pathlib import Path
import unittest


class SymbolInputRegressionTests(unittest.TestCase):
    def test_live_render_does_not_overwrite_symbol_being_edited(self) -> None:
        source = (Path(__file__).parents[1] / "web" / "app.js").read_text(encoding="utf-8")
        self.assertIn("syncSymbolInput(data.symbol);", source)
        self.assertIn("if (!symbolEditing) $('symbol-input').value = symbol;", source)
        self.assertNotIn("$('symbol-input').value = data.symbol;", source)
        self.assertNotIn("$('symbol-input').addEventListener('blur'", source)
        self.assertIn("if (event.key === 'Escape')", source)

    def test_market_and_currency_are_rendered_from_snapshot(self) -> None:
        source = (Path(__file__).parents[1] / "web" / "app.js").read_text(encoding="utf-8")
        self.assertIn("data.instrument.market_label", source)
        self.assertIn("data.quote.currency", source)
        self.assertIn("data.instrument.regulator", source)


if __name__ == "__main__":
    unittest.main()
