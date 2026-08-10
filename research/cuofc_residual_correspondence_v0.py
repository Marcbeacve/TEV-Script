from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from research.cuofc_correspondence_v0 import Construct, Result, R
from tev_script.canonical import canonical_hash, canonical_json
from tev_script.semantic_kernel_v0 import SemanticFieldV0
from tev_script.semantic_residual_v0 import (
    DEFAULT_RESIDUAL_CONTEXT_HASH,
    DEFAULT_RESIDUAL_LAW_HASH,
    ResidualObstructionV0,
    ResidualProgressV0,
    residual_from_obstructions,
    residual_progress,
)

TARGET_KIND = "TEV.SemanticResidualFieldV0"


def _token_hash(token: Any) -> str:
    return canonical_hash({"schema": "CUOFC_FINITE_RESIDUAL_TOKEN_V0", "token": token})


def translate_residual(construct: Construct) -> tuple[Result, SemanticFieldV0]:
    if construct.kind != "residual":
        raise ValueError("CUOFC residual construct required")
    payload = dict(construct.payload)
    domain = str(payload.get("domain", "semantic"))
    judgment_id = str(payload["judgment_id"])
    judgment = payload["judgment"]
    context_hash = str(payload.get("context_hash", DEFAULT_RESIDUAL_CONTEXT_HASH))
    law_hash = str(payload.get("law_hash", DEFAULT_RESIDUAL_LAW_HASH))
    outstanding = tuple(payload.get("outstanding", ()))
    canonical_json(list(outstanding))
    rows = []
    for token in outstanding:
        token_hash = _token_hash(token)
        rows.append(
            ResidualObstructionV0(
                kind="correspondence.outstanding",
                subject=canonical_json(token),
                expected="discharged",
                observed="pending",
                detail={"token": token, "token_hash": token_hash},
                dependency_refs=("cuofc-obligation:" + token_hash,),
            )
        )
    field = residual_from_obstructions(
        domain=domain,
        judgment_id=judgment_id,
        judgment=judgment,
        source={
            "kind": "cuofc_finite_residual",
            "construct_hash": construct.source_hash,
            "outstanding": list(outstanding),
        },
        obstructions=rows,
        context_hash=context_hash,
        law_hash=law_hash,
    )
    result = R(
        construct,
        "DERIVED",
        TARGET_KIND,
        field.field_hash,
        (
            "finite_obstruction_encoding_explicit",
            "judgment_context_law_boundary_preserved",
            "cuofc_has_no_tev_runtime_authority",
        ),
    )
    return result, field


@dataclass(frozen=True, slots=True)
class ResidualProgressCorrespondenceV0:
    before: Result
    after: Result
    progress: ResidualProgressV0


def translate_residual_progress(
    before: Construct,
    after: Construct,
) -> ResidualProgressCorrespondenceV0:
    before_result, before_field = translate_residual(before)
    after_result, after_field = translate_residual(after)
    return ResidualProgressCorrespondenceV0(
        before=before_result,
        after=after_result,
        progress=residual_progress(before_field, after_field),
    )


__all__ = [
    "TARGET_KIND",
    "ResidualProgressCorrespondenceV0",
    "translate_residual",
    "translate_residual_progress",
]
