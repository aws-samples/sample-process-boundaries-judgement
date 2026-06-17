# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Typed reasoning record schema."""

from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field


class _NodeBase(BaseModel):
    id: str = Field(min_length=1)
    kind: str


class Fact(_NodeBase):
    kind: Literal["fact"] = "fact"
    claim: str = Field(min_length=1)
    source: str = Field(min_length=1)


class StandardReference(_NodeBase):
    kind: Literal["standard"] = "standard"
    rule_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    text: str = Field(min_length=1)


class Interpretation(_NodeBase):
    kind: Literal["interpretation"] = "interpretation"
    statement: str = Field(min_length=1)
    applies_to: list[str] = Field(default_factory=list)
    anchors: list[str] = Field(default_factory=list)


class Threshold(_NodeBase):
    kind: Literal["threshold"] = "threshold"
    name: str = Field(min_length=1)
    value: float
    derivation: str = Field(min_length=1)
    inputs: list[str] = Field(default_factory=list)
    sensitivity: str | None = None


class AlternativeConsidered(_NodeBase):
    kind: Literal["alternative"] = "alternative"
    alternative: str = Field(min_length=1)
    rejection_reason: str = Field(min_length=1)


class Conclusion(_NodeBase):
    kind: Literal["conclusion"] = "conclusion"
    statement: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    comfort_zone: Literal["in", "out"]
    comfort_zone_reason: str | None = None
    supported_by: list[str] = Field(min_length=1)


class OpenQuestion(_NodeBase):
    kind: Literal["open_question"] = "open_question"
    question: str = Field(min_length=1)
    escalate_to_reviewer: bool = False
    raised_by: Literal["agent", "adversary"] = "agent"


Node = Annotated[
    Union[
        Fact,
        StandardReference,
        Interpretation,
        Threshold,
        AlternativeConsidered,
        Conclusion,
        OpenQuestion,
    ],
    Field(discriminator="kind"),
]


_EDGE_FIELDS_BY_KIND = {
    "interpretation": ("applies_to", "anchors"),
    "threshold": ("inputs",),
    "conclusion": ("supported_by",),
}


class ReasoningRecord(BaseModel):
    case_id: str
    nodes: dict[str, Node]
    adversarial_rounds: list["AdversarialRound"] = Field(default_factory=list)

    def validate_dag(self) -> None:
        """Verify all edges resolve and the graph is acyclic."""
        for node_id, node in self.nodes.items():
            if node.id != node_id:
                raise ValueError(f"node id mismatch: key={node_id} node.id={node.id}")
            edge_fields = _EDGE_FIELDS_BY_KIND.get(node.kind, ())
            for field_name in edge_fields:
                refs = getattr(node, field_name, [])
                for ref in refs:
                    if ref not in self.nodes:
                        raise ValueError(
                            f"node {node_id}.{field_name} references unknown node: {ref}"
                        )
        self._check_acyclic()

    def _check_acyclic(self) -> None:
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {nid: WHITE for nid in self.nodes}

        def dfs(nid: str) -> None:
            color[nid] = GRAY
            node = self.nodes[nid]
            for field_name in _EDGE_FIELDS_BY_KIND.get(node.kind, ()):
                for ref in getattr(node, field_name, []):
                    if color[ref] == GRAY:
                        raise ValueError(f"cycle detected at node {ref}")
                    if color[ref] == WHITE:
                        dfs(ref)
            color[nid] = BLACK

        for nid in self.nodes:
            if color[nid] == WHITE:
                dfs(nid)


class AdversarialChallenge(BaseModel):
    dimension: Literal["framing", "completeness", "conclusions", "citations"]
    challenge: str
    target_node_id: str | None = None


class AdversarialRound(BaseModel):
    round_number: int
    challenges: list[AdversarialChallenge]
    agent_response_summary: str


ReasoningRecord.model_rebuild()
