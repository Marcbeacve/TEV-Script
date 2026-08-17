from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Callable, Mapping

from .diagnostics import TevScriptError

MAX_TYPE_NESTING_V2 = 128
MAX_COLLECTION_CAPACITY_V2 = 4096
_PRIMITIVES = frozenset({"Bool","Int","Rat","Text","Vec2","Vec3","Unit"})
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")
_TOKEN = re.compile(r"\s*(?:(?P<name>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)|(?P<int>0|[1-9][0-9]*)|(?P<scope>::)|(?P<lt><)|(?P<gt>>)|(?P<comma>,))")


@dataclass(frozen=True, slots=True)
class TypeRefV2:
    kind: str
    name: str
    arguments: tuple["TypeRefV2", ...] = ()
    const_arguments: tuple[int, ...] = ()

    @property
    def collection_capacity(self) -> int | None:
        return self.const_arguments[0] if self.kind in {"list","set","map"} else None

    @property
    def array_length(self) -> int | None:
        return self.const_arguments[0] if self.kind == "array" else None


@dataclass(frozen=True, slots=True)
class ResolvedTypeV2:
    kind: str
    type_id: str
    arguments: tuple["ResolvedTypeV2", ...] = ()
    const_arguments: tuple[int, ...] = ()

    @property
    def collection_capacity(self) -> int | None:
        return self.const_arguments[0] if self.kind in {"list","set","map"} else None

    @property
    def array_length(self) -> int | None:
        return self.const_arguments[0] if self.kind == "array" else None


@dataclass(frozen=True, slots=True)
class _TokenV2:
    kind: str
    text: str
    offset: int


def parse_type_ref_v2(text: str, user_generic_arities: Mapping[str, int] | None = None) -> TypeRefV2:
    if not isinstance(text,str) or not text.strip():
        _fail("TEVS_V2_TYPE_SYNTAX", "type expression must be non-empty")
    tokens: list[_TokenV2] = []
    pos=0
    while pos < len(text):
        if text[pos:].strip() == "":
            pos = len(text)
            break
        match=_TOKEN.match(text,pos)
        if match is None:
            _fail("TEVS_V2_TYPE_SYNTAX", f"invalid type token at offset {pos}")
        kind=next(name for name,value in match.groupdict().items() if value is not None)
        token_text=match.group(kind)
        tokens.append(_TokenV2(kind,token_text,match.start(kind)))
        pos=match.end()
    tokens.append(_TokenV2("eof","",len(text)))
    parser=_TypeParserV2(tokens, user_generic_arities or {})
    result=parser.parse_type(1)
    if parser.current.kind!="eof":
        _fail("TEVS_V2_TYPE_SYNTAX", f"unexpected token {parser.current.text!r} at offset {parser.current.offset}")
    return result


