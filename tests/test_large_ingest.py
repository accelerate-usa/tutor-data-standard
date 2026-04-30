from __future__ import annotations

import csv
import os
from pathlib import Path

import pandas as pd
import pytest

from toolkit.descriptives import load_dataset, prepare_data
from utils.generate_datasets import CONFIG as GENERATOR_CONFIG


def _write_student_csv(path: Path, num_students: int) -> list[str]:
    student_ids = [f"{index + 1:010d}" for index in range(num_students)]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(
            [
                "student_id",
                "district_id",
                "district_name",
                "school_id",
                "school_name",
                "current_grade_level",
                "ell",
                "iep",
                "economic_disadvantage",
            ]
        )
        for index, student_id in enumerate(student_ids):
            writer.writerow(
                [
                    student_id,
                    "0100001",
                    "Stress Test District",
                    f"{(index % 25) + 1:06d}",
                    f"School {(index % 25) + 1}",
                    index % 13,
                    "TRUE" if index % 5 == 0 else "FALSE",
                    "TRUE" if index % 7 == 0 else "FALSE",
                    "TRUE" if index % 3 == 0 else "FALSE",
                ]
            )
    return student_ids


def _write_session_csv(path: Path, student_ids: list[str], num_rows: int) -> float:
    durations = (30, 45, 60)
    ratios = ("1:1", "1:2", "1:3", "1:4")
    expected_minutes = 0
    base_rows = num_rows // len(student_ids)
    extra_rows = num_rows % len(student_ids)

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["student_id", "session_topic", "session_date", "session_duration", "session_ratio", "tutor_id"])
        for student_index, student_id in enumerate(student_ids):
            row_count = base_rows + (1 if student_index < extra_rows else 0)
            for session_index in range(row_count):
                duration = durations[(student_index + session_index) % len(durations)]
                expected_minutes += duration
                writer.writerow(
                    [
                        student_id,
                        "math" if (student_index + session_index) % 2 == 0 else "ela",
                        f"2025-09-{(session_index % 20) + 1:02d}",
                        duration,
                        ratios[(student_index + session_index) % len(ratios)],
                        f"T{(student_index % 2500) + 1}",
                    ]
                )

    return expected_minutes / 60


def _load_and_prepare_generated_files(tmp_path: Path, num_students: int, num_sessions: int) -> tuple[pd.DataFrame, float]:
    student_path = tmp_path / "students.csv"
    session_path = tmp_path / "sessions.csv"
    student_ids = _write_student_csv(student_path, num_students)
    expected_hours = _write_session_csv(session_path, student_ids, num_sessions)

    _, session_df, session_errors, _ = load_dataset(session_path, "session")
    _, student_df, student_errors, _ = load_dataset(student_path, "student")
    prepared = prepare_data(session_df, student_df)

    assert not session_errors["critical"]
    assert not student_errors["critical"]
    assert not pd.api.types.is_datetime64_any_dtype(session_df["session_date"])
    return prepared, expected_hours


def test_fake_dataset_generator_config_uses_default_scale() -> None:
    assert GENERATOR_CONFIG["num_students"] == 2500
    assert GENERATOR_CONFIG["target_tutored_students"] == 1000
    assert GENERATOR_CONFIG["treatment_proportion"] == 0.4
    assert GENERATOR_CONFIG["add_missing_data"] is False
    assert GENERATOR_CONFIG["student_data_file"].name == "example_student_dataset.csv"
    assert GENERATOR_CONFIG["session_data_file"].name == "example_session_dataset.csv"


def test_large_ingest_aggregates_without_full_session_merge(tmp_path: Path) -> None:
    prepared, expected_hours = _load_and_prepare_generated_files(
        tmp_path,
        num_students=1_200,
        num_sessions=24_000,
    )

    assert len(prepared) == 1_200
    assert prepared["total_hours"].sum() == pytest.approx(expected_hours)
    assert int(prepared["received_tutoring"].sum()) == 1_200


@pytest.mark.slow
def test_million_row_ingest_stress_opt_in(tmp_path: Path) -> None:
    if os.environ.get("DATAS_RUN_FULL_STRESS_TEST") != "1":
        pytest.skip("Set DATAS_RUN_FULL_STRESS_TEST=1 to run the million-row local stress test.")

    prepared, expected_hours = _load_and_prepare_generated_files(
        tmp_path,
        num_students=50_000,
        num_sessions=1_000_000,
    )

    assert len(prepared) == 50_000
    assert prepared["total_hours"].sum() == pytest.approx(expected_hours)
    assert int(prepared["received_tutoring"].sum()) == 50_000
