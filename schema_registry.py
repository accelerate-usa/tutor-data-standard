from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import pandas as pd


TRUE_VALUES = {"true", "1", "yes", "y", "t"}
FALSE_VALUES = {"false", "0", "no", "n", "f"}

SESSION_TOPIC_ALIASES = {
    "ela": "ela",
    "english language arts": "ela",
    "english": "ela",
    "reading": "ela",
    "literacy": "ela",
    "math": "math",
    "mathematics": "math",
    "mathematic": "math",
    "maths": "math",
}

GRADE_ALIASES = {
    "pre-k": -1,
    "prek": -1,
    "prekindergarten": -1,
    "pk": -1,
    "kindergarten": 0,
    "kg": 0,
    "k": 0,
}

OUTCOME_SUBJECTS: Mapping[str, Mapping[str, object]] = {
    "ela": {
        "label": "English Language Arts (ELA)",
        "measure_fields": (
            "ela_outcome_measure_1",
            "ela_outcome_measure_2",
            "ela_outcome_measure_3",
        ),
    },
    "math": {
        "label": "Mathematics",
        "measure_fields": (
            "math_outcome_measure_1",
            "math_outcome_measure_2",
            "math_outcome_measure_3",
        ),
    },
}


@dataclass(frozen=True)
class FieldSpec:
    name: str
    dataset: str
    section: str
    description: str
    data_type: str
    example_values: Tuple[str, ...] = ()
    range_of_values: str = ""
    required: bool = False
    aliases: Tuple[str, ...] = ()
    modules: Tuple[str, ...] = ()
    max_unique: Optional[int] = None

    @property
    def all_names(self) -> Tuple[str, ...]:
        return (self.name, *self.aliases)