class _TypeParserV2:
    def __init__(self,tokens:list[_TokenV2],user_generic_arities: Mapping[str, int] | None = None):
        self.tokens=tokens; self.index=0; self.user_generic_arities=dict(user_generic_arities or {})

    @property
    def current(self)->_TokenV2: return self.tokens[self.index]

    def take(self,kind:str)->_TokenV2:
        token=self.current
        if token.kind!=kind:
            _fail("TEVS_V2_TYPE_SYNTAX",f"expected {kind}, got {token.text!r} at offset {token.offset}")
        self.index+=1; return token

    def accept(self,kind:str)->bool:
        if self.current.kind==kind:
            self.index+=1; return True
        return False

    def parse_type(self,depth:int)->TypeRefV2:
        if depth>MAX_TYPE_NESTING_V2:
            _fail("TEVS_V2_TYPE_NESTING",f"type nesting exceeds {MAX_TYPE_NESTING_V2}")
        name=self.take("name").text
        if self.accept("scope"):
            associated=self.take("name").text
            if "." in name or "." in associated:
                _fail("TEVS_V2_ASSOCIATED_TYPE_SYNTAX","associated type projection requires local root and member names")
            return TypeRefV2("associated",f"{name}::{associated}")
        if not self.accept("lt"):
            if name in {"Option","Result","List","Array","Set","Map"}:
                _fail("TEVS_V2_TYPE_ARGUMENTS",f"{name} requires generic arguments")
            return TypeRefV2("named",name)
        if name=="Option":
            argument=self.parse_type(depth+1); self.take("gt")
            return TypeRefV2("option",name,(argument,))
        if name=="Result":
            ok=self.parse_type(depth+1); self.take("comma"); err=self.parse_type(depth+1); self.take("gt")
            return TypeRefV2("result",name,(ok,err))
        if name in {"List","Array","Set"}:
            item=self.parse_type(depth+1); self.take("comma"); bound=self._capacity(); self.take("gt")
            return TypeRefV2(name.lower(),name,(item,),(bound,))
        if name=="Map":
            key=self.parse_type(depth+1); self.take("comma"); value=self.parse_type(depth+1); self.take("comma"); cap=self._capacity(); self.take("gt")
            return TypeRefV2("map",name,(key,value),(cap,))
        arity=self.user_generic_arities.get(name)
        if arity is not None:
            if not 1<=arity<=16:
                _fail("TEVS_V2_USER_GENERIC_ARITY",f"declared generic arity for {name!r} must be 1..16")
            arguments=[]
            for index in range(arity):
                if index:
                    self.take("comma")
                arguments.append(self.parse_type(depth+1))
            self.take("gt")
            return TypeRefV2("user_generic",name,tuple(arguments))
        _fail("TEVS_V2_USER_GENERIC_NOT_DECLARED",f"generic application {name}<...> requires a declared user generic")

    def _capacity(self)->int:
        token=self.take("int")
        value=int(token.text)
        if not 1<=value<=MAX_COLLECTION_CAPACITY_V2:
            _fail("TEVS_V2_COLLECTION_CAPACITY",f"collection capacity must be 1..{MAX_COLLECTION_CAPACITY_V2}, got {value}")
        return value


def resolve_type_ref_v2(
    type_ref: TypeRefV2,
    nominal_resolver: Callable[[str], str] | None = None,
    user_generic_resolver: Callable[[str, tuple[ResolvedTypeV2, ...]], str] | None = None,
    associated_resolver: Callable[[str, str], ResolvedTypeV2] | None = None,
) -> ResolvedTypeV2:
    if type_ref.kind=="associated":
        root, member = associated_type_parts_v2(type_ref)
        if associated_resolver is None:
            _fail("TEVS_V2_ASSOCIATED_TYPE_UNRESOLVED",f"associated type projection {root}::{member} requires an exact witness resolver")
        resolved = associated_resolver(root, member)
        if not isinstance(resolved, ResolvedTypeV2):
            _fail("TEVS_V2_ASSOCIATED_TYPE_UNRESOLVED",f"associated type projection {root}::{member} did not resolve")
        return resolved
    if type_ref.kind=="named":
        if type_ref.name in _PRIMITIVES:
            return ResolvedTypeV2("primitive" if type_ref.name!="Unit" else "unit",type_ref.name)
        if nominal_resolver is None:
            _fail("TEVS_V2_TYPE_UNKNOWN",f"nominal type {type_ref.name!r} requires name resolution")
        resolved=nominal_resolver(type_ref.name)
        if not isinstance(resolved,str) or not resolved:
            _fail("TEVS_V2_TYPE_UNKNOWN",f"nominal type {type_ref.name!r} did not resolve")
        return ResolvedTypeV2("nominal",resolved)
    args=tuple(resolve_type_ref_v2(arg,nominal_resolver,user_generic_resolver,associated_resolver) for arg in type_ref.arguments)
    if type_ref.kind=="user_generic":
        if user_generic_resolver is None:
            _fail("TEVS_V2_USER_GENERIC_RESOLVER",f"generic application {type_ref.name}<...> requires a generic resolver")
        resolved=user_generic_resolver(type_ref.name,args)
        if not isinstance(resolved,str) or not resolved:
            _fail("TEVS_V2_USER_GENERIC_RESOLVER",f"generic application {type_ref.name}<...> did not resolve")
        return ResolvedTypeV2("user_generic",resolved,args)
    if type_ref.kind=="option":
        return ResolvedTypeV2("option",f"Option<{args[0].type_id}>",args)
    if type_ref.kind=="result":
        return ResolvedTypeV2("result",f"Result<{args[0].type_id},{args[1].type_id}>",args)
    bound=type_ref.array_length if type_ref.kind=="array" else type_ref.collection_capacity
    assert bound is not None
    if any(arg.type_id=="Unit" for arg in args):
        _fail("TEVS_V2_TYPE_NOT_STORABLE",f"Unit cannot be stored inside {type_ref.name}")
    if type_ref.kind=="list":
        type_id=f"List<{args[0].type_id},{bound}>"
    elif type_ref.kind=="array":
        type_id=f"Array<{args[0].type_id},{bound}>"
    elif type_ref.kind=="set":
        type_id=f"Set<{args[0].type_id},{bound}>"
    elif type_ref.kind=="map":
        type_id=f"Map<{args[0].type_id},{args[1].type_id},{bound}>"
    else:
        _fail("TEVS_V2_TYPE_REFERENCE_KIND",f"unsupported type reference kind {type_ref.kind!r}")
    return ResolvedTypeV2(type_ref.kind,type_id,args,(bound,))



