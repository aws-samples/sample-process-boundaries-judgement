# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""JSON and markdown persistence for cases, records, and memos."""

import json
import os
from pathlib import Path
from .schema import ReasoningRecord


def load_case(path: Path) -> dict:
    return json.loads(Path(path).read_text())


def save_record(record: ReasoningRecord, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(record.model_dump_json(indent=2))
    os.replace(tmp, path)


def load_record(path: Path) -> ReasoningRecord:
    data = json.loads(Path(path).read_text())
    return ReasoningRecord.model_validate(data)


def save_memo(markdown: str, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(markdown)
    os.replace(tmp, path)
