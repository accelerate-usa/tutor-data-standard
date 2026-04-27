from __future__ import annotations

import pandas as pd

from schema_registry import (
    coerce_dataframe_types,
    dictionary_dataframe,
    get_canonical_columns,
    get_latest_outcome_field,
    get_outcome_measure_fields,
    normalize_dataframe_columns,
    normalize_session_topic,
    parse_datetime,
    parse_flag,
    parse_grade,
    parse_numeric,
)
from utils.generate_schema_artifacts import build_markdown_document


def test_normalize_dataframe_columns_merges_aliases_and_tracks_unknowns() -> None:
    df = pd.DataFrame(
        [["001", pd.NA, "2026-01-10 09:00:00", "x"]],
        columns=["student_id", "session_date", "session_datetime", "extra_col"],
    )

    normalized, report = normalize_dataframe_columns(df, "session")

    assert normalized.loc[0, "student_id"] == "001"
    assert normalized.loc[0, "session_date"] == "2026-01-10 09:00:00"
    assert "extra_col" in report["unknown_columns"]
    assert report["combined_columns"]["session_date"] == ["session_date", "session_datetime"]


def test_parse_flag_handles_unknown_and_invalid_values() -> None:
    assert parse_flag("TRUE") == (True, True)
    assert parse_flag("false") == (False, True)
    parsed_unknown, is_valid_unknown = parse_flag("declined to provide")
    parsed_invalid, is_valid_invalid = parse_flag("maybe")

    assert pd.isna(parsed_unknown) and is_valid_unknown is True
    assert pd.isna(parsed_invalid) and is_valid_invalid is False


def test_parse_grade_handles_aliases_and_numeric_values() -> None:
    assert parse_grade("K") == (0, True)
    assert parse_grade("Pre-K") == (-1, True)
    assert parse_grade("3.0") == (3, True)


def test_parse_numeric_and_datetime() -> None:
    assert parse_numeric("7.5") == (7.5, True)
    assert parse_numeric("bad")[1] is False
    parsed_date, is_valid = parse_datetime("2026-01-10 09:00:00")
    assert is_valid is True
    assert str(parsed_date).startswith("2026-01-10")


def test_normalize_session_topic_maps_common_aliases() -> None:
    assert normalize_session_topic("Mathematics") == ("math", True)
    assert normalize_session_topic("reading") == ("ela", True)
    assert normalize_session_topic("science")[1] is False


def test_coerce_dataframe_types_preserves_identifiers_and_numeric_outcomes() -> None:
    df = pd.DataFrame(
        {
            "student_id": ["00123"],
            "district_id": ["0007"],
            "school_id": ["0042"],
            "current_grade_level": ["3"],
            "ell": ["TRUE"],
            "ela_outcome_measure_1": ["700"],
        }
    )

    typed = coerce_dataframe_types(df, "student")

    assert str(typed.loc[0, "student_id"]) == "00123"
    assert typed.loc[0, "current_grade_level"] == 3
    assert typed.loc[0, "ell"] == True
    assert typed.loc[0, "ela_outcome_measure_1"] == 700


def test_dictionary_dataframe_and_canonical_columns_include_new_outcomes() -> None:
    dictionary_df = dictionary_dataframe("student")
    columns = get_canonical_columns("student")

    assert "ela_outcome_measure_1" in columns
    assert "math_outcome_measure_3" in columns
    assert "ela_outcome_measure_1" in dictionary_df["column_name"].tolist()


def test_outcome_measure_helpers_return_expected_fields() -> None:
    assert get_outcome_measure_fields("ela") == (
        "ela_outcome_measure_1",
        "ela_outcome_measure_2",
        "ela_outcome_measure_3",
    )
    assert get_latest_outcome_field("math") == "math_outcome_measure_3"


def test_generated_dictionary_mentions_optional_mapping_profiles() -> None:
    markdown = build_markdown_document()

    assert "Most teams can upload `sessions.csv` and `students.csv` directly in the dashboard." in markdown
    assert "local mapping profile JSON" in markdown
