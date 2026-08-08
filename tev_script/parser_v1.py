from __future__ import annotations

from .ast_v1 import (
    AnimateStmt,
    AssignStmt,
    BehaviorDecl,
    CallStmt,
    CapabilityDecl,
    EmitStmt,
    EntityDecl,
    EnumDecl,
    EnumPattern,
    ErrPattern,
    Expr,
    FieldInit,
    ForStmt,
    FunctionDecl,
    HandlerDecl,
    IfStmt,
    ImportDecl,
    LetStmt,
    LogStmt,
    MatchArm,
    MatchStmt,
    ModuleUnit,
    MoveStmt,
    NonePattern,
    OkPattern,
    ParameterDecl,
    Pattern,
    RecordDecl,
    RecordFieldDecl,
    ReturnStmt,
    ScriptUnit,
    SomePattern,
    SourceFile,
    StateDecl,
    Statement,
    TopDecl,
    TypeRef,
    UseDecl,
)
from .contracts_v1 import MAX_BLOCK_NESTING, MAX_EXPRESSION_NESTING, MAX_TYPE_NESTING
from .diagnostics import SourceSpan, TevScriptError
from .lexer_v1 import Token, decimal_fraction


_BINARY = {
    "OR": (1, "or"),
    "AND": (2, "and"),
    "EQEQ": (3, "=="),
    "NE": (3, "!="),
    "LT": (4, "<"),
    "LE": (4, "<="),
    "GT": (4, ">"),
    "GE": (4, ">="),
    "PLUS": (5, "+"),
    "MINUS": (5, "-"),
    "STAR": (6, "*"),
    "SLASH": (6, "/"),
}

_TOP_DECL_START = {"CAPABILITY", "RECORD", "ENUM", "FN", "BEHAVIOR"}


