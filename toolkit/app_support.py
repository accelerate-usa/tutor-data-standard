from __future__ import annotations

import json
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import pandas as pd

from schema_registry import get_field_map, get_outcome_measure_fields, get_schema, normalize_name


TAB_LABELS = {
    "overview": "Program Overview",
    "dosage": "Dosage & Access",
    "equity": "Equity Analysis",
    "outcomes": "Outcomes",
    "cost": "Cost Analytics",
}

FILTER_FIELD_OVERRIDES = {
    "dosage": ("gender", "ethnicity"),
    "equity": ("gender", "ethnicity", "ell", "iep", "economic_disadvantage"),
    "outcomes": ("gender", "ethnicity", "ell", "iep", "economic_disadvantage"),
    "cost": ("gender", "ethnicity"),
}

TRI_STATE_FILTER_OPTIONS = {
    "All": "all",
    "Yes": "true",
    "No": "false",
    "Unknown": "unknown",
}


def apply_custom_column_map(
    df: pd.DataFrame,
    custom_column_map: Optional[Mapping[str, str]] = None,
) -> Tuple[pd.DataFrame, Dict[str, str]]:
    if not custom_column_map:
        return df.copy(), {}

    normalized_map = {normalize_name(source): target for source, target in custom_column_map.items()}
    renamed = df.copy()
    applied: Dict[str, str] = {}
    rename_lookup: Dict[str, str] = {}

    for column in renamed.columns:
        normalized = normalize_name(column)
        target = normalized_map.get(normalized)
        if target:
            rename_lookup[column] = target
            applied[str(column)] = target

    if rename_lookup:
        renamed = renamed.rename(columns=rename_lookup)

    return renamed, applied


def parse_mapping_profile_text(profile_text: str) -> Dict[str, object]:
    payload = json.loads(profile_text)
    if not isinstance(payload, dict):
        raise ValueError("Mapping profile must be a JSON object.")
    dataset_profiles = payload.get("dataset_profiles")
    if not isinstance(dataset_profiles, dict):
        raise ValueError("Mapping profile is missing `dataset_profiles`.")
    for dataset_name in ("session", "student"):
        dataset_profile = dataset_profiles.get(dataset_name, {})
        if not isinstance(dataset_profile, dict):
            raise ValueError(f"Mapping profile entry for `{dataset_name}` must be an object.")
        custom_map = dataset_profile.get("custom_column_map", {})
        if custom_map and not isinstance(custom_map, dict):
            raise ValueError(f"`custom_column_map` for `{dataset_name}` must be an object.")
    return payload


def get_profile_column_map(
    profile_payload: Optional[Mapping[str, object]],
    dataset: str,
) -> Dict[str, str]:
    if not profile_payload:
        return {}
    dataset_profiles = profile_payload.get("dataset_profiles", {})
    if not isinstance(dataset_profiles, Mapping):
        return {}
    dataset_profile = dataset_profiles.get(dataset, {})
    if not isinstance(dataset_profile, Mapping):
        return {}
    custom_map = dataset_profile.get("custom_column_map", {})
    if not isinstance(custom_map, Mapping):
        return {}
    return {str(source): str(target) for source, target in custom_map.items()}


def get_filter_specs(df: pd.DataFrame, module: str) -> List[Dict[str, object]]:
    specs: List[Dict[str, object]] = []

    if "school_name" in df.columns:
        school_options = sorted(df["school_name"].dropna().astype(str).unique().tolist())
        if school_options:
            specs.append(
                {
                    "field": "school_name",
                    "label": "School",
                    "kind": "single",
                    "options": ["All", *school_options],
                    "default": "All",
                }
            )

    if "current_grade_level" in df.columns:
        grade_options = sorted(df["current_grade_level"].dropna().unique().tolist())
        if grade_options:
            specs.append(
                {
                    "field": "current_grade_level",
                    "label": "Grade Levels",
                    "kind": "multi",
                    "options": grade_options,
                    "default": grade_options,
                }
            )

    field_map = get_field_map("student")
    for field_name in FILTER_FIELD_OVERRIDES.get(module, ()):
        if field_name not in df.columns or field_name not in field_map:
            continue
        spec = field_map[field_name]
        if spec.data_type == "tri_state_flag":
            specs.append(
                {
                    "field": field_name,
                    "label": spec.description.split(".")[0],
                    "kind": "tri_state",
                    "options": list(TRI_STATE_FILTER_OPTIONS.keys()),
                    "default": "All",
                }
            )
            continue

        options = sorted(df[field_name].dropna().astype(str).unique().tolist())
        if options:
            specs.append(
                {
                    "field": field_name,
                    "label": field_name.replace("_", " ").title(),
                    "kind": "multi",
                    "options": options,
                    "default": options,
                }
            )

    return specs


