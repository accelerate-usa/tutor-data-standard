from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pandas as pd
import pytest

from utils.generate_datasets import CONFIG as GENERATOR_CONFIG, generate_student_data, set_random_seed
from toolkit.app_support import build_module_readiness, get_profile_column_map
from toolkit.descriptives import (
    calculate_cost_metrics,
    calculate_dosage_metrics,
    calculate_equity_metrics,
    calculate_outcome_metrics,
    get_prepared_data_cached,
    get_tutored_students,
    load_dataset,
    prepare_data,
    weighted_metric_average,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def write_csv(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_load_dataset_preserves_identifier_strings_and_aliases(tmp_path: Path) -> None:
    student_path = write_csv(
        tmp_path / "student.csv",
        "\n".join(
            [
                "Student Number,district_id,district_name,school_id,school_name,current_grade_level,gender,ethnicity,ell,iep,economic_disadvantage,ela_state_score_two_years_ago,ela_state_score_one_year_ago,ela_state_score_current_year,math_state_score_two_years_ago,math_state_score_one_year_ago,math_state_score_current_year,performance_level_prior_year,performance_level_current_year",
                "00123,0007,District,0042,School,3,Female,X,TRUE,FALSE,TRUE,700,710,720,690,700,710,Basic,Proficient",
            ]
        ),
    )

    raw_df, typed_df, errors, report = load_dataset(student_path, "student", {"Student Number": "student_id"})

    assert raw_df.loc[0, "student_id"] == "00123"
    assert str(typed_df.loc[0, "student_id"]) == "00123"
    assert typed_df.loc[0, "ela_outcome_measure_3"] == 720
    assert not errors["critical"]
    assert report["applied_custom_column_map"] == {"Student Number": "student_id"}


def test_load_dataset_applies_mapping_profile_to_custom_names(tmp_path: Path) -> None:
    session_path = write_csv(
        tmp_path / "session.csv",
        "\n".join(
            [
                "Learner ID,Topic,Session DateTime,Minutes,Tutor",
                "00123,Math,2026-01-10 09:00:00,45,T1",
            ]
        ),
    )

    profile = {
        "dataset_profiles": {
            "session": {
                "custom_column_map": {
                    "Learner ID": "student_id",
                    "Topic": "session_topic",
                    "Session DateTime": "session_date",
                    "Minutes": "session_duration",
                    "Tutor": "tutor_id",
                }
            }
        }
    }

    _, typed_df, errors, report = load_dataset(
        session_path,
        "session",
        custom_column_map=get_profile_column_map(profile, "session"),
    )

    assert list(typed_df.columns)[:5] == ["student_id", "session_topic", "session_date", "session_duration", "tutor_id"]
    assert typed_df.loc[0, "session_topic"] == "math"
    assert not errors["critical"]
    assert report["applied_custom_column_map"]["Learner ID"] == "student_id"


def test_prepare_data_keeps_missing_flags_unknown() -> None:
    session_df = pd.DataFrame(
        {
            "student_id": ["001"],
            "session_topic": ["ela"],
            "session_date": ["2026-01-15 09:00:00"],
            "session_duration": [60],
            "tutor_id": ["T1"],
        }
    )
    student_df = pd.DataFrame(
        {
            "student_id": ["001"],
            "district_id": ["01"],
            "district_name": ["District"],
            "school_id": ["02"],
            "school_name": ["School"],
            "current_grade_level": [3],
            "gender": ["Female"],
            "ethnicity": ["X"],
            "ell": pd.array([pd.NA], dtype="boolean"),
            "iep": pd.array([False], dtype="boolean"),
            "economic_disadvantage": pd.array([True], dtype="boolean"),
        }
    )

    prepared = prepare_data(session_df, student_df)

    assert pd.isna(prepared.loc[0, "ell"])
    assert prepared.loc[0, "total_hours"] == 1.0
    assert prepared.loc[0, "received_tutoring"] == True


def test_prepare_data_calculates_outcome_summary_columns() -> None:
    session_df = pd.DataFrame(
        {
            "student_id": ["001"],
            "session_topic": ["math"],
            "session_date": ["2026-01-15 09:00:00"],
            "session_duration": [30],
            "tutor_id": ["T1"],
        }
    )
    student_df = pd.DataFrame(
        {
            "student_id": ["001"],
            "district_id": ["01"],
            "district_name": ["District"],
            "school_id": ["02"],
            "school_name": ["School"],
            "current_grade_level": [4],
            "gender": ["Male"],
            "ethnicity": ["Y"],
            "ela_outcome_measure_1": [700],
            "ela_outcome_measure_2": [710],
            "ela_outcome_measure_3": [725],
            "math_outcome_measure_1": [690],
            "math_outcome_measure_2": [700],
            "math_outcome_measure_3": [715],
        }
    )

    prepared = prepare_data(session_df, student_df)

    assert prepared.loc[0, "ela_latest_outcome"] == 725
    assert prepared.loc[0, "ela_raw_gain"] == 25
    assert prepared.loc[0, "ela_value_added"] == 5
    assert prepared.loc[0, "math_raw_gain"] == 25


def test_prepare_data_aggregates_sessions_before_student_merge(monkeypatch: pytest.MonkeyPatch) -> None:
    session_df = pd.DataFrame(
        {
            "student_id": ["001", "001", "002"],
            "session_topic": ["math", "ela", "math"],
            "session_date": ["2026-01-15", "2026-01-16", "2026-01-17"],
            "session_duration": [30, 45, 60],
            "tutor_id": ["T1", "T1", "T2"],
        }
    )
    student_df = pd.DataFrame(
        {
            "student_id": ["001", "002", "003"],
            "district_id": ["01", "01", "01"],
            "district_name": ["District", "District", "District"],
            "school_id": ["02", "02", "02"],
            "school_name": ["School", "School", "School"],
            "current_grade_level": [3, 4, 5],
        }
    )
    original_merge = pd.DataFrame.merge
    full_session_merge_calls = []

    def tracking_merge(self, right, *args, **kwargs):
        if len(self) == len(session_df) and len(right) == len(student_df):
            full_session_merge_calls.append((len(self), len(right)))
        return original_merge(self, right, *args, **kwargs)

    monkeypatch.setattr(pd.DataFrame, "merge", tracking_merge)

    prepared = prepare_data(session_df, student_df)

    assert not full_session_merge_calls
    assert prepared.set_index("student_id").loc["001", "total_hours"] == pytest.approx(1.25)
    assert prepared.set_index("student_id").loc["002", "total_hours"] == pytest.approx(1.0)
    assert prepared.set_index("student_id").loc["003", "total_hours"] == pytest.approx(0.0)


def test_session_ingest_leaves_dates_unparsed_until_time_views(tmp_path: Path) -> None:
    session_path = write_csv(
        tmp_path / "session.csv",
        "\n".join(
            [
                "student_id,session_topic,session_date,session_duration,tutor_id",
                "001,math,2026-01-10 09:00:00,45,T1",
                "002,ela,2026-01-11 10:00:00,30,T2",
            ]
        ),
    )

    _, typed_df, errors, _ = load_dataset(session_path, "session")

    assert not errors["critical"]
    assert not pd.api.types.is_datetime64_any_dtype(typed_df["session_date"])
    assert typed_df["session_date"].astype(str).tolist() == ["2026-01-10 09:00:00", "2026-01-11 10:00:00"]


def test_session_validation_does_not_depend_on_row_parser_calls(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    session_path = write_csv(
        tmp_path / "session.csv",
        "\n".join(
            [
                "student_id,session_topic,session_date,session_duration,tutor_id",
                "001,math,2026-01-10,45,T1",
                "002,science,not-a-date,bad,T2",
            ]
        ),
    )

    import toolkit.descriptives as descriptives

    def fail_row_parser(*_args, **_kwargs):
        raise AssertionError("row-wise parser was called")

    monkeypatch.setattr(descriptives, "parse_datetime", fail_row_parser)
    monkeypatch.setattr(descriptives, "parse_numeric", fail_row_parser)

    _, _, errors, _ = load_dataset(session_path, "session")

    warnings = "\n".join(errors["warnings"])
    assert "`session_topic` 'science'" in warnings
    assert "`session_date` 'not-a-date'" in warnings
    assert "`session_duration` 'bad'" in warnings


def test_get_prepared_data_cached_matches_prepare_data() -> None:
    session_df = pd.DataFrame(
        {
            "student_id": ["1"],
            "session_topic": ["ela"],
            "session_date": ["2026-01-10"],
            "session_duration": [60],
            "tutor_id": ["T1"],
        }
    )
    student_df = pd.DataFrame(
        {
            "student_id": ["1"],
            "district_id": ["01"],
            "district_name": ["District"],
            "school_id": ["02"],
            "school_name": ["School"],
            "current_grade_level": [3],
        }
    )

    expected = prepare_data(session_df, student_df)
    cached = get_prepared_data_cached(session_df, student_df)

    assert expected.equals(cached)


def test_get_tutored_students_excludes_zero_hour_students() -> None:
    df = pd.DataFrame(
        {
            "student_id": ["1", "2", "3"],
            "total_hours": [0.0, 2.5, 4.0],
        }
    )

    tutored = get_tutored_students(df)

    assert tutored["student_id"].tolist() == ["2", "3"]


def test_calculate_dosage_metrics_excludes_untutored_students() -> None:
    df = pd.DataFrame(
        {
            "student_id": ["1", "2", "3"],
            "total_hours": [0.0, 30.0, 60.0],
        }
    )

    metrics = calculate_dosage_metrics(df, 60.0)

    assert metrics["tutored_students"] == 2
    assert metrics["mean_hours"] == 45.0
    assert metrics["pct_full_dosage"] == 50.0


def test_calculate_equity_metrics_excludes_untutored_students() -> None:
    df = pd.DataFrame(
        {
            "student_id": ["1", "2", "3", "4"],
            "total_hours": [0.0, 10.0, 20.0, 0.0],
            "ell": pd.array([True, True, False, False], dtype="boolean"),
        }
    )

    metrics = calculate_equity_metrics(df)

    assert metrics["ell_ell_n"] == 1
    assert metrics["ell_non_ell_n"] == 1
    assert metrics["ell_gap"] == -10.0


def test_calculate_outcome_metrics_excludes_untutored_students() -> None:
    df = pd.DataFrame(
        {
            "student_id": ["1", "2"],
            "total_hours": [0.0, 5.0],
            "ela_value_added": [99.0, 3.0],
            "ela_raw_gain": [88.0, 6.0],
        }
    )

    metrics = calculate_outcome_metrics(df)

    assert metrics["ela_va_mean"] == 3.0
    assert metrics["ela_raw_mean"] == 6.0
    assert metrics["ela_va_n"] == 1


def test_calculate_cost_metrics_uses_tutored_students_and_prorates_filtered_view() -> None:
    full_df = pd.DataFrame(
        {
            "student_id": ["1", "2", "3"],
            "total_hours": [0.0, 10.0, 30.0],
            "ela_value_added": [pd.NA, 2.0, 6.0],
            "math_value_added": [pd.NA, 1.0, 3.0],
            "ela_raw_gain": [pd.NA, 4.0, 8.0],
            "math_raw_gain": [pd.NA, 2.0, 4.0],
        }
    )
    filtered_df = full_df[full_df["student_id"].isin(["1", "2"])].copy()

    metrics = calculate_cost_metrics(filtered_df, 4000.0, 20.0, reference_df=full_df)

    assert metrics["tutored_students"] == 1
    assert metrics["allocated_cost"] == pytest.approx(1000.0)
    assert metrics["cost_per_student"] == pytest.approx(1000.0)
    assert metrics["cost_per_hour"] == pytest.approx(100.0)
    assert metrics["cost_allocation_share"] == pytest.approx(0.25)


def test_weighted_metric_average_uses_available_subject_sample_sizes() -> None:
    metrics = {
        "ela_va_mean": 2.0,
        "ela_va_n": 10,
        "math_va_mean": 8.0,
        "math_va_n": 30,
    }

    average = weighted_metric_average(
        metrics,
        (
            ("ela_va_mean", "ela_va_n"),
            ("math_va_mean", "math_va_n"),
        ),
    )

    assert average == pytest.approx(6.5)


def test_generate_student_data_honors_exact_target_tutored_students() -> None:
    config = deepcopy(GENERATOR_CONFIG)
    config["num_students"] = 120
    config["target_tutored_students"] = 40
    set_random_seed(7)

    students, treatment_info, _ = generate_student_data(config)

    assert len(students) == 120
    assert sum(1 for info in treatment_info.values() if info["is_treated"]) == 40


def test_end_to_end_example_metrics_and_readiness() -> None:
    session_path = REPO_ROOT / "utils" / "example_session_dataset.csv"
    student_path = REPO_ROOT / "utils" / "example_student_dataset.csv"

    _, session_df, session_errors, _ = load_dataset(session_path, "session")
    _, student_df, student_errors, _ = load_dataset(student_path, "student")
    prepared = prepare_data(session_df, student_df)
    outcomes = calculate_outcome_metrics(prepared)
    equity = calculate_equity_metrics(prepared)
    readiness = build_module_readiness(prepared, session_df, student_df)

    assert not session_errors["critical"]
    assert not student_errors["critical"]
    assert len(prepared) == len(student_df)
    assert "ela_va_mean" in outcomes
    assert "econ_gap" in equity
    assert not readiness.empty
    assert "Outcomes" in readiness["tab"].tolist()


def test_example_cost_per_student_uses_tutored_students() -> None:
    session_path = REPO_ROOT / "utils" / "example_session_dataset.csv"
    student_path = REPO_ROOT / "utils" / "example_student_dataset.csv"

    _, session_df, _, _ = load_dataset(session_path, "session")
    _, student_df, _, _ = load_dataset(student_path, "student")
    prepared = prepare_data(session_df, student_df)

    metrics = calculate_cost_metrics(prepared, 2_000_000.0, 60.0, reference_df=prepared)

    assert len(student_df) == 2500
    assert metrics["tutored_students"] == 1000
    assert metrics["cost_per_student"] == pytest.approx(2000.0)


def test_mapping_profile_json_round_trip() -> None:
    payload = {
        "version": 1,
        "dataset_profiles": {
            "student": {"custom_column_map": {"Student Number": "student_id"}},
            "session": {"custom_column_map": {"Session DateTime": "session_date"}},
        },
    }

    encoded = json.dumps(payload)
    decoded = json.loads(encoded)

    assert decoded["dataset_profiles"]["student"]["custom_column_map"]["Student Number"] == "student_id"