STUDENT_FIELD_SPECS: Tuple[FieldSpec, ...] = (
    FieldSpec(
        name="student_id",
        dataset="student",
        section="Identifiers",
        description="Unique identifier for the student. Stored and matched as text.",
        data_type="identifier",
        example_values=("0016740395", "S67890"),
        range_of_values="Any non-empty string. Must match the session file exactly after trimming whitespace.",
        required=True,
        modules=("overview", "dosage", "equity", "outcomes", "cost"),
    ),
    FieldSpec(
        name="district_id",
        dataset="student",
        section="Identifiers",
        description="District identifier stored as text to preserve leading zeros.",
        data_type="identifier",
        example_values=("0803360",),
        range_of_values="Any non-empty string.",
        required=True,
        modules=("overview", "dosage", "equity", "outcomes", "cost"),
    ),
    FieldSpec(
        name="district_name",
        dataset="student",
        section="Identifiers",
        description="District name.",
        data_type="string",
        example_values=("Denver Public Schools",),
        range_of_values="Free text.",
        required=True,
        modules=("overview",),
    ),
    FieldSpec(
        name="school_id",
        dataset="student",
        section="Identifiers",
        description="School identifier stored as text to preserve leading zeros.",
        data_type="identifier",
        example_values=("631930",),
        range_of_values="Any non-empty string.",
        required=True,
        modules=("overview", "dosage", "equity", "outcomes", "cost"),
    ),
    FieldSpec(
        name="school_name",
        dataset="student",
        section="Identifiers",
        description="School name.",
        data_type="string",
        example_values=("Denver High School",),
        range_of_values="Free text.",
        required=True,
        modules=("overview", "dosage", "equity", "outcomes", "cost"),
    ),
    FieldSpec(
        name="current_grade_level",
        dataset="student",
        section="Student Characteristics",
        description="Current grade level served. Upload accepts numeric grades plus common labels such as K and Pre-K.",
        data_type="integer",
        example_values=("8", "K", "Pre-K"),
        range_of_values="-1 through 12 after normalization.",
        required=True,
        modules=("overview", "dosage", "equity", "outcomes", "cost"),
    ),
    FieldSpec(
        name="gender",
        dataset="student",
        section="Student Characteristics",
        description="Student gender category as reported locally.",
        data_type="categorical",
        example_values=("Female", "Male", "Nonbinary", "Unknown"),
        range_of_values="No more than 5 unique strings is recommended.",
        aliases=("sex",),
        modules=("dosage",),
        max_unique=5,
    ),
    FieldSpec(
        name="ethnicity",
        dataset="student",
        section="Student Characteristics",
        description="Student ethnicity or race category as reported locally.",
        data_type="categorical",
        example_values=("White", "Hispanic or Latino", "Black or African American"),
        range_of_values="No more than 10 unique strings is recommended.",
        modules=("dosage", "equity"),
        max_unique=10,
    ),
    FieldSpec(
        name="ell",
        dataset="student",
        section="Student Characteristics",
        description="English learner flag. Blank values are treated as unknown rather than false.",
        data_type="tri_state_flag",
        example_values=("TRUE", "FALSE", "Unknown"),
        range_of_values="Boolean-like values or blank.",
        aliases=("english_learner", "english_language_learner"),
        modules=("equity",),
    ),
    FieldSpec(
        name="iep",
        dataset="student",
        section="Student Characteristics",
        description="IEP flag. Blank values are treated as unknown rather than false.",
        data_type="tri_state_flag",
        example_values=("TRUE", "FALSE", "Unknown"),
        range_of_values="Boolean-like values or blank.",
        modules=("equity",),
    ),
    FieldSpec(
        name="gifted_flag",
        dataset="student",
        section="Student Characteristics",
        description="Gifted flag.",
        data_type="tri_state_flag",
        example_values=("TRUE", "FALSE", "Unknown"),
        range_of_values="Boolean-like values or blank.",
    ),
    FieldSpec(
        name="homeless_flag",
        dataset="student",
        section="Student Characteristics",
        description="Homelessness flag.",
        data_type="tri_state_flag",
        example_values=("TRUE", "FALSE", "Unknown"),
        range_of_values="Boolean-like values or blank.",
    ),
    FieldSpec(
        name="disability",
        dataset="student",
        section="Student Characteristics",
        description="Disability flag.",
        data_type="tri_state_flag",
        example_values=("TRUE", "FALSE", "Unknown"),
        range_of_values="Boolean-like values or blank.",
    ),
    FieldSpec(
        name="economic_disadvantage",
        dataset="student",
        section="Student Characteristics",
        description="Economic disadvantage flag.",
        data_type="tri_state_flag",
        example_values=("TRUE", "FALSE", "Unknown"),
        range_of_values="Boolean-like values or blank.",
        aliases=("free_reduced_lunch",),
        modules=("equity",),
    ),
    FieldSpec(
        name="ela_outcome_measure_1",
        dataset="student",
        section="Ordered Outcome Measures",
        description="Earliest available numeric ELA outcome measure.",
        data_type="numeric_outcome",
        example_values=("712",),
        range_of_values="Any comparable numeric outcome scale. Measure 1 is the earliest observation in order.",
        aliases=("ela_state_score_two_years_ago", "ela_outcome_score_two_years_ago"),
        modules=("outcomes",),
    ),
    FieldSpec(
        name="ela_outcome_measure_2",
        dataset="student",
        section="Ordered Outcome Measures",
        description="Middle or later numeric ELA outcome measure.",
        data_type="numeric_outcome",
        example_values=("726",),
        range_of_values="Any comparable numeric outcome scale. Measure 2 must be later than measure 1.",
        aliases=("ela_state_score_one_year_ago", "ela_outcome_score_one_year_ago"),
        modules=("outcomes",),
    ),
    FieldSpec(
        name="ela_outcome_measure_3",
        dataset="student",
        section="Ordered Outcome Measures",
        description="Most recent numeric ELA outcome measure.",
        data_type="numeric_outcome",
        example_values=("775",),
        range_of_values="Any comparable numeric outcome scale. Measure 3 is the most recent observation.",
        aliases=("ela_state_score_current_year", "ela_outcome_score_current_year"),
        modules=("outcomes", "equity"),
    ),
    FieldSpec(
        name="math_outcome_measure_1",
        dataset="student",
        section="Ordered Outcome Measures",
        description="Earliest available numeric math outcome measure.",
        data_type="numeric_outcome",
        example_values=("705",),
        range_of_values="Any comparable numeric outcome scale. Measure 1 is the earliest observation in order.",
        aliases=("math_state_score_two_years_ago", "math_outcome_score_two_years_ago"),
        modules=("outcomes",),
    ),
    FieldSpec(
        name="math_outcome_measure_2",
        dataset="student",
        section="Ordered Outcome Measures",
        description="Middle or later numeric math outcome measure.",
        data_type="numeric_outcome",
        example_values=("719",),
        range_of_values="Any comparable numeric outcome scale. Measure 2 must be later than measure 1.",
        aliases=("math_state_score_one_year_ago", "math_outcome_score_one_year_ago"),
        modules=("outcomes",),
    ),
    FieldSpec(
        name="math_outcome_measure_3",
        dataset="student",
        section="Ordered Outcome Measures",
        description="Most recent numeric math outcome measure.",
        data_type="numeric_outcome",
        example_values=("741",),
        range_of_values="Any comparable numeric outcome scale. Measure 3 is the most recent observation.",
        aliases=("math_state_score_current_year", "math_outcome_score_current_year"),
        modules=("outcomes", "equity"),
    ),
    FieldSpec(
        name="performance_level_previous",
        dataset="student",
        section="Performance Levels",
        description="The previous available categorical performance level, if reported.",
        data_type="categorical",
        example_values=("Basic", "Proficient"),
        range_of_values="No more than 6 unique strings is recommended.",
        aliases=("performance_level_prior_year",),
        modules=("equity",),
        max_unique=6,
    ),
    FieldSpec(
        name="performance_level_most_recent",
        dataset="student",
        section="Performance Levels",
        description="The most recent categorical performance level, if reported.",
        data_type="categorical",
        example_values=("Basic", "Advanced"),
        range_of_values="No more than 6 unique strings is recommended.",
        aliases=("performance_level_current_year",),
        modules=("equity",),
        max_unique=6,
    ),
    FieldSpec(
        name="performance_level_earliest",
        dataset="student",
        section="Performance Levels",
        description="The earliest available categorical performance level, if reported.",
        data_type="categorical",
        example_values=("Basic",),
        range_of_values="No more than 6 unique strings is recommended.",
        aliases=("performance_level_two_years_ago",),
        max_unique=6,
    ),
)