def summarize_active_filters(filter_values: Mapping[str, object], filter_specs: Sequence[Mapping[str, object]]) -> str:
    parts: List[str] = []
    for spec in filter_specs:
        field = str(spec["field"])
        label = str(spec["label"])
        kind = str(spec["kind"])
        default = spec["default"]
        value = filter_values.get(field, default)

        if kind == "single":
            if value != default:
                parts.append(f"{label}: {value}")
            continue

        if kind == "tri_state":
            if value != default:
                parts.append(f"{label}: {value}")
            continue

        selected = list(value) if isinstance(value, (list, tuple, set)) else []
        default_values = list(default) if isinstance(default, (list, tuple, set)) else []
        if not selected or selected == default_values:
            continue
        if len(selected) <= 2:
            summary = ", ".join(str(item) for item in selected)
        else:
            summary = f"{len(selected)} selected"
        parts.append(f"{label}: {summary}")

    return "; ".join(parts)


def apply_filter_values(df: pd.DataFrame, filter_values: Mapping[str, object]) -> pd.DataFrame:
    filtered = df.copy()

    school_name = filter_values.get("school_name")
    if school_name and school_name != "All" and "school_name" in filtered.columns:
        filtered = filtered[filtered["school_name"] == school_name]

    grade_levels = filter_values.get("current_grade_level")
    if isinstance(grade_levels, (list, tuple, set)) and grade_levels and "current_grade_level" in filtered.columns:
        filtered = filtered[filtered["current_grade_level"].isin(list(grade_levels))]

    for field_name, value in filter_values.items():
        if field_name in {"school_name", "current_grade_level"} or field_name not in filtered.columns:
            continue

        if value == "All" or value == "all" or value is None:
            continue

        field_spec = get_field_map("student").get(field_name)
        if field_spec and field_spec.data_type == "tri_state_flag":
            normalized_value = normalize_name(value)
            if normalized_value in {"yes", "true"}:
                filtered = filtered[filtered[field_name].eq(True)]
            elif normalized_value in {"no", "false"}:
                filtered = filtered[filtered[field_name].eq(False)]
            elif normalized_value == "unknown":
                filtered = filtered[filtered[field_name].isna()]
            continue

        if isinstance(value, (list, tuple, set)):
            selected = list(value)
            default_options = sorted(filtered[field_name].dropna().astype(str).unique().tolist())
            if selected and selected != default_options:
                filtered = filtered[filtered[field_name].astype(str).isin([str(item) for item in selected])]

    return filtered


def build_unknown_denominator_notes(df: pd.DataFrame, fields: Mapping[str, str]) -> List[str]:
    notes: List[str] = []
    total_students = len(df)
    if total_students == 0:
        return notes

    for field_name, label in fields.items():
        if field_name not in df.columns:
            continue
        unknown_count = int(df[field_name].isna().sum())
        if unknown_count <= 0:
            continue
        unknown_pct = unknown_count / total_students * 100
        notes.append(f"{label}: {unknown_pct:.1f}% unknown and excluded from subgroup-specific comparisons")

    return notes


def build_normalization_summary_rows(
    dataset: str,
    raw_df: Optional[pd.DataFrame],
    normalized_df: Optional[pd.DataFrame],
    report: Optional[Mapping[str, object]],
    errors: Optional[Mapping[str, Sequence[str]]],
) -> pd.DataFrame:
    alias_sources = report.get("alias_sources", {}) if report else {}
    combined_columns = report.get("combined_columns", {}) if report else {}
    unknown_columns = report.get("unknown_columns", []) if report else []
    applied_custom_map = report.get("applied_custom_column_map", {}) if report else {}
    critical_count = len(errors.get("critical", [])) if errors else 0
    warning_count = len(errors.get("warnings", [])) if errors else 0
    info_count = len(errors.get("info", [])) if errors else 0

    return pd.DataFrame(
        [
            {
                "dataset": dataset.title(),
                "uploaded_rows": len(raw_df) if raw_df is not None else 0,
                "canonical_columns": len(normalized_df.columns) if normalized_df is not None else 0,
                "renamed_columns": sum(
                    1
                    for canonical, source_columns in alias_sources.items()
                    if isinstance(source_columns, Sequence)
                    and any(normalize_name(source_column) != str(canonical) for source_column in source_columns)
                ),
                "merged_columns": len(combined_columns) if isinstance(combined_columns, Mapping) else 0,
                "unknown_columns": len(unknown_columns) if isinstance(unknown_columns, Sequence) else 0,
                "profile_mappings_applied": len(applied_custom_map) if isinstance(applied_custom_map, Mapping) else 0,
                "critical_issues": critical_count,
                "warnings": warning_count,
                "info_messages": info_count,
            }
        ]
    )


