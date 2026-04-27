from __future__ import annotations

import json

import pandas as pd
import pytest

from toolkit.app_support import (
    apply_custom_column_map,
    apply_filter_values,
    build_mapping_profile,
    build_module_readiness,
    build_normalization_detail_rows,
    build_normalization_summary_rows,
    build_unknown_denominator_notes,
    combine_export_sections,
    export_dataframe_bytes,
    export_sections_json,
    get_filter_specs,
    get_profile_column_map,
    get_tab_readiness_notes,
    parse_mapping_profile_text,
    summarize_active_filters,
)


def make_filter_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "school_name": ["A", "A", "B", "B"],
            "current_grade_level": [3, 4, 3, 5],
            "gender": ["Female", "Male", "Female", "Unknown"],
            "ethnicity": ["X", "Y", "X", "Z"],
            "ell": pd.array([True, False, pd.NA, True], dtype="boolean"),
            "iep": pd.array([False, True, pd.NA, False], dtype="boolean"),
            "economic_disadvantage": pd.array([True, True, False, pd.NA], dtype="boolean"),
        }
    )


def make_readiness_frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    prepared_df = pd.DataFrame(
        {
            "student_id": ["1", "2"],
            "school_name": ["A", "B"],
            "total_hours": [10.0, 20.0],
            "ethnicity": ["X", "Y"],
            "ell": pd.array([True, False], dtype="boolean"),
            "iep": pd.array([False, True], dtype="boolean"),
            "performance_level_most_recent": ["Basic", "Proficient"],
            "ela_latest_outcome": [700, 710],
            "math_latest_outcome": [690, 720],
            "ela_raw_gain": [5, 6],
            "ela_value_added": [2, 3],
            "math_raw_gain": [4, 7],
            "math_value_added": [1, 2],
        }
    )
    session_df = pd.DataFrame(
        {
            "student_id": ["1", "2"],
            "session_topic": ["ela", "math"],
            "session_duration": [60, 45],
            "session_date": ["2026-01-15 09:00:00", "2026-01-15 10:00:00"],
        }
    )
    student_df = pd.DataFrame({"student_id": ["1", "2"]})
    return prepared_df, session_df, student_df


def test_apply_custom_column_map_renames_exact_and_normalized_matches() -> None:
    df = pd.DataFrame({" Student Number ": ["001"], "Hours": [5]})
    renamed, applied = apply_custom_column_map(df, {"student number": "student_id"})

    assert list(renamed.columns) == ["student_id", "Hours"]
    assert applied == {" Student Number ": "student_id"}


def test_build_mapping_profile_extracts_alias_and_custom_maps() -> None:
    session_report = {
        "alias_sources": {"session_date": ["session_datetime"]},
        "applied_custom_column_map": {"Learner ID": "student_id"},
    }
    student_report = {
        "alias_sources": {"student_id": ["Student Number"]},
        "applied_custom_column_map": {},
    }

    profile = build_mapping_profile(session_report, student_report)

    assert profile["dataset_profiles"]["session"]["custom_column_map"]["session_datetime"] == "session_date"
    assert profile["dataset_profiles"]["session"]["custom_column_map"]["Learner ID"] == "student_id"
    assert profile["dataset_profiles"]["student"]["custom_column_map"]["Student Number"] == "student_id"


def test_parse_mapping_profile_text_rejects_invalid_payload() -> None:
    with pytest.raises(ValueError):
        parse_mapping_profile_text("[]")

    with pytest.raises(ValueError):
        parse_mapping_profile_text(json.dumps({"version": 1}))


def test_get_profile_column_map_returns_dataset_map() -> None:
    payload = {
        "dataset_profiles": {
            "student": {"custom_column_map": {"Student Number": "student_id"}},
            "session": {"custom_column_map": {"Session DateTime": "session_date"}},
        }
    }

    assert get_profile_column_map(payload, "student") == {"Student Number": "student_id"}
    assert get_profile_column_map(payload, "session") == {"Session DateTime": "session_date"}


def test_get_filter_specs_includes_base_and_module_specific_fields() -> None:
    specs = get_filter_specs(make_filter_df(), "equity")
    fields = [spec["field"] for spec in specs]

    assert fields[:2] == ["school_name", "current_grade_level"]
    assert "ethnicity" in fields
    assert "ell" in fields
    assert "iep" in fields
    assert "economic_disadvantage" in fields


def test_apply_filter_values_handles_school_grade_and_unknown_tri_state() -> None:
    df = make_filter_df()
    filtered = apply_filter_values(
        df,
        {
            "school_name": "B",
            "current_grade_level": [3, 5],
            "ell": "Unknown",
        },
    )

    assert len(filtered) == 1
    assert filtered.iloc[0]["school_name"] == "B"
    assert pd.isna(filtered.iloc[0]["ell"])


