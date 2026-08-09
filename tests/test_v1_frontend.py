from __future__ import annotations

import json
import unittest
from fractions import Fraction
from pathlib import Path

from tev_script.ast_v1 import (
    BehaviorDecl,
    EnumDecl,
    ForStmt,
    MatchStmt,
    ModuleUnit,
    RecordDecl,
    ScriptUnit,
)
from tev_script.diagnostics import TevScriptError
from tev_script.frontend_v1 import parse_v1_bytes, parse_versioned_bytes
from tev_script.lexer_v1 import LexerV1
from tev_script.source import SourceUnit

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / "conformance" / "v1-source-syntax-cases.json").read_text())


class V1LexerTests(unittest.TestCase):
    def test_all_new_multichar_tokens(self) -> None:
        source = SourceUnit("tokens.tevs", "-> => .. :: == != <= >=")
        kinds = [t.kind for t in LexerV1(source).tokenize()[:-1]]
        self.assertEqual(
            kinds,
            ["ARROW", "FAT_ARROW", "RANGE", "COLONCOLON", "EQEQ", "NE", "LE", "GE"],
        )

    def test_exact_decimal_fraction(self) -> None:
        parsed = parse_v1_bytes(
            "Exact.tevs",
            b'script Exact version "1.0.0"; entity E { state x: Rat = 0.1; on start { return; } }',
        )
        expr = parsed.entities[0].states[0].initial
        self.assertEqual(expr.kind, "rat")
        self.assertEqual(expr.value, Fraction(1, 10))

    def test_unicode_is_allowed_inside_text(self) -> None:
        parsed = parse_v1_bytes(
            "Text.tevs",
            'script Text version "1.0.0"; entity E { on start { log "áβ🙂"; } }'.encode(),
        )
        stmt = parsed.entities[0].handlers[0].body[0]
        self.assertEqual(stmt.expression.value, "áβ🙂")

    def test_decimal_and_range_tokenization_is_unambiguous(self) -> None:
        source = SourceUnit("numeric.tevs", "1.0 1..4 1...4")
        tokens = [(t.kind, t.text) for t in LexerV1(source).tokenize()[:-1]]
        self.assertEqual(
            tokens,
            [
                ("DECIMAL", "1.0"),
                ("INT", "1"), ("RANGE", ".."), ("INT", "4"),
                ("INT", "1"), ("RANGE", ".."), ("DOT", "."), ("INT", "4"),
            ],
        )

    def test_v1_constructor_keywords_are_exact_case_sensitive(self) -> None:
        source = SourceUnit("keywords.tevs", "Option Result Some None Ok Err option result some none ok err")
        kinds = [t.kind for t in LexerV1(source).tokenize()[:-1]]
        self.assertEqual(
            kinds,
            ["OPTION", "RESULT", "SOME", "NONE", "OK", "ERR", "IDENT", "IDENT", "IDENT", "IDENT", "IDENT", "IDENT"],
        )

    def test_supported_string_escapes_are_exact(self) -> None:
        source = SourceUnit("escapes.tevs", r'"a\nb\rc\td\"e\\f"')
        tokens = LexerV1(source).tokenize()
        self.assertEqual(tokens[0].kind, "STRING")
        self.assertEqual(tokens[0].text, 'a\nb\rc\td"e\\f')


