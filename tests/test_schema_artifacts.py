from __future__ import annotations

from io import StringIO
from pathlib import Path

import pandas as pd

from schema_registry import dictionary_dataframe, get_canonical_columns
from utils.generate_schema_artifacts import build_markdown_document


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = REPO_ROOT / "schema"


def _normalize_newlines(value: str) -> str:
    return value.replace("\r\n", "\n")


def _csv_text(df: pd.DataFrame) -> str:
    buffer = StringIO()
    df.to_csv(buffer, index=False)
    return buffer.getvalue()


def test_generated_schema_artifacts_are_current() -> None:
    expected_files = {
        "data_dictionary.md": build_markdown_document(),
    }

    for dataset in ("student", "session"):
        expected_files[f"{dataset}_dictionary.csv"] = _csv_text(dictionary_dataframe(dataset))
        expected_files[f"{dataset}_template_header.csv"] = _csv_text(
            pd.DataFrame(columns=get_canonical_columns(dataset))
        )

    for filename, expected in expected_files.items():
        actual = (SCHEMA_DIR / filename).read_text(encoding="utf-8")
        assert _normalize_newlines(actual) == _normalize_newlines(expected), (
            f"{filename} is out of date. Run `python utils/generate_schema_artifacts.py`."
        )
