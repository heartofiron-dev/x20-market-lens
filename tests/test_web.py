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


if __name__ == "__main__":
    unittest.main()