class V1PositiveSyntaxCorpusTests(unittest.TestCase):
    def test_positive_corpus(self) -> None:
        for case in CASES["positive"]:
            with self.subTest(case=case["id"]):
                result = parse_v1_bytes(f'{case["id"]}.tevs', case["source"].encode())
                self.assertIn(type(result), {ScriptUnit, ModuleUnit})

    def test_module_export_flags_are_preserved(self) -> None:
        case = next(x for x in CASES["positive"] if x["id"] == "module-exports")
        module = parse_v1_bytes("module.tevs", case["source"].encode())
        self.assertIsInstance(module, ModuleUnit)
        self.assertEqual(module.module_id, "game.math")
        self.assertTrue(all(item.exported for item in module.declarations))

    def test_script_preserves_imports_and_top_declarations(self) -> None:
        source = b'''script Full version "1.0.0";
import game.shared;
capability world.temp(Vec2) -> Rat observation;
record Damage { amount: Int; critical: Bool; }
enum Kind { A; B; }
fn twice(x: Int) -> Int = x * 2;
behavior Base { state alive: Bool = true; on start { log "base"; } }
entity E { use Base; on start { return; } }
'''
        unit = parse_v1_bytes("Full.tevs", source)
        self.assertEqual([x.module_id for x in unit.imports], ["game.shared"])
        self.assertEqual(len(unit.declarations), 5)
        self.assertIsInstance(unit.declarations[1], RecordDecl)
        self.assertIsInstance(unit.declarations[2], EnumDecl)
        self.assertIsInstance(unit.declarations[4], BehaviorDecl)

    def test_nested_option_result_type_shape(self) -> None:
        case = next(x for x in CASES["positive"] if x["id"] == "nested-types")
        unit = parse_v1_bytes("Types.tevs", case["source"].encode())
        type_ref = unit.declarations[0].fields[0].type_ref
        self.assertEqual(type_ref.kind, "result")
        self.assertEqual(type_ref.arguments[0].kind, "option")
        self.assertEqual(type_ref.arguments[0].arguments[0].name, "Int")
        self.assertEqual(type_ref.arguments[1].name, "Text")

    def test_record_constructor_is_unambiguous_with_if_block(self) -> None:
        source = b'''script Parse version "1.0.0";
record R { x: Int; }
entity E {
  state x: Int = 0;
  on update {
    if true { x = 1; }
    let r = R(x = 2);
  }
}
'''
        unit = parse_v1_bytes("Parse.tevs", source)
        body = unit.entities[0].handlers[0].body
        self.assertEqual(body[0].__class__.__name__, "IfStmt")
        self.assertEqual(body[1].expression.kind, "record")
        record_name, fields = body[1].expression.value
        self.assertEqual(record_name, "R")
        self.assertEqual([(f.name, f.expression.value) for f in fields], [("x", 2)])

    def test_operator_precedence_tree(self) -> None:
        case = next(x for x in CASES["positive"] if x["id"] == "complex-precedence")
        unit = parse_v1_bytes("Expr.tevs", case["source"].encode())
        expression = unit.entities[0].handlers[0].body[0].expression
        self.assertEqual((expression.kind, expression.value), ("binary", "or"))
        left, right = expression.children
        self.assertEqual((left.kind, left.value), ("binary", "and"))
        self.assertEqual((right.kind, right.value), ("bool", True))
        comparison = left.children[0]
        self.assertEqual(comparison.value, "<")
        addition = comparison.children[0]
        self.assertEqual(addition.value, "+")
        self.assertEqual(addition.children[1].value, "*")

    def test_for_bounds_and_match_patterns_are_preserved(self) -> None:
        loop_case = next(x for x in CASES["positive"] if x["id"] == "static-for-negative-lower")
        loop_unit = parse_v1_bytes("Loop.tevs", loop_case["source"].encode())
        loop = loop_unit.entities[0].handlers[0].body[0]
        self.assertIsInstance(loop, ForStmt)
        self.assertEqual((loop.lower, loop.upper), (-2, 3))

        sum_case = next(x for x in CASES["positive"] if x["id"] == "option-result")
        sum_unit = parse_v1_bytes("Sums.tevs", sum_case["source"].encode())
        matches = [s for s in sum_unit.entities[0].handlers[0].body if isinstance(s, MatchStmt)]
        self.assertEqual(len(matches), 2)
        self.assertEqual([a.pattern.__class__.__name__ for a in matches[0].arms], ["SomePattern", "NonePattern"])
        self.assertEqual([a.pattern.__class__.__name__ for a in matches[1].arms], ["OkPattern", "ErrPattern"])

    def test_source_spans_keep_original_path(self) -> None:
        unit = parse_v1_bytes(
            "nested/path/Span.tevs",
            b'script Span version "1.0.0"; entity E { on start { return; } }',
        )
        self.assertEqual(unit.span.path, "nested/path/Span.tevs")
        self.assertEqual(unit.entities[0].handlers[0].body[0].span.path, "nested/path/Span.tevs")

    def test_complete_statement_surface_parses_without_token_leakage(self) -> None:
        source = b'''script Statements version "1.0.0";
entity E {
  state x: Int = 0;
  on custom(v: Int) {
    let a = v;
    x = a;
    call audio.play("call");
    emit custom(a);
    log "log";
    move vec2(1, 0);
    animate "Walk";
    if true { x = 2; } else { x = 3; }
    for i in 0 .. 2 { log "loop"; }
    return;
  }
}
'''
        unit = parse_v1_bytes("Statements.tevs", source)
        names = [type(stmt).__name__ for stmt in unit.entities[0].handlers[0].body]
        self.assertEqual(
            names,
            ["LetStmt", "AssignStmt", "CallStmt", "EmitStmt", "LogStmt", "MoveStmt", "AnimateStmt", "IfStmt", "ForStmt", "ReturnStmt"],
        )


