"""Validate the privacy-preserving output_validation API payload."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


def output_validation_contract_errors(record: dict[str, Any]) -> list[str]:
    path = Path(__file__).parent / "schema" / "output_validation.schema.json"
    schema = json.loads(path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    return [f"{'.'.join(map(str, error.absolute_path)) or 'root'}: {error.message}" for error in sorted(validator.iter_errors(record), key=str)]