class ParserV1:
    def __init__(self, tokens: tuple[Token, ...]) -> None:
        self.tokens = tokens
        self.index = 0
        self._block_depth = 0
        self._expression_depth = 0
        self._unary_depth = 0
        self._type_depth = 0

    def parse_source_file(self) -> SourceFile:
        if self._at("SCRIPT"):
            return self._script_unit()
        if self._at("MODULE"):
            return self._module_unit()
        token = self._current()
        raise TevScriptError(
            "TEVS_V1_PARSE_SOURCE_KIND",
            f"expected script or module, got {token.kind}",
            token.span,
        )

    def _script_unit(self) -> ScriptUnit:
        start = self._expect("SCRIPT").span
        program_id = self._expect("IDENT").text
        self._expect("VERSION")
        version = self._expect("STRING").text
        self._expect("SEMI")
        imports = self._imports()
        declarations: list[TopDecl] = []
        while self._current().kind in _TOP_DECL_START:
            declarations.append(self._top_decl(exported=False))
        entities: list[EntityDecl] = []
        while self._at("ENTITY"):
            entities.append(self._entity())
        if not entities:
            raise TevScriptError(
                "TEVS_V1_PARSE_ENTITY_MISSING",
                "a V1 script requires at least one entity",
                self._current().span,
            )
        end = self._expect("EOF").span
        return ScriptUnit(
            program_id,
            version,
            tuple(imports),
            tuple(declarations),
            tuple(entities),
            self._merge(start, end),
        )

    def _module_unit(self) -> ModuleUnit:
        start = self._expect("MODULE").span
        module_id = self._qualified_name()
        self._expect("VERSION")
        version = self._expect("STRING").text
        self._expect("SEMI")
        imports = self._imports()
        declarations: list[TopDecl] = []
        while self._at("EXPORT") or self._current().kind in _TOP_DECL_START:
            exported = self._match("EXPORT")
            if self._current().kind not in _TOP_DECL_START:
                raise TevScriptError(
                    "TEVS_V1_PARSE_EXPORT_TARGET",
                    "export must prefix a module top-level declaration",
                    self._current().span,
                )
            declarations.append(self._top_decl(exported=exported))
        end = self._expect("EOF").span
        return ModuleUnit(
            module_id,
            version,
            tuple(imports),
            tuple(declarations),
            self._merge(start, end),
        )

    def _imports(self) -> list[ImportDecl]:
        result: list[ImportDecl] = []
        while self._at("IMPORT"):
            start = self._advance().span
            module_id = self._qualified_name()
            end = self._expect("SEMI").span
            result.append(ImportDecl(module_id, self._merge(start, end)))
        return result

    def _top_decl(self, *, exported: bool) -> TopDecl:
        if self._at("CAPABILITY"):
            return self._capability(exported)
        if self._at("RECORD"):
            return self._record(exported)
        if self._at("ENUM"):
            return self._enum(exported)
        if self._at("FN"):
            return self._function(exported)
        if self._at("BEHAVIOR"):
            return self._behavior(exported)
        token = self._current()
        raise TevScriptError(
            "TEVS_V1_PARSE_TOP_DECL",
            f"unexpected top-level declaration token {token.kind}",
            token.span,
        )

    def _capability(self, exported: bool) -> CapabilityDecl:
        start = self._expect("CAPABILITY").span
        capability_id = self._qualified_name()
        self._expect("LPAREN")
        parameters: list[TypeRef] = []
        if not self._at("RPAREN"):
            while True:
                parameters.append(self._type_ref())
                if not self._match("COMMA"):
                    break
        self._expect("RPAREN")
        self._expect("ARROW")
        return_type = self._type_ref()
        kind_token = self._current()
        if self._match("OBSERVATION"):
            kind = "observation"
        elif self._match("EFFECT"):
            kind = "effect"
        else:
            raise TevScriptError(
                "TEVS_V1_PARSE_CAPABILITY_KIND",
                "capability kind must be observation or effect",
                kind_token.span,
            )
        end = self._expect("SEMI").span
        return CapabilityDecl(
            capability_id,
            tuple(parameters),
            return_type,
            kind,
            exported,
            self._merge(start, end),
        )

    def _record(self, exported: bool) -> RecordDecl:
        start = self._expect("RECORD").span
        name = self._expect("IDENT").text
        self._expect("LBRACE")
        fields: list[RecordFieldDecl] = []
        while not self._at("RBRACE"):
            f_start = self._current().span
            field_name = self._expect("IDENT").text
            self._expect("COLON")
            type_ref = self._type_ref()
            end = self._expect("SEMI").span
            fields.append(RecordFieldDecl(field_name, type_ref, self._merge(f_start, end)))
        if not fields:
            raise TevScriptError(
                "TEVS_V1_PARSE_RECORD_FIELD_MISSING",
                "a record requires at least one field",
                self._current().span,
            )
        end = self._expect("RBRACE").span
        return RecordDecl(name, tuple(fields), exported, self._merge(start, end))

    def _enum(self, exported: bool) -> EnumDecl:
        start = self._expect("ENUM").span
        name = self._expect("IDENT").text
        self._expect("LBRACE")
        variants: list[str] = []
        while not self._at("RBRACE"):
            variants.append(self._expect("IDENT").text)
            self._expect("SEMI")
        if not variants:
            raise TevScriptError(
                "TEVS_V1_PARSE_ENUM_VARIANT_MISSING",
                "an enum requires at least one variant",
                self._current().span,
            )
        end = self._expect("RBRACE").span
        return EnumDecl(name, tuple(variants), exported, self._merge(start, end))

    def _function(self, exported: bool) -> FunctionDecl:
        start = self._expect("FN").span
        name = self._expect("IDENT").text
        parameters, _ = self._parameter_list()
        self._expect("ARROW")
        return_type = self._type_ref()
        self._expect("EQUAL")
        expression = self._expression()
        end = self._expect("SEMI").span
        return FunctionDecl(
            name,
            parameters,
            return_type,
            expression,
            exported,
            self._merge(start, end),
        )

    def _behavior(self, exported: bool) -> BehaviorDecl:
        start = self._expect("BEHAVIOR").span
        name = self._expect("IDENT").text
        self._expect("LBRACE")
        uses: list[UseDecl] = []
        states: list[StateDecl] = []
        handlers: list[HandlerDecl] = []
        while not self._at("RBRACE"):
            if self._at("USE"):
                uses.append(self._use())
            elif self._at("STATE"):
                states.append(self._state())
            elif self._at("ON"):
                handlers.append(self._handler())
            else:
                token = self._current()
                raise TevScriptError(
                    "TEVS_V1_PARSE_BEHAVIOR_MEMBER",
                    f"expected use, state, or on, got {token.kind}",
                    token.span,
                )
        end = self._expect("RBRACE").span
        return BehaviorDecl(
            name,
            tuple(uses),
            tuple(states),
            tuple(handlers),
            exported,
            self._merge(start, end),
        )

    def _entity(self) -> EntityDecl:
        start = self._expect("ENTITY").span
        name = self._expect("IDENT").text
        self._expect("LBRACE")
        uses: list[UseDecl] = []
        states: list[StateDecl] = []
        handlers: list[HandlerDecl] = []
        while not self._at("RBRACE"):
            if self._at("USE"):
                uses.append(self._use())
            elif self._at("STATE"):
                states.append(self._state())
            elif self._at("ON"):
                handlers.append(self._handler())
            else:
                token = self._current()
                raise TevScriptError(
                    "TEVS_V1_PARSE_ENTITY_MEMBER",
                    f"expected use, state, or on, got {token.kind}",
                    token.span,
                )
        end = self._expect("RBRACE").span
        return EntityDecl(name, tuple(uses), tuple(states), tuple(handlers), self._merge(start, end))

    def _use(self) -> UseDecl:
        start = self._expect("USE").span
        behavior_id = self._qualified_name()
        end = self._expect("SEMI").span
        return UseDecl(behavior_id, self._merge(start, end))

    def _state(self) -> StateDecl:
        start = self._expect("STATE").span
        name = self._expect("IDENT").text
        self._expect("COLON")
        type_ref = self._type_ref()
        self._expect("EQUAL")
        initial = self._expression()
        end = self._expect("SEMI").span
        return StateDecl(name, type_ref, initial, self._merge(start, end))

    def _handler(self) -> HandlerDecl:
        start = self._expect("ON").span
        event_id = self._expect("IDENT").text
        if self._at("LPAREN"):
            parameters, _ = self._parameter_list()
        else:
            parameters = ()
        body, end = self._block()
        return HandlerDecl(event_id, parameters, body, self._merge(start, end))

    def _parameter_list(self) -> tuple[tuple[ParameterDecl, ...], SourceSpan]:
        self._expect("LPAREN")
        parameters: list[ParameterDecl] = []
        if not self._at("RPAREN"):
            while True:
                start = self._current().span
                name = self._expect("IDENT").text
                self._expect("COLON")
                type_ref = self._type_ref()
                parameters.append(ParameterDecl(name, type_ref, self._merge(start, type_ref.span)))
                if not self._match("COMMA"):
                    break
        end = self._expect("RPAREN").span
        return tuple(parameters), end

    def _type_ref(self) -> TypeRef:
        self._type_depth += 1
        if self._type_depth > MAX_TYPE_NESTING:
            self._type_depth -= 1
            raise TevScriptError(
                "TEVS_V1_BUDGET_TYPE_NESTING",
                f"type nesting exceeds {MAX_TYPE_NESTING}",
                self._current().span,
            )
        try:
            start = self._current().span
            if self._match("OPTION"):
                self._expect("LT")
                argument = self._type_ref()
                end = self._expect("GT").span
                return TypeRef.option(argument, self._merge(start, end))
            if self._match("RESULT"):
                self._expect("LT")
                ok = self._type_ref()
                self._expect("COMMA")
                err = self._type_ref()
                end = self._expect("GT").span
                return TypeRef.result(ok, err, self._merge(start, end))
            name = self._qualified_name()
            if name in {"Option", "Result"}:
                raise TevScriptError(
                    "TEVS_V1_PARSE_TYPE_ARGUMENTS",
                    f"{name} requires type arguments",
                    start,
                )
            return TypeRef.named(name, self._merge(start, self._previous().span))
        finally:
            self._type_depth -= 1

    def _block(self) -> tuple[tuple[Statement, ...], SourceSpan]:
        start = self._expect("LBRACE").span
        self._block_depth += 1
        if self._block_depth > MAX_BLOCK_NESTING:
            self._block_depth -= 1
            raise TevScriptError(
                "TEVS_V1_BUDGET_BLOCK_NESTING",
                f"lexical block nesting exceeds {MAX_BLOCK_NESTING}",
                start,
            )
        try:
            body: list[Statement] = []
            while not self._at("RBRACE"):
                if self._at("EOF"):
                    raise TevScriptError(
                        "TEVS_V1_PARSE_BLOCK_UNTERMINATED",
                        "unterminated block",
                        self._current().span,
                    )
                body.append(self._statement())
            end = self._expect("RBRACE").span
            return tuple(body), end
        finally:
            self._block_depth -= 1

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
        if self._match("LOG"):
            expression = self._expression()
            end = self._expect("SEMI").span
            return LogStmt(expression, self._merge(token.span, end))
        if self._match("MOVE"):
            expression = self._expression()
            end = self._expect("SEMI").span
            return MoveStmt(expression, self._merge(token.span, end))
        if self._match("ANIMATE"):
            expression = self._expression()
            end = self._expect("SEMI").span
            return AnimateStmt(expression, self._merge(token.span, end))
        if self._match("MATCH"):
            return self._match_statement(token.span)
        if self._match("FOR"):
            return self._for(token.span)
        if self._match("RETURN"):
            end = self._expect("SEMI").span
            return ReturnStmt(self._merge(token.span, end))
        if self._at("IDENT") and self._peek(1).kind == "EQUAL":
            name = self._advance().text
            self._expect("EQUAL")
            expression = self._expression()
            end = self._expect("SEMI").span
            return AssignStmt(name, expression, self._merge(token.span, end))
        raise TevScriptError(
            "TEVS_V1_PARSE_STATEMENT",
            f"unexpected statement token {token.kind}",
            token.span,
        )

    def _let(self, start: SourceSpan) -> LetStmt:
        name = self._expect("IDENT").text
        type_ref: TypeRef | None = None
        if self._match("COLON"):
            type_ref = self._type_ref()
        self._expect("EQUAL")
        expression = self._expression()
        end = self._expect("SEMI").span
        return LetStmt(name, type_ref, expression, self._merge(start, end))

    def _if(self, start: SourceSpan) -> IfStmt:
        condition = self._expression()
        then_body, end = self._block()
        else_body: tuple[Statement, ...] = ()
        if self._match("ELSE"):
            else_body, end = self._block()
        return IfStmt(condition, then_body, else_body, self._merge(start, end))

    def _call_statement(self, start: SourceSpan) -> CallStmt:
        capability_id = self._qualified_name()
        arguments, _ = self._arguments()
        end = self._expect("SEMI").span
        return CallStmt(capability_id, arguments, self._merge(start, end))

    def _emit(self, start: SourceSpan) -> EmitStmt:
        event_id = self._expect("IDENT").text
        arguments, _ = self._arguments()
        end = self._expect("SEMI").span
        return EmitStmt(event_id, arguments, self._merge(start, end))

    def _for(self, start: SourceSpan) -> ForStmt:
        variable = self._expect("IDENT").text
        self._expect("IN")
        lower = self._signed_int()
        self._expect("RANGE")
        upper = self._signed_int()
        body, end = self._block()
        return ForStmt(variable, lower, upper, body, self._merge(start, end))

    def _signed_int(self) -> int:
        sign = -1 if self._match("MINUS") else 1
        token = self._expect("INT")
        return sign * int(token.text)

    def _match_statement(self, start: SourceSpan) -> MatchStmt:
        expression = self._expression()
        self._expect("LBRACE")
        arms: list[MatchArm] = []
        while not self._at("RBRACE"):
            p_start = self._current().span
            pattern = self._pattern()
            self._expect("FAT_ARROW")
            body, end = self._block()
            arms.append(MatchArm(pattern, body, self._merge(p_start, end)))
        if not arms:
            raise TevScriptError(
                "TEVS_V1_PARSE_MATCH_ARM_MISSING",
                "match requires at least one arm",
                self._current().span,
            )
        end = self._expect("RBRACE").span
        return MatchStmt(expression, tuple(arms), self._merge(start, end))

    def _pattern(self) -> Pattern:
        start = self._current().span
        if self._match("SOME"):
            self._expect("LPAREN")
            binding = self._expect("IDENT").text
            end = self._expect("RPAREN").span
            return SomePattern(binding, self._merge(start, end))
        if self._match("NONE"):
            return NonePattern(start)
        if self._match("OK"):
            self._expect("LPAREN")
            binding = self._expect("IDENT").text
            end = self._expect("RPAREN").span
            return OkPattern(binding, self._merge(start, end))
        if self._match("ERR"):
            self._expect("LPAREN")
            binding = self._expect("IDENT").text
            end = self._expect("RPAREN").span
            return ErrPattern(binding, self._merge(start, end))
        type_name = self._qualified_name()
        self._expect("COLONCOLON")
        variant = self._expect("IDENT").text
        return EnumPattern(type_name, variant, self._merge(start, self._previous().span))

    def _expression(self, minimum: int = 1) -> Expr:
        self._expression_depth += 1
        if self._expression_depth > MAX_EXPRESSION_NESTING:
            self._expression_depth -= 1
            raise TevScriptError(
                "TEVS_V1_BUDGET_EXPRESSION_NESTING",
                f"expression nesting exceeds {MAX_EXPRESSION_NESTING}",
                self._current().span,
            )
        try:
            left = self._unary()
            while True:
                token = self._current()
                item = _BINARY.get(token.kind)
                if item is None or item[0] < minimum:
                    break
                precedence, operator_text = item
                self._advance()
                right = self._expression(precedence + 1)
                left = Expr(
                    "binary",
                    operator_text,
                    (left, right),
                    self._merge(left.span, right.span),
                )
            return left
        finally:
            self._expression_depth -= 1

    def _unary(self) -> Expr:
        token = self._current()
        if token.kind in {"NOT", "MINUS"}:
            self._unary_depth += 1
            if self._expression_depth + self._unary_depth > MAX_EXPRESSION_NESTING:
                self._unary_depth -= 1
                raise TevScriptError(
                    "TEVS_V1_BUDGET_EXPRESSION_NESTING",
                    f"expression nesting exceeds {MAX_EXPRESSION_NESTING}",
                    token.span,
                )
            try:
                if self._match("NOT"):
                    child = self._unary()
                    return Expr("unary", "not", (child,), self._merge(token.span, child.span))
                self._expect("MINUS")
                child = self._unary()
                return Expr("unary", "-", (child,), self._merge(token.span, child.span))
            finally:
                self._unary_depth -= 1
        return self._postfix()

    def _postfix(self) -> Expr:
        expression = self._primary()
        while True:
            if self._at("LPAREN"):
                arguments, end = self._arguments()
                expression = Expr(
                    "call",
                    None,
                    (expression, *arguments),
                    self._merge(expression.span, end),
                )
                continue
            if self._match("DOT"):
                field = self._expect("IDENT")
                expression = Expr(
                    "field",
                    field.text,
                    (expression,),
                    self._merge(expression.span, field.span),
                )
                continue
            break
        return expression

    def _primary(self) -> Expr:
        token = self._current()
        if self._match("TRUE"):
            return Expr("bool", True, (), token.span)
        if self._match("FALSE"):
            return Expr("bool", False, (), token.span)
        if self._match("INT"):
            return Expr("int", int(token.text), (), token.span)
        if self._match("DECIMAL"):
            return Expr("rat", decimal_fraction(token.text), (), token.span)
        if self._match("STRING"):
            return Expr("text", token.text, (), token.span)
        if self._match("SOME"):
            start = token.span
            self._expect("LPAREN")
            value = self._expression()
            end = self._expect("RPAREN").span
            return Expr("some", None, (value,), self._merge(start, end))
        if self._match("NONE"):
            return Expr("none", None, (), token.span)
        if self._match("OK"):
            start = token.span
            self._expect("LPAREN")
            value = self._expression()
            end = self._expect("RPAREN").span
            return Expr("ok", None, (value,), self._merge(start, end))
        if self._match("ERR"):
            start = token.span
            self._expect("LPAREN")
            value = self._expression()
            end = self._expect("RPAREN").span
            return Expr("err", None, (value,), self._merge(start, end))
        if self._match("LPAREN"):
            start = token.span
            inner = self._expression()
            end = self._expect("RPAREN").span
            return Expr("group", None, (inner,), self._merge(start, end))
        if self._at("IDENT"):
            start = token.span
            name = self._qualified_name()
            if self._match("COLONCOLON"):
                variant = self._expect("IDENT")
                return Expr(
                    "enum",
                    (name, variant.text),
                    (),
                    self._merge(start, variant.span),
                )
            if self._looks_like_named_constructor_arguments():
                fields, end = self._field_arguments()
                return Expr("record", (name, fields), (), self._merge(start, end))
            return Expr("name", name, (), self._merge(start, self._previous().span))
        raise TevScriptError(
            "TEVS_V1_PARSE_EXPRESSION",
            f"unexpected expression token {token.kind}",
            token.span,
        )

    def _looks_like_named_constructor_arguments(self) -> bool:
        return (
            self._at("LPAREN")
            and self._peek(1).kind == "IDENT"
            and self._peek(2).kind == "EQUAL"
        )

    def _field_arguments(self) -> tuple[tuple[FieldInit, ...], SourceSpan]:
        self._expect("LPAREN")
        fields: list[FieldInit] = []
        while True:
            start = self._current().span
            name = self._expect("IDENT").text
            self._expect("EQUAL")
            expression = self._expression()
            fields.append(FieldInit(name, expression, self._merge(start, expression.span)))
            if not self._match("COMMA"):
                break
            if self._at("RPAREN"):
                break
        end = self._expect("RPAREN").span
        return tuple(fields), end

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

    def _qualified_name(self) -> str:
        parts = [self._expect("IDENT").text]
        while self._at("DOT") and self._peek(1).kind == "IDENT":
            self._advance()
            parts.append(self._advance().text)
        return ".".join(parts)

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
                "TEVS_V1_PARSE_EXPECTED_TOKEN",
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