SESSION_FIELD_SPECS: Tuple[FieldSpec, ...] = (
    FieldSpec(
        name="student_id",
        dataset="session",
        section="Core Session Data",
        description="Unique identifier for the student. Must match the student file exactly after trimming whitespace.",
        data_type="identifier",
        example_values=("0016740395", "S67890"),
        range_of_values="Any non-empty string.",
        required=True,
        modules=("overview", "dosage", "equity", "outcomes", "cost"),
    ),
    FieldSpec(
        name="session_topic",
        dataset="session",
        section="Core Session Data",
        description="Tutoring subject. Intake normalizes common aliases such as 'reading' to 'ela' and 'mathematics' to 'math'.",
        data_type="categorical",
        example_values=("math", "ela", "reading"),
        range_of_values="Currently supported analysis expects math or ela after normalization.",
        required=True,
        modules=("overview", "dosage"),
        max_unique=2,
    ),
    FieldSpec(
        name="session_date",
        dataset="session",
        section="Core Session Data",
        description="Date or datetime for the tutoring session.",
        data_type="datetime",
        example_values=("2024-06-15", "2024-06-15 10:30:00"),
        range_of_values="Any parseable date or datetime.",
        aliases=("session_datetime",),
        required=True,
        modules=("overview", "dosage"),
    ),
    FieldSpec(
        name="session_duration",
        dataset="session",
        section="Core Session Data",
        description="Duration of the session in minutes.",
        data_type="numeric",
        example_values=("45", "60"),
        range_of_values="Non-negative numeric values.",
        required=True,
        modules=("overview", "dosage", "equity", "outcomes", "cost"),
    ),
    FieldSpec(
        name="session_ratio",
        dataset="session",
        section="Core Session Data",
        description="Student-to-tutor ratio.",
        data_type="string",
        example_values=("1:1", "1:3"),
        range_of_values="Free text or ratio notation.",
    ),
    FieldSpec(
        name="tutor_id",
        dataset="session",
        section="Core Session Data",
        description="Unique identifier for the tutor.",
        data_type="identifier",
        example_values=("T54321", "98765"),
        range_of_values="Any non-empty string.",
        required=True,
        modules=("overview",),
    ),
)


