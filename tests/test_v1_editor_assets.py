from __future__ import annotations

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
EDITOR = ROOT / "editors" / "vscode"


class V1EditorAssetTests(unittest.TestCase):
    def test_package_is_static_zero_dependency_language_support(self) -> None:
        package = self._load("package.json")
        self.assertTrue(package["private"])
        self.assertEqual(package["categories"], ["Programming Languages"])
        self.assertNotIn("dependencies", package)
        self.assertNotIn("devDependencies", package)
        self.assertNotIn("scripts", package)
        self.assertNotIn("activationEvents", package)
        self.assertNotIn("main", package)
        self.assertNotIn("browser", package)
        contributes = package["contributes"]
        language = contributes["languages"][0]
        self.assertEqual(language["id"], "tevscript")
        self.assertIn(".tevs", language["extensions"])
        self.assertEqual(language["configuration"], "./language-configuration.json")
        grammar = contributes["grammars"][0]
        self.assertEqual(grammar["language"], "tevscript")
        self.assertEqual(grammar["scopeName"], "source.tevscript")
        self.assertEqual(grammar["path"], "./syntaxes/tevscript.tmLanguage.json")

    def test_language_configuration_matches_portable_lexical_surface(self) -> None:
        config = self._load("language-configuration.json")
        self.assertEqual(config["comments"]["lineComment"], "#")
        self.assertIn(["{", "}"], config["brackets"])
        self.assertIn(["(", ")"], config["brackets"])
        self.assertIn(["<", ">"], config["brackets"])
        self.assertEqual(config["wordPattern"], "[A-Za-z_][A-Za-z0-9_]*")

    def test_textmate_grammar_covers_v1_keywords_and_algebraic_constructs(self) -> None:
        grammar = self._load("syntaxes/tevscript.tmLanguage.json")
        self.assertEqual(grammar["scopeName"], "source.tevscript")
        text = json.dumps(grammar, ensure_ascii=True, sort_keys=True)
        for token in (
            "script",
            "module",
            "import",
            "export",
            "capability",
            "observation",
            "effect",
            "record",
            "enum",
            "fn",
            "behavior",
            "entity",
            "use",
            "state",
            "match",
            "for",
            "Option",
            "Result",
            "Some",
            "None",
            "Ok",
            "Err",
            "Bool",
            "Int",
            "Rat",
            "Text",
            "Vec2",
            "Vec3",
            "Unit",
        ):
            self.assertIn(token, text)
        for operator in ("->", "=>", "::"):
            self.assertIn(operator, text)
        self.assertIn("comment.line.number-sign.tevscript", text)
        self.assertIn("invalid.illegal.escape.tevscript", text)

    def test_snippets_cover_core_v1_authoring_shapes(self) -> None:
        snippets = self._load("snippets/tevscript.json")
        required = {
            "V1 script",
            "V1 module",
            "Entity",
            "Behavior",
            "Record",
            "Enum",
            "Pure function",
            "Capability observation",
            "Capability effect",
            "Option match",
            "Result match",
            "Bounded for",
            "Event handler",
        }
        self.assertTrue(required.issubset(snippets))
        bodies = "\n".join(
            "\n".join(value["body"])
            for value in snippets.values()
        )
        self.assertIn('version \"1.0.0\";', bodies)
        self.assertIn("Some(", bodies)
        self.assertIn("Err(", bodies)
        self.assertIn(" .. ", bodies)

    def test_editor_readme_preserves_one_semantic_authority_with_external_lsp(self) -> None:
        readme = (EDITOR / "README.md").read_text(encoding="utf-8")
        for phrase in (
            "zero-runtime, zero-dependency",
            "does **not** provide",
            "independent parser",
            "second type checker",
            "formatter",
            "external thin LSP adapter",
            "tev-script-v1-lsp",
            "canonical V1 parser/linker/static-semantic pipeline",
            "VS Code lexical package -> presentation only",
            "external V1 LSP         -> protocol adapter only",
            "V1 compiler pipeline    -> semantic authority",
        ):
            self.assertIn(phrase, readme)

    @staticmethod
    def _load(relative: str) -> dict[str, object]:
        path = EDITOR / relative
        return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