class V1NegativeSyntaxCorpusTests(unittest.TestCase):
    def test_negative_corpus_fails_closed_with_expected_category(self) -> None:
        for case in CASES["negative"]:
            with self.subTest(case=case["id"]):
                with self.assertRaises(TevScriptError) as captured:
                    parse_v1_bytes(f'{case["id"]}.tevs', case["source"].encode())
                self.assertEqual(captured.exception.diagnostic.code, case["code"])
                if captured.exception.diagnostic.span is not None:
                    self.assertEqual(captured.exception.diagnostic.span.path, f'{case["id"]}.tevs')

    def test_nul_source_fails_with_language_diagnostic(self) -> None:
        with self.assertRaises(TevScriptError) as captured:
            parse_v1_bytes("nul.tevs", b'script Nul version "1.0.0";\x00')
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_SOURCE_NUL")

    def test_invalid_utf8_fails_with_language_diagnostic(self) -> None:
        with self.assertRaises(TevScriptError) as captured:
            parse_v1_bytes("utf8.tevs", b'\xff')
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_SOURCE_UTF8")


class V1VersionedFrontendTests(unittest.TestCase):
    def test_versioned_dispatch_accepts_v1_script(self) -> None:
        parsed = parse_versioned_bytes(
            "V1.tevs",
            b'script V1 version "1.0.0"; entity E { on start { return; } }',
        )
        self.assertIsInstance(parsed, ScriptUnit)

    def test_versioned_dispatch_accepts_v1_module(self) -> None:
        parsed = parse_versioned_bytes(
            "M.tevs",
            b'module a.b version "1.0.0"; export enum K { A; }',
        )
        self.assertIsInstance(parsed, ModuleUnit)

    def test_versioned_dispatch_preserves_v02_parser_path(self) -> None:
        from tev_script.ast import ScriptDecl

        parsed = parse_versioned_bytes(
            "Compat.tevs",
            b'script Compat version "0.2.0"; entity E { state x: Int = 0; on start { return; } }',
        )
        self.assertIsInstance(parsed, ScriptDecl)
        self.assertEqual(parsed.name, "Compat")
        self.assertEqual(parsed.language_version, "0.2.0")

    def test_versioned_dispatch_rejects_unknown_version_before_compilation(self) -> None:
        with self.assertRaises(TevScriptError) as captured:
            parse_versioned_bytes(
                "Future.tevs",
                b'script Future version "2.0.0"; entity E { on start { return; } }',
            )
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_SOURCE_VERSION_UNSUPPORTED")

    def test_comments_before_header_are_ignored(self) -> None:
        parsed = parse_versioned_bytes(
            "Comment.tevs",
            b'# leading comment\nscript Comment version "1.0.0"; entity E { on start { return; } }',
        )
        self.assertIsInstance(parsed, ScriptUnit)