def validate_static_type_ref_v2(
    type_ref: TypeRefV2,
    *,
    type_parameters: Sequence[str] = (),
    nominal_resolver: Callable[[str], str] | None = None,
    user_generic_arities: Mapping[str, int] | None = None,
) -> ResolvedTypeV2:
    if not isinstance(type_ref, TypeRefV2):
        _fail("TEVS_V2_TYPE_REFERENCE_KIND", "static validation requires TypeRefV2")
    parameters = frozenset(type_parameters)
    arities = dict(user_generic_arities or {})

    def nominal(name: str) -> str:
        if name in parameters:
            return "Int"
        if nominal_resolver is None:
            _fail("TEVS_V2_TYPE_UNKNOWN", f"nominal type {name!r} requires name resolution")
        resolved = nominal_resolver(name)
        if not isinstance(resolved, str) or not resolved:
            _fail("TEVS_V2_TYPE_UNKNOWN", f"nominal type {name!r} did not resolve")
        return resolved

    def user_generic(name: str, arguments: tuple[ResolvedTypeV2, ...]) -> str:
        expected = arities.get(name)
        if expected is None:
            _fail(
                "TEVS_V2_USER_GENERIC_NOT_DECLARED",
                f"generic application {name}<...> requires a declared user generic",
            )
        if len(arguments) != expected:
            _fail(
                "TEVS_V2_USER_GENERIC_ARITY",
                f"generic application {name}<...> expects {expected} arguments, got {len(arguments)}",
            )
        encoded = ",".join(argument.type_id for argument in arguments)
        return f"__tev_static_generic__.{name}<{encoded}>"

    def associated(root: str, member: str) -> ResolvedTypeV2:
        if root not in parameters:
            _fail(
                "TEVS_V2_ASSOCIATED_TYPE_UNRESOLVED",
                f"associated type projection {root}::{member} requires a type parameter",
            )
        return ResolvedTypeV2("primitive", "Int")

    return resolve_type_ref_v2(type_ref, nominal, user_generic, associated)


def associated_type_parts_v2(type_ref: TypeRefV2) -> tuple[str, str]:
    if type_ref.kind != "associated" or "::" not in type_ref.name:
        _fail("TEVS_V2_ASSOCIATED_TYPE_SYNTAX","type reference is not an associated type projection")
    root, member = type_ref.name.split("::",1)
    if not root or not member or "::" in member:
        _fail("TEVS_V2_ASSOCIATED_TYPE_SYNTAX",f"invalid associated type projection {type_ref.name!r}")
    return root, member


def collection_iteration_bound(type_ref: ResolvedTypeV2) -> int:
    bound=type_ref.array_length if type_ref.kind=="array" else type_ref.collection_capacity
    if bound is None:
        _fail("TEVS_V2_NOT_ITERABLE",f"type {type_ref.type_id!r} is not a bounded collection")
    return bound


def _fail(code:str,message:str)->None:
    raise TevScriptError(code,message)
