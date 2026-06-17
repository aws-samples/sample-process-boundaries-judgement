# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import json
from pathlib import Path
from governed_reasoning.schema import ReasoningRecord, Fact, Conclusion, StandardReference
from governed_reasoning.persistence import (
    load_case,
    save_record,
    load_record,
    save_memo,
)


def test_load_case_returns_dict(tmp_path: Path):
    case_path = tmp_path / "case.json"
    case_path.write_text(json.dumps({"case_id": "c1", "facts": ["fact a"], "context": "..."}))
    case = load_case(case_path)
    assert case["case_id"] == "c1"
    assert "facts" in case


def test_save_and_load_record_round_trips(tmp_path: Path):
    rec = ReasoningRecord(
        case_id="c1",
        nodes={
            "f1": Fact(id="f1", claim="x", source="src"),
            "s1": StandardReference(id="s1", rule_id="r", version="v", text="t"),
            "c1": Conclusion(
                id="c1",
                statement="ok",
                confidence=0.9,
                comfort_zone="in",
                supported_by=["f1", "s1"],
            ),
        },
    )
    out = tmp_path / "record.json"
    save_record(rec, out)
    loaded = load_record(out)
    assert loaded.case_id == "c1"
    assert "f1" in loaded.nodes
    assert loaded.nodes["c1"].confidence == 0.9


def test_save_memo_writes_markdown(tmp_path: Path):
    out = tmp_path / "memo.md"
    save_memo("# Memo\n\nBody.", out)
    assert out.read_text().startswith("# Memo")


def test_save_record_is_atomic(tmp_path: Path):
    rec = ReasoningRecord(case_id="c1", nodes={})
    out = tmp_path / "record.json"
    save_record(rec, out)
    # No leftover .tmp file
    assert not (tmp_path / "record.json.tmp").exists()