class V1BudgetTests(unittest.TestCase):
    def test_source_byte_budget(self) -> None:
        with self.assertRaises(TevScriptError) as captured:
            parse_v1_bytes("large.tevs", b" " * 1_000_001)
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_V1_SOURCE_BUDGET")

    def test_call_argument_budget(self) -> None:
        args = ",".join("1" for _ in range(65))
        source = f'script Args version "1.0.0"; entity E {{ on start {{ let x = f({args}); }} }}'.encode()
        with self.assertRaises(TevScriptError) as captured:
            parse_v1_bytes("args.tevs", source)
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_V1_BUDGET_CALL_ARGUMENTS")

    def test_parameter_budget(self) -> None:
        params = ",".join(f"p{i}: Int" for i in range(65))
        source = f'script Params version "1.0.0"; fn f({params}) -> Int = 0; entity E {{ on start {{ return; }} }}'.encode()
        with self.assertRaises(TevScriptError) as captured:
            parse_v1_bytes("params.tevs", source)
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_V1_BUDGET_FUNCTION_PARAMETERS")

    def test_expression_nesting_budget(self) -> None:
        expression = "1"
        for _ in range(129):
            expression = f"({expression})"
        source = f'script Deep version "1.0.0"; entity E {{ state x: Int = {expression}; on start {{ return; }} }}'.encode()
        with self.assertRaises(TevScriptError) as captured:
            parse_v1_bytes("deep.tevs", source)
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_V1_BUDGET_EXPRESSION_NESTING")

    def test_combined_unary_and_parenthesis_depth_uses_one_budget(self) -> None:
        expression = "(" * 70 + ("not " * 70) + "true" + ")" * 70
        source = f'script DeepMix version "1.0.0"; entity E {{ state x: Bool = {expression}; on start {{ return; }} }}'.encode()
        with self.assertRaises(TevScriptError) as captured:
            parse_v1_bytes("deep-mix.tevs", source)
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_V1_BUDGET_EXPRESSION_NESTING")

    def test_type_nesting_budget(self) -> None:
        type_text = "Int"
        for _ in range(129):
            type_text = f"Option<{type_text}>"
        source = f'script DeepType version "1.0.0"; entity E {{ state x: {type_text} = None; on start {{ return; }} }}'.encode()
        with self.assertRaises(TevScriptError) as captured:
            parse_v1_bytes("types-deep.tevs", source)
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_V1_BUDGET_TYPE_NESTING")

    def test_block_nesting_budget(self) -> None:
        body = "return;"
        for _ in range(65):
            body = f"if true {{ {body} }}"
        source = f'script Deep version "1.0.0"; entity E {{ on start {{ {body} }} }}'.encode()
        with self.assertRaises(TevScriptError) as captured:
            parse_v1_bytes("blocks.tevs", source)
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_V1_BUDGET_BLOCK_NESTING")

    def test_nested_static_loop_budget(self) -> None:
        body = 'log "x";'
        for i in range(9):
            body = f"for i{i} in 0 .. 1 {{ {body} }}"
        source = f'script Loops version "1.0.0"; entity E {{ on start {{ {body} }} }}'.encode()
        with self.assertRaises(TevScriptError) as captured:
            parse_v1_bytes("loops.tevs", source)
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_V1_BUDGET_NESTED_STATIC_LOOPS")

    def test_static_loop_iteration_budget(self) -> None:
        source = b'script LoopBudget version "1.0.0"; entity E { on start { for i in 0 .. 1025 { return; } } }'
        with self.assertRaises(TevScriptError) as captured:
            parse_v1_bytes("loop-budget.tevs", source)
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_V1_BUDGET_STATIC_LOOP_ITERATIONS")

    def test_reversed_static_loop_range_fails_closed(self) -> None:
        source = b'script LoopOrder version "1.0.0"; entity E { on start { for i in 5 .. 1 { return; } } }'
        with self.assertRaises(TevScriptError) as captured:
            parse_v1_bytes("loop-order.tevs", source)
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_V1_FOR_RANGE_ORDER")


if __name__ == "__main__":
    unittest.main()
