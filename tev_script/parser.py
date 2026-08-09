from __future__ import annotations

from fractions import Fraction

from .ast import (
    AssignStmt,
    CallStmt,
    EmitStmt,
    EntityDecl,
    Expr,
    HandlerDecl,
    IfStmt,
    LetStmt,
    ParameterDecl,
    ReturnStmt,
    ScriptDecl,
    StateDecl,
    Statement,
)
from .diagnostics import SourceSpan, TevScriptError
from .lexer import Token, decimal_fraction

_PRECEDENCE = {
    "OR": 1,
    "AND": 2,
    "EQEQ": 3,
    "NE": 3,
    "LT": 3,
    "LE": 3,
    "GT": 3,
    "GE": 3,
    "PLUS": 4,
    "MINUS": 4,
    "STAR": 5,
    "SLASH": 5,
}


class Parser:
    def __init__(self, tokens: tuple[Token, ...]) -> None:
        self.tokens = tokens
        self.index = 0

    def parse_script(self) -> ScriptDecl:
        start = self._expect("SCRIPT").span
        name = self._expect("IDENT").text
        self._expect("VERSION")
        language_version = self._expect("STRING").text
        self._expect("SEMI")
        entities: list[EntityDecl] = []
        while not self._at("EOF"):
            entities.append(self._entity())
        if not entities:
            raise TevScriptError(
                "TEVS_PARSE_ENTITY_MISSING",
                "a script requires at least one entity",
                start,
            )
        return ScriptDecl(
            name=name,
            language_version=language_version,
            entities=tuple(entities),
            span=self._merge(start, self._current().span),
        )

    def _entity(self) -> EntityDecl:
        start = self._expect("ENTITY").span
        name = self._expect("IDENT").text
        self._expect("LBRACE")
        states: list[StateDecl] = []
        handlers: list[HandlerDecl] = []
        while not self._at("RBRACE"):
            if self._at("STATE"):
                states.append(self._state())
            elif self._at("ON"):
                handlers.append(self._handler())
            else:
                token = self._current()
                raise TevScriptError(
                    "TEVS_PARSE_ENTITY_MEMBER",
                    f"expected state or on, got {token.kind}",
                    token.span,
                )
        end = self._expect("RBRACE").span
        return EntityDecl(name, tuple(states), tuple(handlers), self._merge(start, end))

    def _state(self) -> StateDecl:
        start = self._expect("STATE").span
        name = self._expect("IDENT").text
        self._expect("COLON")
        type_name = self._expect("IDENT").text
        self._expect("EQUAL")
        initial = self._expression()
        end = self._expect("SEMI").span
        return StateDecl(name, type_name, initial, self._merge(start, end))

    def _handler(self) -> HandlerDecl:
        start = self._expect("ON").span
        event_id = self._expect("IDENT").text
        parameters: list[ParameterDecl] = []
        if self._match("LPAREN"):
            if not self._at("RPAREN"):
                while True:
                    p_start = self._current().span
                    name = self._expect("IDENT").text
                    self._expect("COLON")
                    type_name = self._expect("IDENT").text
                    parameters.append(
                        ParameterDecl(name, type_name, self._merge(p_start, self._previous().span))
                    )
                    if not self._match("COMMA"):
                        break
            self._expect("RPAREN")
        body, end = self._block()
        return HandlerDecl(event_id, tuple(parameters), body, self._merge(start, end))

    def _block(self) -> tuple[tuple[Statement, ...], SourceSpan]:
        self._expect("LBRACE")
        statements: list[Statement] = []
        while not self._at("RBRACE"):
            statements.append(self._statement())
        end = self._expect("RBRACE").span
        return tuple(statements), end

    def _statement(self) -> Statement:
        token = self._current()
        if self._match("LET"):
            return self._let(token.span)
        if self._match("IF"):
            return self._if(token.span)
        if self._match("CALL"):
            return self._call_statement(token.span)
        if self._match("EMIT"):
            return self._emit(token.span)
        if self._match("RETURN"):
            end = self._expect("SEMI").span
            return ReturnStmt(self._merge(token.span, end))
        if self._match("LOG"):
            expr = self._expression()
            end = self._expect("SEMI").span
            return CallStmt("debug.log", (expr,), self._merge(token.span, end))
        if self._match("MOVE"):
            expr = self._expression()
            end = self._expect("SEMI").span
            return CallStmt(
                "motion.move2d",
                (expr,),
                self._merge(token.span, end),
            )
        if self._match("ANIMATE"):
            expr = self._expression()
            end = self._expect("SEMI").span
            return CallStmt(
                "animation.play",
                (expr,),
                self._merge(token.span, end),
            )
        if self._at("IDENT") and self._peek(1).kind == "EQUAL":
            name = self._advance().text
            self._expect("EQUAL")
            expr = self._expression()
            end = self._expect("SEMI").span
            return AssignStmt(name, expr, self._merge(token.span, end))
        raise TevScriptError(
            "TEVS_PARSE_STATEMENT",
            f"unexpected statement token {token.kind}",
            token.span,
            "Use let, assignment, if, call, emit, log, move, animate, or return",
        )

    def _let(self, start: SourceSpan) -> LetStmt:
        name = self._expect("IDENT").text
        type_name: str | None = None
        if self._match("COLON"):
            type_name = self._expect("IDENT").text
        self._expect("EQUAL")
        expr = self._expression()
        end = self._expect("SEMI").span
        return LetStmt(name, type_name, expr, self._merge(start, end))

    def _if(self, start: SourceSpan) -> IfStmt:
        condition = self._expression()
        then_body, then_end = self._block()
        else_body: tuple[Statement, ...] = ()
        end = then_end
        if self._match("ELSE"):
            else_body, end = self._block()
        return IfStmt(condition, then_body, else_body, self._merge(start, end))

    def _call_statement(self, start: SourceSpan) -> CallStmt:
        capability_id = self._qualified_name()
        arguments, end = self._arguments()
        semi = self._expect("SEMI").span
        return CallStmt(capability_id, arguments, self._merge(start, semi))

    def _emit(self, start: SourceSpan) -> EmitStmt:
        event_id = self._expect("IDENT").text
        arguments, _ = self._arguments()
        end = self._expect("SEMI").span
        return EmitStmt(event_id, arguments, self._merge(start, end))

    def _expression(self, minimum: int = 1) -> Expr:
        left = self._prefix()
        while True:
            token = self._current()
            precedence = _PRECEDENCE.get(token.kind, 0)
            if precedence < minimum:
                break
            operator = self._advance()
            right = self._expression(precedence + 1)
            left = Expr(
                "binary",
                operator.kind,
                (left, right),
                self._merge(left.span, right.span),
            )
        return left

    def _prefix(self) -> Expr:
        token = self._current()
        if token.kind in {"MINUS", "NOT"}:
            operator = self._advance()
            child = self._expression(6)
            return Expr(
                "unary",
                operator.kind,
                (child,),
                self._merge(operator.span, child.span),
            )
        if token.kind == "INT":
            self._advance()
            return Expr("int", int(token.text), (), token.span)
        if token.kind == "DECIMAL":
            self._advance()
            return Expr("rat", decimal_fraction(token.text), (), token.span)
        if token.kind == "STRING":
            self._advance()
            return Expr("text", token.text, (), token.span)
        if token.kind in {"TRUE", "FALSE"}:
            self._advance()
            return Expr("bool", token.kind == "TRUE", (), token.span)
        if token.kind == "IDENT":
            start = token.span
            name = self._qualified_name()
            if self._at("LPAREN"):
                arguments, end = self._arguments()
                return Expr("call", name, arguments, self._merge(start, end))
            return Expr("name", name, (), self._merge(start, self._previous().span))
        if token.kind == "LPAREN":
            start = self._advance().span
            inner = self._expression()
            end = self._expect("RPAREN").span
            return Expr(inner.kind, inner.value, inner.children, self._merge(start, end))
        raise TevScriptError(
            "TEVS_PARSE_EXPRESSION",
            f"unexpected expression token {token.kind}",
            token.span,
        )

    def _qualified_name(self) -> str:
        parts = [self._expect("IDENT").text]
        while self._match("DOT"):
            parts.append(self._expect("IDENT").text)
        return ".".join(parts)

    def _arguments(self) -> tuple[tuple[Expr, ...], SourceSpan]:
        self._expect("LPAREN")
        arguments: list[Expr] = []
        if not self._at("RPAREN"):
            while True:
                arguments.append(self._expression())
                if not self._match("COMMA"):
                    break
        end = self._expect("RPAREN").span
        return tuple(arguments), end

    def _current(self) -> Token:
        return self.tokens[self.index]

    def _previous(self) -> Token:
        return self.tokens[max(0, self.index - 1)]

    def _peek(self, offset: int) -> Token:
        return self.tokens[min(len(self.tokens) - 1, self.index + offset)]

    def _at(self, kind: str) -> bool:
        return self._current().kind == kind

    def _advance(self) -> Token:
        token = self._current()
        if token.kind != "EOF":
            self.index += 1
        return token

    def _match(self, kind: str) -> bool:
        if self._at(kind):
            self._advance()
            return True
        return False

    def _expect(self, kind: str) -> Token:
        token = self._current()
        if token.kind != kind:
            raise TevScriptError(
                "TEVS_PARSE_EXPECTED_TOKEN",
                f"expected {kind}, got {token.kind}",
                token.span,
            )
        return self._advance()

    @staticmethod
    def _merge(left: SourceSpan, right: SourceSpan) -> SourceSpan:
        return SourceSpan(
            path=left.path,
            start_offset=left.start_offset,
            end_offset=right.end_offset,
            line=left.line,
            column=left.column,
        )