def build_normalization_detail_rows(
    dataset: str,
    report: Optional[Mapping[str, object]],
) -> pd.DataFrame:
    if not report:
        return pd.DataFrame(columns=["dataset", "canonical_column", "source_columns", "status"])

    rows: List[Dict[str, object]] = []
    alias_sources = report.get("alias_sources", {})
    combined_columns = report.get("combined_columns", {})
    unknown_columns = report.get("unknown_columns", [])

    if isinstance(alias_sources, Mapping):
        for canonical, source_columns in alias_sources.items():
            if not isinstance(source_columns, Sequence):
                continue
            status = "Accepted as canonical"
            if any(normalize_name(source_column) != str(canonical) for source_column in source_columns):
                status = "Mapped from alias"
            if isinstance(combined_columns, Mapping) and canonical in combined_columns:
                status = "Merged alias columns"
            rows.append(
                {
                    "dataset": dataset.title(),
                    "canonical_column": canonical,
                    "source_columns": ", ".join(str(source_column) for source_column in source_columns),
                    "status": status,
                }
            )

    if isinstance(unknown_columns, Sequence):
        for unknown_column in unknown_columns:
            rows.append(
                {
                    "dataset": dataset.title(),
                    "canonical_column": "",
                    "source_columns": str(unknown_column),
                    "status": "Not used by current schema",
                }
            )

    if not rows:
        return pd.DataFrame(columns=["dataset", "canonical_column", "source_columns", "status"])
    return pd.DataFrame(rows)