DATASET_SCHEMAS: Mapping[str, Tuple[FieldSpec, ...]] = {
    "student": STUDENT_FIELD_SPECS,
    "session": SESSION_FIELD_SPECS,
}


def normalize_name(name: object) -> str:
    return str(name).strip().lower()


def get_schema(dataset: str) -> Tuple[FieldSpec, ...]:
    return DATASET_SCHEMAS[dataset]


def get_canonical_columns(dataset: str) -> List[str]:
    return [field.name for field in get_schema(dataset)]


def get_field_map(dataset: str) -> Dict[str, FieldSpec]:
    return {field.name: field for field in get_schema(dataset)}


def get_alias_lookup(dataset: str) -> Dict[str, str]:
    lookup: Dict[str, str] = {}
    for field in get_schema(dataset):
        for name in field.all_names:
            lookup[normalize_name(name)] = field.name
    return lookup


def get_module_columns(dataset: str) -> Dict[str, List[str]]:
    module_columns: Dict[str, List[str]] = {}
    for field in get_schema(dataset):
        for module in field.modules:
            module_columns.setdefault(module, []).append(field.name)
    return module_columns


def get_outcome_measure_fields(subject: str) -> Tuple[str, str, str]:
    return tuple(OUTCOME_SUBJECTS[subject]["measure_fields"])  # type: ignore[return-value]


def get_latest_outcome_field(subject: str) -> str:
    return get_outcome_measure_fields(subject)[-1]


def make_blank_series(index: pd.Index) -> pd.Series:
    return pd.Series(pd.NA, index=index, dtype="object")


def clean_raw_series(series: pd.Series) -> pd.Series:
    cleaned = series.copy()

    def _clean(value: object) -> object:
        if pd.isna(value):
            return pd.NA
        text = str(value).strip()
        return pd.NA if text == "" else text

    return cleaned.map(_clean)


def normalize_dataframe_columns(df: pd.DataFrame, dataset: str) -> Tuple[pd.DataFrame, Dict[str, object]]:
    alias_lookup = get_alias_lookup(dataset)
    normalized = pd.DataFrame(index=df.index)
    alias_sources: Dict[str, List[str]] = {}
    combined_columns: Dict[str, List[str]] = {}
    unknown_columns: List[str] = []

    grouped_columns: Dict[str, List[str]] = {}
    for column in df.columns:
        normalized_name = normalize_name(column)
        canonical = alias_lookup.get(normalized_name)
        if canonical is None:
            canonical = str(column).strip()
            unknown_columns.append(canonical)
        else:
            alias_sources.setdefault(canonical, []).append(str(column))
        grouped_columns.setdefault(canonical, []).append(str(column))

    for output_column, source_columns in grouped_columns.items():
        combined = make_blank_series(df.index)
        for source_column in source_columns:
            combined = combined.combine_first(clean_raw_series(df[source_column]))
        normalized[output_column] = combined
        if len(source_columns) > 1:
            combined_columns[output_column] = source_columns

    report = {
        "alias_sources": alias_sources,
        "combined_columns": combined_columns,
        "unknown_columns": unknown_columns,
    }
    return normalized, report