def test_summarize_active_filters_compacts_values() -> None:
    df = make_filter_df()
    specs = get_filter_specs(df, "dosage")
    summary = summarize_active_filters(
        {
            "school_name": "A",
            "current_grade_level": [3, 4],
            "gender": ["Female"],
            "ethnicity": ["X", "Y", "Z"],
        },
        specs,
    )

    assert "School: A" in summary
    assert "Grade Levels" in summary
    assert "Gender: Female" in summary


def test_build_unknown_denominator_notes_reports_unknowns() -> None:
    notes = build_unknown_denominator_notes(
        make_filter_df(),
        {"ell": "ELL", "iep": "IEP"},
    )

    assert any(note.startswith("ELL:") for note in notes)
    assert any(note.startswith("IEP:") for note in notes)


def test_build_normalization_summary_rows_counts_aliases_and_unknowns() -> None:
    raw_df = pd.DataFrame({"Student Number": ["1"], "unused_col": ["x"]})
    normalized_df = pd.DataFrame({"student_id": ["1"]})
    report = {
        "alias_sources": {"student_id": ["Student Number"]},
        "combined_columns": {},
        "unknown_columns": ["unused_col"],
        "applied_custom_column_map": {"Student Number": "student_id"},
    }
    errors = {"critical": [], "warnings": ["w1", "w2"], "info": ["i1"]}

    summary = build_normalization_summary_rows("student", raw_df, normalized_df, report, errors)

    assert summary.loc[0, "renamed_columns"] == 1
    assert summary.loc[0, "unknown_columns"] == 1
    assert summary.loc[0, "profile_mappings_applied"] == 1
    assert summary.loc[0, "warnings"] == 2


def test_build_normalization_detail_rows_includes_unknown_columns() -> None:
    report = {
        "alias_sources": {"student_id": ["Student Number"]},
        "combined_columns": {},
        "unknown_columns": ["unused_col"],
    }

    details = build_normalization_detail_rows("student", report)

    assert "Mapped from alias" in details["status"].tolist()
    assert "Not used by current schema" in details["status"].tolist()


def test_build_module_readiness_marks_partial_and_ready_sections() -> None:
    prepared_df, session_df, student_df = make_readiness_frames()
    readiness = build_module_readiness(prepared_df, session_df, student_df)

    dosage_summary = readiness[(readiness["tab"] == "Dosage & Access") & (readiness["section"] == "Tab summary")].iloc[0]
    equity_gap_row = readiness[(readiness["tab"] == "Equity Analysis") & (readiness["section"] == "Subgroup dosage gaps")].iloc[0]

    assert dosage_summary["status"] == "Ready"
    assert equity_gap_row["status"] == "Partial"


def test_get_tab_readiness_notes_returns_status_and_missing_details() -> None:
    prepared_df, session_df, student_df = make_readiness_frames()
    readiness = build_module_readiness(prepared_df, session_df, student_df)
    status, details = get_tab_readiness_notes(readiness, "Equity Analysis")

    assert status in {"Ready", "Partial", "Unavailable"}
    assert isinstance(details, list)


def test_export_dataframe_bytes_supports_csv_tsv_and_json() -> None:
    df = pd.DataFrame({"a": [1], "b": [2]})

    csv_bytes, csv_mime, csv_ext = export_dataframe_bytes(df, "csv")
    tsv_bytes, tsv_mime, tsv_ext = export_dataframe_bytes(df, "tsv")
    json_bytes, json_mime, json_ext = export_dataframe_bytes(df, "json")

    assert csv_mime == "text/csv" and csv_ext == "csv" and b"a,b" in csv_bytes
    assert tsv_mime == "text/tab-separated-values" and tsv_ext == "tsv" and b"a\tb" in tsv_bytes
    assert json_mime == "application/json" and json_ext == "json" and b'"a"' in json_bytes


def test_combine_export_sections_adds_export_section_column() -> None:
    combined = combine_export_sections(
        {
            "metrics": pd.DataFrame({"value": [1]}),
            "empty": pd.DataFrame(),
            "summary": pd.DataFrame({"value": [2]}),
        }
    )

    assert combined["export_section"].tolist() == ["metrics", "summary"]
    assert combined["value"].tolist() == [1, 2]


def test_combine_export_sections_preserves_existing_section_columns() -> None:
    combined = combine_export_sections(
        {
            "readiness_summary": pd.DataFrame(
                {
                    "section": ["Tab summary"],
                    "status": ["Ready"],
                }
            )
        }
    )

    assert combined["export_section"].tolist() == ["readiness_summary"]
    assert combined["section"].tolist() == ["Tab summary"]


def test_combine_export_sections_renames_existing_export_section_column() -> None:
    combined = combine_export_sections(
        {
            "metrics": pd.DataFrame(
                {
                    "export_section": ["original"],
                    "value": [1],
                }
            )
        }
    )

    assert combined["export_section"].tolist() == ["metrics"]
    assert combined["source_export_section"].tolist() == ["original"]


def test_export_sections_json_serializes_named_frames() -> None:
    payload = export_sections_json({"metrics": pd.DataFrame({"value": [1]})})
    parsed = json.loads(payload.decode("utf-8"))

    assert parsed == {"metrics": [{"value": 1}]}