def build_module_readiness(
    prepared_df: Optional[pd.DataFrame],
    session_df: Optional[pd.DataFrame],
    student_df: Optional[pd.DataFrame],
) -> pd.DataFrame:
    prepared_columns = set(prepared_df.columns) if prepared_df is not None else set()
    session_columns = set(session_df.columns) if session_df is not None else set()
    student_columns = set(student_df.columns) if student_df is not None else set()

    def missing(columns: Iterable[str], available: set[str]) -> List[str]:
        return [column for column in columns if column not in available]

    rows: List[Dict[str, object]] = []

    def add_row(tab: str, section: str, status: str, detail: str) -> None:
        rows.append({"tab": TAB_LABELS[tab], "section": section, "status": status, "detail": detail})

    dosage_missing = missing(["total_hours"], prepared_columns)
    add_row(
        "dosage",
        "Dosage summary and distribution",
        "Ready" if not dosage_missing else "Unavailable",
        "Uses merged student/session dosage totals." if not dosage_missing else f"Missing: {', '.join(dosage_missing)}",
    )

    subject_missing = missing(["school_name", "total_hours"], prepared_columns) + missing(
        ["student_id", "session_topic", "session_duration"],
        session_columns,
    )
    add_row(
        "dosage",
        "School and subject dosage tables",
        "Ready" if not subject_missing else "Unavailable",
        "School and subject dosage breakdowns are available." if not subject_missing else f"Missing: {', '.join(subject_missing)}",
    )

    time_missing = missing(["session_date", "session_duration"], session_columns)
    add_row(
        "dosage",
        "Time-of-day and over-time implementation views",
        "Ready" if not time_missing else "Unavailable",
        "Session timestamps can power implementation timing views." if not time_missing else f"Missing: {', '.join(time_missing)}",
    )

    available_gap_fields = [field for field in ("ell", "iep", "economic_disadvantage") if field in prepared_columns]
    if "total_hours" not in prepared_columns or not available_gap_fields:
        add_row(
            "equity",
            "Subgroup dosage gaps",
            "Unavailable",
            "Requires total_hours plus at least one of ell, iep, or economic_disadvantage.",
        )
    else:
        add_row(
            "equity",
            "Subgroup dosage gaps",
            "Partial" if len(available_gap_fields) < 3 else "Ready",
            f"Available subgroup fields: {', '.join(available_gap_fields)}",
        )

    ethnicity_missing = missing(["ethnicity", "total_hours"], prepared_columns)
    add_row(
        "equity",
        "Ethnicity dosage comparison",
        "Ready" if not ethnicity_missing else "Unavailable",
        "Ethnicity dosage comparison is available." if not ethnicity_missing else f"Missing: {', '.join(ethnicity_missing)}",
    )

    proficiency_missing = missing(["performance_level_most_recent", "student_id"], prepared_columns) + missing(["student_id"], session_columns)
    add_row(
        "equity",
        "Tutoring by proficiency level",
        "Ready" if not proficiency_missing else "Unavailable",
        "Most recent performance level can be compared with tutoring participation." if not proficiency_missing else f"Missing: {', '.join(proficiency_missing)}",
    )

    latest_outcome_columns = [f"{subject}_latest_outcome" for subject in ("ela", "math") if f"{subject}_latest_outcome" in prepared_columns]
    if "student_id" in session_columns and latest_outcome_columns:
        add_row(
            "equity",
            "Tutoring likelihood by latest outcome",
            "Partial" if len(latest_outcome_columns) == 1 else "Ready",
            f"Available latest outcomes: {', '.join(latest_outcome_columns)}",
        )
    else:
        add_row(
            "equity",
            "Tutoring likelihood by latest outcome",
            "Unavailable",
            "Requires session student_id and at least one latest outcome measure.",
        )

    for subject in ("ela", "math"):
        required_columns = [f"{subject}_raw_gain", f"{subject}_value_added"]
        subject_missing = missing(required_columns, prepared_columns)
        add_row(
            "outcomes",
            f"{subject.upper()} value-added and raw gain",
            "Ready" if not subject_missing else "Unavailable",
            "Three ordered measures are available for this subject." if not subject_missing else f"Missing derived columns: {', '.join(subject_missing)}",
        )

    basic_cost_missing = missing(["total_hours"], prepared_columns)
    add_row(
        "cost",
        "Basic cost metrics",
        "Ready" if not basic_cost_missing else "Unavailable",
        "Cost per student and per hour are available." if not basic_cost_missing else f"Missing: {', '.join(basic_cost_missing)}",
    )

    outcome_cost_columns = [
        column
        for column in ("ela_value_added", "math_value_added", "ela_raw_gain", "math_raw_gain")
        if column in prepared_columns
    ]
    if outcome_cost_columns:
        add_row(
            "cost",
            "Outcome-based cost metrics",
            "Ready",
            f"Available outcome columns: {', '.join(outcome_cost_columns)}",
        )
    else:
        add_row(
            "cost",
            "Outcome-based cost metrics",
            "Unavailable",
            "Requires at least one raw gain or value-added outcome series.",
        )

    readiness_df = pd.DataFrame(rows)
    if readiness_df.empty:
        return readiness_df

    tab_rows: List[Dict[str, object]] = []
    for tab_name, tab_df in readiness_df.groupby("tab", sort=False):
        statuses = set(tab_df["status"].tolist())
        if statuses == {"Ready"}:
            status = "Ready"
        elif "Ready" in statuses or "Partial" in statuses:
            status = "Partial"
        else:
            status = "Unavailable"
        detail = "; ".join(
            f"{row.section}: {row.detail}"
            for row in tab_df.itertuples(index=False)
            if row.status != "Ready"
        )
        tab_rows.append({"tab": tab_name, "section": "Tab summary", "status": status, "detail": detail or "All tracked sections available."})

    summary_df = pd.DataFrame(tab_rows)
    return pd.concat([summary_df, readiness_df], ignore_index=True)


def get_tab_readiness_notes(readiness_df: pd.DataFrame, tab_label: str) -> Tuple[str, List[str]]:
    if readiness_df.empty:
        return "Unavailable", []
    tab_df = readiness_df[readiness_df["tab"] == tab_label]
    if tab_df.empty:
        return "Unavailable", []

    summary_row = tab_df[tab_df["section"] == "Tab summary"]
    status = summary_row["status"].iloc[0] if not summary_row.empty else "Unavailable"
    details = [
        f"{row.section}: {row.detail}"
        for row in tab_df.itertuples(index=False)
        if row.section != "Tab summary" and row.status != "Ready"
    ]
    return str(status), details