def parse_flag(value: object) -> Tuple[object, bool]:
    if pd.isna(value):
        return pd.NA, True
    normalized = normalize_name(value)
    if normalized in TRUE_VALUES:
        return True, True
    if normalized in FALSE_VALUES:
        return False, True
    if normalized in {"unknown", "declined", "declined to provide", "na", "n/a"}:
        return pd.NA, True
    return pd.NA, False


def parse_grade(value: object) -> Tuple[object, bool]:
    if pd.isna(value):
        return pd.NA, True
    normalized = normalize_name(value)
    if normalized in GRADE_ALIASES:
        return GRADE_ALIASES[normalized], True
    try:
        numeric = float(str(value).strip())
        integer = int(numeric)
        return (integer, integer == numeric)
    except (TypeError, ValueError):
        return pd.NA, False


def parse_numeric(value: object) -> Tuple[object, bool]:
    if pd.isna(value):
        return pd.NA, True
    try:
        return float(str(value).strip()), True
    except (TypeError, ValueError):
        return pd.NA, False


def parse_datetime(value: object) -> Tuple[object, bool]:
    if pd.isna(value):
        return pd.NaT, True
    parsed = pd.to_datetime(value, errors="coerce")
    return parsed, not pd.isna(parsed)


def normalize_session_topic(value: object) -> Tuple[object, bool]:
    if pd.isna(value):
        return pd.NA, True
    normalized = normalize_name(value)
    canonical = SESSION_TOPIC_ALIASES.get(normalized)
    if canonical:
        return canonical, True
    return str(value).strip().lower(), False


def coerce_dataframe_types(df: pd.DataFrame, dataset: str) -> pd.DataFrame:
    typed = df.copy()
    field_map = get_field_map(dataset)

    for column in typed.columns:
        spec = field_map.get(column)
        if spec is None:
            continue

        raw_series = clean_raw_series(typed[column])

        if spec.data_type in {"identifier", "string", "categorical"}:
            typed[column] = raw_series.astype("string")
        elif spec.data_type == "tri_state_flag":
            typed[column] = pd.array([parse_flag(value)[0] for value in raw_series], dtype="boolean")
        elif spec.data_type == "integer":
            typed[column] = pd.array([parse_grade(value)[0] for value in raw_series], dtype="Int64")
        elif spec.data_type in {"numeric", "numeric_outcome"}:
            typed[column] = pd.to_numeric(raw_series, errors="coerce").astype("Float64")
        elif spec.data_type == "datetime":
            typed[column] = pd.to_datetime(raw_series, errors="coerce")

    if "session_topic" in typed.columns:
        typed["session_topic"] = pd.Series(
            [normalize_session_topic(value)[0] for value in clean_raw_series(typed["session_topic"])],
            index=typed.index,
            dtype="string",
        )

    return typed


def outcome_support_columns() -> List[str]:
    columns: List[str] = []
    for subject in OUTCOME_SUBJECTS:
        columns.extend(get_outcome_measure_fields(subject))
    return columns


def dictionary_rows(dataset: str) -> List[Mapping[str, object]]:
    rows: List[Mapping[str, object]] = []
    for field in get_schema(dataset):
        rows.append(
            {
                "section": field.section,
                "column_name": field.name,
                "description": field.description,
                "data_type": field.data_type,
                "required": "yes" if field.required else "recommended",
                "example_values": ", ".join(field.example_values),
                "range_of_values": field.range_of_values,
                "aliases": ", ".join(field.aliases),
                "used_in": ", ".join(field.modules),
            }
        )
    return rows


def dictionary_dataframe(dataset: str) -> pd.DataFrame:
    return pd.DataFrame(dictionary_rows(dataset))


def required_columns(dataset: str) -> List[str]:
    return [field.name for field in get_schema(dataset) if field.required]


def categorical_limits(dataset: str) -> Dict[str, int]:
    return {
        field.name: field.max_unique
        for field in get_schema(dataset)
        if field.max_unique is not None
    }

