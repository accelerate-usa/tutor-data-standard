"""
DATAS Analysis Toolkit - Enhanced Version
A production-quality Streamlit application for analyzing tutoring program data.

Designed for policymakers, district leaders, and funders.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from scipy import stats
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
from functools import lru_cache
import json
import os
import platform
import re
import subprocess
from io import StringIO
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
DATAS_APP_VERSION = "1.0.0"
DATAS_BUILD_LABEL = "2026-04-30-runtime-diagnostics"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from schema_registry import (
    OUTCOME_SUBJECTS,
    SESSION_TOPIC_ALIASES,
    categorical_limits,
    clean_raw_series,
    coerce_dataframe_types,
    get_field_map,
    get_module_columns,
    get_outcome_measure_fields,
    normalize_dataframe_columns,
    normalize_name,
    normalize_session_topic,
    parse_datetime,
    parse_flag,
    parse_grade,
    parse_numeric,
    required_columns,
)
from toolkit.app_support import (
    TAB_LABELS,
    TRI_STATE_FILTER_OPTIONS,
    apply_custom_column_map,
    apply_filter_values,
    build_module_readiness,
    build_normalization_detail_rows,
    build_normalization_summary_rows,
    build_unknown_denominator_notes,
    get_filter_specs,
    get_profile_column_map,
    get_tab_readiness_notes,
    parse_mapping_profile_text,
    summarize_active_filters,
)

# Page configuration
st.set_page_config(
    page_title="DATAS Program Analysis",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for professional styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1f77b4;
        margin-bottom: 0.5rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .insight-box {
        background-color: #fff3cd;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #ffc107;
        margin: 1rem 0;
    }
    .warning-box {
        background-color: #f8d7da;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #dc3545;
        margin: 1rem 0;
    }
    .success-box {
        background-color: #d4edda;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #28a745;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# METRIC HELPERS
# ============================================================================

@lru_cache(maxsize=1)
def get_runtime_build_info() -> Dict[str, str]:
    """Return deployment details that help distinguish stale Cloud builds."""
    commit = ""
    commit_source = ""
    for env_key in (
        "STREAMLIT_GIT_COMMIT",
        "GIT_COMMIT",
        "COMMIT_SHA",
        "SOURCE_COMMIT",
        "SOURCE_VERSION",
        "GITHUB_SHA",
    ):
        env_value = os.environ.get(env_key, "").strip()
        if env_value:
            commit = env_value[:12]
            commit_source = env_key
            break

    branch = os.environ.get("GIT_BRANCH", "").strip()
    if not commit:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short=12", "HEAD"],
                cwd=REPO_ROOT,
                capture_output=True,
                check=True,
                text=True,
                timeout=2,
            )
            commit = result.stdout.strip()
            commit_source = "git rev-parse"
        except Exception:
            commit = "unknown"
            commit_source = "not available"

    if not branch:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=REPO_ROOT,
                capture_output=True,
                check=True,
                text=True,
                timeout=2,
            )
            branch = result.stdout.strip()
        except Exception:
            branch = "unknown"

    config_path = REPO_ROOT / ".streamlit" / "config.toml"
    watcher_status = "config file not found"
    if config_path.exists():
        try:
            config_text = config_path.read_text(encoding="utf-8")
            watcher_status = (
                "utils/stress_test_data blacklisted"
                if "utils/stress_test_data" in config_text
                else "config found; stress-test folder not listed"
            )
        except OSError:
            watcher_status = "config file found; unable to read"

    return {
        "datas_version": DATAS_APP_VERSION,
        "build_label": DATAS_BUILD_LABEL,
        "git_commit": commit,
        "git_commit_source": commit_source,
        "git_branch": branch,
        "streamlit_version": st.__version__,
        "python_version": platform.python_version(),
        "watcher_config": watcher_status,
    }


def render_runtime_diagnostics() -> None:
    """Render compact deployment details for Cloud troubleshooting."""
    info = get_runtime_build_info()
    with st.expander("Runtime diagnostics", expanded=False):
        st.caption("Use this to confirm the hosted app has picked up the latest GitHub deployment.")
        st.code(
            "\n".join(
                [
                    f"DATAS app version: {info['datas_version']}",
                    f"Build label: {info['build_label']}",
                    f"Git commit: {info['git_commit']} ({info['git_commit_source']})",
                    f"Git branch: {info['git_branch']}",
                    f"Streamlit: {info['streamlit_version']}",
                    f"Python: {info['python_version']}",
                    f"Watcher config: {info['watcher_config']}",
                ]
            ),
            language="text",
        )


def build_metric_help(formula_lines: Sequence[str], explanation: str, notes: Optional[Sequence[str]] = None) -> str:
    """Build markdown-safe help text with formula-first formatting."""
    sections = ["**Formula**", "\n".join(f"`{line}`" for line in formula_lines)]
    if explanation:
        sections.append(explanation)
    if notes:
        sections.append("\n".join(notes))
    return "\n\n".join(section for section in sections if section)


OUTCOME_MEASURE_HELP_NOTE = (
    "`M1` = earliest score, `M2` = middle score, `M3` = most recent score, "
    "all on the same assessment scale."
)

# ============================================================================
# DATA VALIDATION FUNCTIONS
# ============================================================================

def validate_data_comprehensive(df: pd.DataFrame, data_type: str) -> Dict[str, List[str]]:
    """
    Comprehensive data validation function.
    Returns a dictionary with error categories and messages.
    """
    errors = {
        'critical': [],  # Errors that prevent analysis
        'warnings': [],  # Issues that may affect analysis
        'info': []       # Informational messages
    }
    
    # Check if dataframe is empty
    if df is None or df.empty:
        errors['critical'].append("The file is empty or could not be read.")
        return errors
    
    # Normalize column names (strip whitespace)
    df.columns = df.columns.str.strip()
    headers = list(df.columns)
    
    # Define expected columns based on data type
    if data_type == 'session':
        expected_required = ["student_id", "session_topic", "session_date", "session_duration", "tutor_id"]
        expected_optional = ["session_ratio"]  # Optional columns
    elif data_type == 'student':
        expected_required = [
            "student_id", "district_id", "district_name", "school_id", "school_name",
            "current_grade_level", "gender", "ethnicity", "ell", "iep", "gifted_flag",
            "homeless_flag", "ela_state_score_two_years_ago", "ela_state_score_one_year_ago",
            "ela_state_score_current_year", "math_state_score_two_years_ago",
            "math_state_score_one_year_ago", "math_state_score_current_year",
            "performance_level_prior_year", "performance_level_current_year",
            "disability", "economic_disadvantage"
        ]
        expected_optional = ["performance_level_two_years_ago"]  # Optional columns
    else:
        errors['critical'].append(f"Unknown data type: {data_type}")
        return errors
    
    # Check for missing required columns (treat as warnings, not blocking)
    missing_required = [col for col in expected_required if col not in headers]
    if missing_required:
        errors['warnings'].append(f"**Missing Recommended Columns ({len(missing_required)}):**")
        errors['warnings'].append("**Note:** Analysis will proceed, but some features may not work without these columns.")
        for col in missing_required:
            errors['warnings'].append(f"  • `{col}`")
    
    # Check for unexpected/extra columns
    all_expected = expected_required + expected_optional
    extra_columns = [col for col in headers if col not in all_expected]
    if extra_columns:
        errors['warnings'].append(f"**Unexpected Columns Found ({len(extra_columns)}):**")
        for col in extra_columns[:10]:  # Limit to first 10
            errors['warnings'].append(f"  • `{col}` (will be ignored)")
        if len(extra_columns) > 10:
            errors['warnings'].append(f"  ... and {len(extra_columns) - 10} more")
    
    # Validate data types and values row by row
    if data_type == 'session':
        errors = _validate_session_data(df, errors)
    elif data_type == 'student':
        errors = _validate_student_data(df, errors)
    
    return errors


def _validate_session_data(df: pd.DataFrame, errors: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """Validate session data row by row."""
    row_errors = []
    missing_value_errors = []
    
    # Check for missing values in important columns
    important_cols = ['student_id', 'session_topic', 'session_date', 'session_duration', 'tutor_id']
    for col in important_cols:
        if col in df.columns:
            missing_count = df[col].isna().sum()
            if missing_count > 0:
                missing_value_errors.append(f"  • `{col}`: {missing_count:,} missing values")
    
    if missing_value_errors:
        errors['warnings'].append("**Missing Values in Important Columns:**")
        errors['warnings'].extend(missing_value_errors)
    
    # Validate each row
    for idx, row in df.iterrows():
        row_num = idx + 2  # +2 because Excel/CSV row 1 is header
        
        # Validate student_id
        if 'student_id' in df.columns:
            sid = str(row['student_id']).strip()
            if pd.isna(row['student_id']) or sid == '' or sid == 'nan':
                row_errors.append(f"Row {row_num}: `student_id` is missing")
            elif not re.match(r'^\d+$', sid):
                row_errors.append(f"Row {row_num}: `student_id` '{sid}' should contain only digits")
        
        # Validate session_topic
        if 'session_topic' in df.columns:
            topic = str(row['session_topic']).strip().lower()
            if pd.isna(row['session_topic']) or topic == '' or topic == 'nan':
                row_errors.append(f"Row {row_num}: `session_topic` is missing")
            elif topic not in ['math', 'ela']:
                row_errors.append(f"Row {row_num}: `session_topic` '{row['session_topic']}' must be 'math' or 'ela'")
        
        # Validate session_date
        if 'session_date' in df.columns:
            date_str = str(row['session_date']).strip()
            if pd.isna(row['session_date']) or date_str == '' or date_str == 'nan':
                row_errors.append(f"Row {row_num}: `session_date` is missing")
            else:
                # Try to parse as datetime - accept various formats
                date_valid = False
                # Try common datetime formats
                date_formats = [
                    '%Y-%m-%d',           # YYYY-MM-DD
                    '%Y-%m-%d %H:%M:%S',  # YYYY-MM-DD HH:MM:SS
                    '%Y-%m-%d %H:%M',     # YYYY-MM-DD HH:MM
                    '%Y/%m/%d',           # YYYY/MM/DD
                    '%Y/%m/%d %H:%M:%S',  # YYYY/MM/DD HH:MM:SS
                    '%m/%d/%Y',           # MM/DD/YYYY
                    '%m/%d/%Y %H:%M:%S',  # MM/DD/YYYY HH:MM:SS
                ]
                
                for fmt in date_formats:
                    try:
                        datetime.strptime(date_str, fmt)
                        date_valid = True
                        break
                    except ValueError:
                        continue
                
                # Also try pandas to_datetime as fallback (handles many formats)
                if not date_valid:
                    try:
                        pd.to_datetime(date_str)
                        date_valid = True
                    except (ValueError, TypeError):
                        pass
                
                if not date_valid:
                    row_errors.append(f"Row {row_num}: `session_date` '{date_str}' is not a valid date or datetime")
        
        # Validate session_duration
        if 'session_duration' in df.columns:
            if pd.isna(row['session_duration']):
                row_errors.append(f"Row {row_num}: `session_duration` is missing")
            else:
                try:
                    dur = float(row['session_duration'])
                    if dur < 0:
                        row_errors.append(f"Row {row_num}: `session_duration` {dur} must be greater than or equal to 0")
                except (ValueError, TypeError):
                    row_errors.append(f"Row {row_num}: `session_duration` '{row['session_duration']}' must be a number")
        
        # Validate tutor_id
        if 'tutor_id' in df.columns:
            tid = str(row['tutor_id']).strip()
            if pd.isna(row['tutor_id']) or tid == '' or tid == 'nan':
                row_errors.append(f"Row {row_num}: `tutor_id` is missing")
    
    # Limit row errors to prevent overwhelming output
    if row_errors:
        errors['warnings'].append(f"**Data Quality Issues (showing first 20):**")
        errors['warnings'].extend(row_errors[:20])
        if len(row_errors) > 20:
            errors['warnings'].append(f"  ... and {len(row_errors) - 20} more issues")
    
    return errors


def _validate_student_data(df: pd.DataFrame, errors: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """Validate student data row by row."""
    row_errors = []
    missing_value_errors = []
    
    # Check for missing values in important columns
    important_cols = ['student_id', 'district_id', 'school_id']
    for col in important_cols:
        if col in df.columns:
            missing_count = df[col].isna().sum()
            if missing_count > 0:
                missing_value_errors.append(f"  • `{col}`: {missing_count:,} missing values")
    
    if missing_value_errors:
        errors['warnings'].append("**Missing Values in Important Columns:**")
        errors['warnings'].extend(missing_value_errors)
    
    # Track unique values for validation
    unique_ethnicities = set()
    unique_perf_levels_prior = set()
    unique_perf_levels_current = set()
    
    # Validate each row
    for idx, row in df.iterrows():
        row_num = idx + 2  # +2 because Excel/CSV row 1 is header
        
        # Validate student_id
        if 'student_id' in df.columns:
            sid = str(row['student_id']).strip()
            if pd.isna(row['student_id']) or sid == '' or sid == 'nan':
                row_errors.append(f"Row {row_num}: `student_id` is missing")
        
        # Validate district_id
        if 'district_id' in df.columns:
            did = str(row['district_id']).strip()
            if pd.isna(row['district_id']) or did == '' or did == 'nan':
                row_errors.append(f"Row {row_num}: `district_id` is missing")
        
        # Validate school_id
        if 'school_id' in df.columns:
            sid = str(row['school_id']).strip()
            if pd.isna(row['school_id']) or sid == '' or sid == 'nan':
                row_errors.append(f"Row {row_num}: `school_id` is missing")
        
        # Validate current_grade_level
        if 'current_grade_level' in df.columns:
            if pd.isna(row['current_grade_level']):
                row_errors.append(f"Row {row_num}: `current_grade_level` is missing")
            else:
                try:
                    grade = int(float(row['current_grade_level']))
                    if grade < -1 or grade > 12:
                        row_errors.append(f"Row {row_num}: `current_grade_level` {grade} must be between -1 and 12")
                except (ValueError, TypeError):
                    row_errors.append(f"Row {row_num}: `current_grade_level` '{row['current_grade_level']}' must be an integer")
        
        # Validate boolean fields
        bool_fields = ['ell', 'iep', 'gifted_flag', 'homeless_flag', 'disability', 'economic_disadvantage']
        for field in bool_fields:
            if field in df.columns:
                val = str(row[field]).strip().lower()
                valid_bools = ['true', 'false', '1', '0', 't', 'f', 'yes', 'no', 'y', 'n', 'male', 'female']
                if pd.isna(row[field]) or val == '' or val == 'nan':
                    # Missing boolean values are warnings, not critical
                    pass
                elif val not in valid_bools:
                    row_errors.append(f"Row {row_num}: `{field}` '{row[field]}' must be a boolean (TRUE/FALSE, 1/0, Yes/No, etc.)")
        
        # Validate numeric score fields
        score_fields = [
            'ela_state_score_two_years_ago', 'ela_state_score_one_year_ago', 'ela_state_score_current_year',
            'math_state_score_two_years_ago', 'math_state_score_one_year_ago', 'math_state_score_current_year'
        ]
        for field in score_fields:
            if field in df.columns and not pd.isna(row[field]):
                try:
                    float(row[field])
                except (ValueError, TypeError):
                    row_errors.append(f"Row {row_num}: `{field}` '{row[field]}' must be a number")
        
        # Track unique values
        if 'ethnicity' in df.columns and not pd.isna(row.get('ethnicity')):
            unique_ethnicities.add(str(row['ethnicity']).strip())
        if 'performance_level_prior_year' in df.columns and not pd.isna(row.get('performance_level_prior_year')):
            unique_perf_levels_prior.add(str(row['performance_level_prior_year']).strip())
        if 'performance_level_current_year' in df.columns and not pd.isna(row.get('performance_level_current_year')):
            unique_perf_levels_current.add(str(row['performance_level_current_year']).strip())
    
    # Check for too many unique values (data quality issue)
    if len(unique_ethnicities) > 10:
        errors['warnings'].append(f"`ethnicity` column has {len(unique_ethnicities)} unique values (expected ≤10). This may indicate data quality issues.")
    if len(unique_perf_levels_prior) > 6:
        errors['warnings'].append(f"`performance_level_prior_year` column has {len(unique_perf_levels_prior)} unique values (expected ≤6).")
    if len(unique_perf_levels_current) > 6:
        errors['warnings'].append(f"`performance_level_current_year` column has {len(unique_perf_levels_current)} unique values (expected ≤6).")
    
    # Limit row errors to prevent overwhelming output
    if row_errors:
        errors['warnings'].append(f"**Data Quality Issues (showing first 20):**")
        errors['warnings'].extend(row_errors[:20])
        if len(row_errors) > 20:
            errors['warnings'].append(f"  ... and {len(row_errors) - 20} more issues")
    
    return errors


def get_source_name(source) -> str:
    if isinstance(source, (str, Path)):
        return Path(source).name
    return getattr(source, "name", "uploaded_file")


def reset_source(source) -> None:
    if hasattr(source, "seek"):
        source.seek(0)


def read_tabular_data(source) -> pd.DataFrame:
    source_name = get_source_name(source)
    suffix = Path(source_name).suffix.lower()

    if isinstance(source, (str, Path)):
        if suffix == ".csv":
            return pd.read_csv(source, dtype=str, keep_default_na=False)
        if suffix in {".xlsx", ".xls"}:
            return pd.read_excel(source, dtype=str)
        if suffix == ".json":
            return pd.read_json(source)
    else:
        reset_source(source)
        if suffix == ".csv":
            return pd.read_csv(source, dtype=str, keep_default_na=False)
        if suffix in {".xlsx", ".xls"}:
            return pd.read_excel(source, dtype=str)
        if suffix == ".json":
            payload = source.read()
            reset_source(source)
            if isinstance(payload, bytes):
                payload = payload.decode("utf-8")
            return pd.read_json(StringIO(payload))

    raise ValueError(f"Unsupported file type for '{source_name}'. Upload CSV, XLSX, XLS, or JSON.")


def load_dataset(
    source,
    data_type: str,
    custom_column_map: Optional[Mapping[str, str]] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, List[str]], Dict[str, object]]:
    raw_df = read_tabular_data(source)
    remapped_raw_df, applied_custom_map = apply_custom_column_map(raw_df, custom_column_map)
    normalized_raw_df, normalization_report = normalize_dataframe_columns(remapped_raw_df, data_type)
    normalization_report["applied_custom_column_map"] = applied_custom_map
    validation_errors = validate_data_comprehensive(normalized_raw_df, data_type, normalization_report)
    typed_df = coerce_dataframe_types(normalized_raw_df, data_type)
    return normalized_raw_df, typed_df, validation_errors, normalization_report


def validate_data_comprehensive(
    df: pd.DataFrame,
    data_type: str,
    normalization_report: Optional[Dict[str, object]] = None,
) -> Dict[str, List[str]]:
    """Comprehensive data validation with schema-aware column aliases and module hints."""
    errors = {
        'critical': [],
        'warnings': [],
        'info': []
    }

    if df is None or df.empty:
        errors['critical'].append("The file is empty or could not be read.")
        return errors

    headers = [str(column).strip() for column in df.columns]
    expected_required = required_columns(data_type)
    field_map = get_field_map(data_type)
    module_columns = get_module_columns(data_type)
    all_expected = list(field_map.keys())

    missing_required = [column for column in expected_required if column not in headers]
    if missing_required:
        errors['warnings'].append(f"**Missing Core Columns ({len(missing_required)}):**")
        errors['warnings'].append("**Note:** Analysis can still load, but core summaries and joins may be incomplete.")
        for column in missing_required:
            errors['warnings'].append(f"  • `{column}`")

    for module_name, module_fields in module_columns.items():
        if module_name == "overview":
            continue
        optional_module_fields = [field for field in module_fields if field not in expected_required]
        missing_module_fields = [field for field in optional_module_fields if field not in headers]
        if missing_module_fields:
            errors['info'].append(
                f"Missing `{module_name}` support columns: {', '.join(f'`{field}`' for field in missing_module_fields)}"
            )

    extra_columns = [column for column in headers if column not in all_expected]
    if extra_columns:
        errors['warnings'].append(f"**Unexpected Columns Found ({len(extra_columns)}):**")
        for column in extra_columns[:10]:
            errors['warnings'].append(f"  • `{column}` (accepted but not used by the current dashboard)")
        if len(extra_columns) > 10:
            errors['warnings'].append(f"  ... and {len(extra_columns) - 10} more")

    if normalization_report:
        alias_sources = normalization_report.get("alias_sources", {})
        if isinstance(alias_sources, dict):
            alias_messages = []
            for canonical, source_columns in alias_sources.items():
                if isinstance(source_columns, list):
                    legacy_columns = [source for source in source_columns if normalize_name(source) != canonical]
                    if legacy_columns:
                        alias_messages.append(f"`{canonical}` from {', '.join(f'`{source}`' for source in legacy_columns)}")
            if alias_messages:
                errors['info'].append("Accepted legacy column names: " + "; ".join(alias_messages))

        combined_columns = normalization_report.get("combined_columns", {})
        if isinstance(combined_columns, dict) and combined_columns:
            details = []
            for canonical, source_columns in combined_columns.items():
                if isinstance(source_columns, list):
                    details.append(f"`{canonical}` ← {', '.join(f'`{source}`' for source in source_columns)}")
            if details:
                errors['info'].append("Merged duplicate/alias columns: " + "; ".join(details))

    if data_type == 'session':
        errors = _validate_session_data(df, errors)
    elif data_type == 'student':
        errors = _validate_student_data(df, errors)
    else:
        errors['critical'].append(f"Unknown data type: {data_type}")

    return errors


def _append_missing_value_messages(df: pd.DataFrame, columns: List[str], errors: Dict[str, List[str]]) -> None:
    missing_value_errors = []
    for column in columns:
        if column in df.columns:
            missing_count = clean_raw_series(df[column]).isna().sum()
            if missing_count > 0:
                missing_value_errors.append(f"  • `{column}`: {missing_count:,} missing values")

    if missing_value_errors:
        errors['warnings'].append("**Missing Values in Important Columns:**")
        errors['warnings'].extend(missing_value_errors)


def _validate_session_data(df: pd.DataFrame, errors: Dict[str, List[str]]) -> Dict[str, List[str]]:
    _append_missing_value_messages(df, ['student_id', 'session_topic', 'session_date', 'session_duration', 'tutor_id'], errors)

    row_errors: List[str] = []
    issue_count = 0

    def add_row_issues(mask: pd.Series, message_for_index) -> None:
        nonlocal issue_count
        matching = mask[mask]
        count = int(len(matching))
        if count == 0:
            return
        issue_count += count
        remaining_slots = max(0, 20 - len(row_errors))
        if remaining_slots == 0:
            return
        for idx in matching.index[:remaining_slots]:
            row_errors.append(message_for_index(idx))

    if 'student_id' in df.columns:
        student_ids = clean_raw_series(df['student_id'])
        add_row_issues(
            student_ids.isna(),
            lambda idx: f"Row {idx + 2}: `student_id` is missing",
        )

    if 'session_topic' in df.columns:
        topics = clean_raw_series(df['session_topic'])
        normalized_topics = topics.astype("string").str.strip().str.lower()
        canonical_topics = normalized_topics.map(lambda value: SESSION_TOPIC_ALIASES.get(value, value), na_action="ignore")
        invalid_topics = topics.notna() & ~canonical_topics.isin({"math", "ela"})
        add_row_issues(
            invalid_topics,
            lambda idx: f"Row {idx + 2}: `session_topic` '{topics.loc[idx]}' is not currently supported. Use math/ela or a recognized alias.",
        )

    if 'session_date' in df.columns:
        dates = clean_raw_series(df['session_date'])
        parsed_dates = pd.to_datetime(dates, errors="coerce")
        invalid_dates = dates.notna() & parsed_dates.isna()
        add_row_issues(
            invalid_dates,
            lambda idx: f"Row {idx + 2}: `session_date` '{dates.loc[idx]}' is not a valid date or datetime",
        )

    if 'session_duration' in df.columns:
        durations = clean_raw_series(df['session_duration'])
        numeric_durations = pd.to_numeric(durations, errors="coerce")
        invalid_durations = durations.notna() & numeric_durations.isna()
        negative_durations = durations.notna() & numeric_durations.notna() & (numeric_durations < 0)
        add_row_issues(
            invalid_durations,
            lambda idx: f"Row {idx + 2}: `session_duration` '{durations.loc[idx]}' must be numeric minutes",
        )
        add_row_issues(
            negative_durations,
            lambda idx: f"Row {idx + 2}: `session_duration` {numeric_durations.loc[idx]} must be greater than or equal to 0",
        )

    if 'tutor_id' in df.columns:
        tutor_ids = clean_raw_series(df['tutor_id'])
        add_row_issues(
            tutor_ids.isna(),
            lambda idx: f"Row {idx + 2}: `tutor_id` is missing",
        )

    if issue_count:
        errors['warnings'].append("**Data Quality Issues (showing first 20):**")
        errors['warnings'].extend(row_errors)
        if issue_count > 20:
            errors['warnings'].append(f"  ... and {issue_count - 20} more issues")

    return errors


def _validate_student_data(df: pd.DataFrame, errors: Dict[str, List[str]]) -> Dict[str, List[str]]:
    row_errors = []
    _append_missing_value_messages(df, ['student_id', 'district_id', 'school_id'], errors)

    field_map = get_field_map('student')
    tri_state_fields = [field_name for field_name, field in field_map.items() if field.data_type == 'tri_state_flag']
    numeric_outcome_fields = [field_name for field_name, field in field_map.items() if field.data_type == 'numeric_outcome']
    unique_limits = categorical_limits('student')
    unique_tracker = {field_name: set() for field_name in unique_limits}

    for idx, row in df.iterrows():
        row_num = idx + 2

        for identifier_field in ['student_id', 'district_id', 'school_id']:
            if identifier_field in df.columns and pd.isna(row.get(identifier_field)):
                row_errors.append(f"Row {row_num}: `{identifier_field}` is missing")

        if 'current_grade_level' in df.columns:
            value = row.get('current_grade_level')
            grade, grade_valid = parse_grade(value)
            if pd.isna(value):
                row_errors.append(f"Row {row_num}: `current_grade_level` is missing")
            elif not grade_valid:
                row_errors.append(f"Row {row_num}: `current_grade_level` '{value}' must be an integer grade, K, or Pre-K")
            elif grade < -1 or grade > 12:
                row_errors.append(f"Row {row_num}: `current_grade_level` {grade} must be between -1 and 12")

        for field_name in tri_state_fields:
            if field_name in df.columns:
                value = row.get(field_name)
                _, flag_valid = parse_flag(value)
                if not pd.isna(value) and not flag_valid:
                    row_errors.append(f"Row {row_num}: `{field_name}` '{value}' must be a boolean-like value (TRUE/FALSE, 1/0, Yes/No) or blank")

        for field_name in numeric_outcome_fields:
            if field_name in df.columns:
                value = row.get(field_name)
                _, numeric_valid = parse_numeric(value)
                if not pd.isna(value) and not numeric_valid:
                    row_errors.append(f"Row {row_num}: `{field_name}` '{value}' must be numeric")

        for field_name, max_unique in unique_limits.items():
            if field_name in df.columns and not pd.isna(row.get(field_name)):
                unique_tracker[field_name].add(str(row.get(field_name)).strip())

    for field_name, observed_values in unique_tracker.items():
        max_unique = unique_limits[field_name]
        if len(observed_values) > max_unique:
            errors['warnings'].append(
                f"`{field_name}` has {len(observed_values)} unique values (recommended ≤{max_unique}). This may indicate misspellings or duplicate categories."
            )

    if row_errors:
        errors['warnings'].append("**Data Quality Issues (showing first 20):**")
        errors['warnings'].extend(row_errors[:20])
        if len(row_errors) > 20:
            errors['warnings'].append(f"  ... and {len(row_errors) - 20} more issues")

    return errors


def display_validation_errors(errors: Dict[str, List[str]], data_type: str) -> bool:
    """
    Display validation errors in a user-friendly way.
    Returns True if there are any issues (errors or warnings), False otherwise.
    Note: This function no longer blocks data loading - it just informs the user.
    """
    has_critical = len(errors.get('critical', [])) > 0
    has_warnings = len(errors.get('warnings', [])) > 0
    has_info = len(errors.get('info', [])) > 0
    
    if not (has_critical or has_warnings or has_info):
        st.success(f"✅ **{data_type.capitalize()} data validation passed!**")
        return False
    
    # Display critical errors as warnings (since we're not blocking)
    if has_critical:
        st.warning("### ⚠️ Data Quality Issues Found")
        st.markdown("**The following issues were detected in your data:**")
        for error in errors['critical']:
            st.markdown(error)
        st.markdown("**Note:** Analysis will proceed, but results may be affected by these issues.")
        st.markdown("---")
    
    # Display warnings
    if has_warnings:
        st.warning("### ⚠️ Warnings")
        st.markdown("**These issues may affect analysis quality:**")
        for warning in errors['warnings']:
            st.markdown(warning)
        st.markdown("---")
    
    # Display info messages
    if has_info:
        st.info("### ℹ️ Information")
        for info in errors['info']:
            st.markdown(info)
        st.markdown("---")
    
    return has_critical or has_warnings


# ============================================================================
# DATA PREPARATION FUNCTIONS
# ============================================================================

def false_mask(index: pd.Index) -> pd.Series:
    return pd.Series(False, index=index)


def flag_equals(df: pd.DataFrame, field: str, target: bool) -> pd.Series:
    if field not in df.columns:
        return false_mask(df.index)
    return df[field].eq(target).fillna(False)


def tutoring_hours_series(df: pd.DataFrame) -> pd.Series:
    if 'total_hours' not in df.columns:
        return pd.Series(0.0, index=df.index, dtype=float)
    return pd.to_numeric(df['total_hours'], errors='coerce').fillna(0.0)


def get_tutored_student_mask(df: pd.DataFrame) -> pd.Series:
    return tutoring_hours_series(df) > 0


def get_tutored_students(df: pd.DataFrame) -> pd.DataFrame:
    return df.loc[get_tutored_student_mask(df)].copy()


def summarize_analysis_population(df: pd.DataFrame) -> Dict[str, object]:
    matched_students = len(df)
    analysis_df = get_tutored_students(df)
    tutored_students = len(analysis_df)
    pct_tutored = (tutored_students / matched_students * 100) if matched_students > 0 else 0.0
    return {
        'matched_students': matched_students,
        'tutored_students': tutored_students,
        'pct_tutored': pct_tutored,
        'analysis_df': analysis_df,
    }


def add_outcome_summary_columns(student_df: pd.DataFrame) -> pd.DataFrame:
    student_df = student_df.copy()

    for subject in OUTCOME_SUBJECTS:
        measure_fields = [field for field in get_outcome_measure_fields(subject) if field in student_df.columns]
        ordered_fields = get_outcome_measure_fields(subject)
        latest_col = f"{subject}_latest_outcome"
        raw_col = f"{subject}_raw_gain"
        va_col = f"{subject}_value_added"

        if measure_fields:
            student_df[latest_col] = student_df[list(reversed(measure_fields))].bfill(axis=1).iloc[:, 0]
        else:
            student_df[latest_col] = np.nan

        if all(field in student_df.columns for field in ordered_fields):
            first, second, third = ordered_fields
            student_df[raw_col] = student_df[third] - student_df[first]
            student_df[va_col] = (student_df[third] - student_df[second]) - (student_df[second] - student_df[first])
        else:
            student_df[raw_col] = np.nan
            student_df[va_col] = np.nan

    return student_df


def prepare_data(session_df: pd.DataFrame, student_df: pd.DataFrame) -> pd.DataFrame:
    """Prepare student-level analysis data without materializing session-level joins."""
    session_df = session_df.copy()
    student_df = student_df.copy()
    
    # Standardize student_id if it exists
    if 'student_id' in session_df.columns:
        session_df['student_id'] = session_df['student_id'].astype('string').str.strip()
    if 'student_id' in student_df.columns:
        student_df['student_id'] = student_df['student_id'].astype('string').str.strip()
    else:
        # If student_id is missing, we can't proceed
        return student_df
    
    if 'student_id' not in session_df.columns or 'session_duration' not in session_df.columns:
        hours_per_student = pd.DataFrame({'student_id': student_df['student_id'].unique(), 'total_hours': 0.0})
    else:
        try:
            session_duration_hours = pd.to_numeric(session_df['session_duration'], errors='coerce') / 60
            session_hours = pd.DataFrame(
                {
                    'student_id': session_df['student_id'],
                    'session_duration_hours': session_duration_hours,
                }
            )
            valid_student_ids = pd.Index(student_df['student_id'].dropna().unique())
            session_hours = session_hours[session_hours['student_id'].isin(valid_student_ids)]
            hours_per_student = (
                session_hours.groupby('student_id', as_index=False)['session_duration_hours']
                .sum()
                .rename(columns={'session_duration_hours': 'total_hours'})
            )
        except:
            hours_per_student = pd.DataFrame({'student_id': student_df['student_id'].unique(), 'total_hours': 0.0})
    
    # Merge hours back
    try:
        student_with_hours = student_df.merge(hours_per_student, on='student_id', how='left')
        student_with_hours['total_hours'] = student_with_hours['total_hours'].fillna(0)
    except:
        student_with_hours = student_df.copy()
        student_with_hours['total_hours'] = 0

    student_with_hours['received_tutoring'] = tutoring_hours_series(student_with_hours) > 0
    return add_outcome_summary_columns(student_with_hours)


def apply_filters(df: pd.DataFrame, filters: Dict) -> pd.DataFrame:
    """Apply filters to dataframe."""
    filtered_df = df.copy()
    
    if filters.get('school') and filters['school'] != 'All':
        filtered_df = filtered_df[filtered_df['school_name'] == filters['school']]
    
    if filters.get('grades'):
        filtered_df = filtered_df[filtered_df['current_grade_level'].isin(filters['grades'])]
    
    if filters.get('ell') is not None:
        filtered_df = filtered_df[flag_equals(filtered_df, 'ell', filters['ell'])]
    
    if filters.get('iep') is not None:
        filtered_df = filtered_df[flag_equals(filtered_df, 'iep', filters['iep'])]
    
    if filters.get('economic_disadvantage') is not None:
        filtered_df = filtered_df[flag_equals(filtered_df, 'economic_disadvantage', filters['economic_disadvantage'])]
    
    if filters.get('gender'):
        filtered_df = filtered_df[filtered_df['gender'].isin(filters['gender'])]
    
    if filters.get('ethnicity'):
        filtered_df = filtered_df[filtered_df['ethnicity'].isin(filters['ethnicity'])]
    
    return filtered_df


# ============================================================================
# METRICS CALCULATION FUNCTIONS
# ============================================================================

def calculate_dosage_metrics(df: pd.DataFrame, target_dosage: float) -> Dict:
    """Calculate comprehensive dosage metrics."""
    analysis_df = get_tutored_students(df)
    hours = tutoring_hours_series(analysis_df)

    if len(analysis_df) == 0:
        return {}
    
    metrics = {
        'median_hours': hours.median(),
        'mean_hours': hours.mean(),
        'q25': hours.quantile(0.25),
        'q75': hours.quantile(0.75),
        'iqr': hours.quantile(0.75) - hours.quantile(0.25),
        'tutored_students': len(analysis_df),
        'target_dosage': target_dosage,
        'total_tutoring_hours': hours.sum(),
    }
    
    # Dosage categories (quartiles)
    metrics['pct_below_25'] = (hours < target_dosage * 0.25).sum() / len(analysis_df) * 100
    metrics['pct_25_50'] = ((hours >= target_dosage * 0.25) & (hours < target_dosage * 0.5)).sum() / len(analysis_df) * 100
    metrics['pct_50_75'] = ((hours >= target_dosage * 0.5) & (hours < target_dosage * 0.75)).sum() / len(analysis_df) * 100
    metrics['pct_75_99'] = ((hours >= target_dosage * 0.75) & (hours < target_dosage)).sum() / len(analysis_df) * 100
    metrics['pct_full_dosage'] = (hours >= target_dosage).sum() / len(analysis_df) * 100
    
    # Gini coefficient (simple proxy for inequality)
    sorted_hours = np.sort(hours)
    n = len(sorted_hours)
    if n > 0 and sorted_hours.sum() > 0:
        cumsum = np.cumsum(sorted_hours)
        metrics['gini'] = (2 * np.sum((np.arange(1, n + 1)) * sorted_hours)) / (n * cumsum[-1]) - (n + 1) / n
    else:
        metrics['gini'] = 0
    
    return metrics


def calculate_equity_metrics(df: pd.DataFrame) -> Dict:
    """Calculate equity gaps in dosage."""
    metrics = {}
    
    # ELL vs non-ELL
    if 'ell' in df.columns:
        ell_hours = df[df['ell'] == True]['total_hours'].dropna()
        non_ell_hours = df[df['ell'] == False]['total_hours'].dropna()
        if len(ell_hours) > 0 and len(non_ell_hours) > 0:
            metrics['ell_gap'] = ell_hours.mean() - non_ell_hours.mean()  # Positive = ELL students get more
            metrics['ell_ell_mean'] = ell_hours.mean()
            metrics['ell_non_ell_mean'] = non_ell_hours.mean()
            metrics['ell_ell_n'] = len(ell_hours)
            metrics['ell_non_ell_n'] = len(non_ell_hours)
    
    # IEP vs non-IEP
    if 'iep' in df.columns:
        iep_hours = df[df['iep'] == True]['total_hours'].dropna()
        non_iep_hours = df[df['iep'] == False]['total_hours'].dropna()
        if len(iep_hours) > 0 and len(non_iep_hours) > 0:
            metrics['iep_gap'] = iep_hours.mean() - non_iep_hours.mean()  # Positive = IEP students get more
            metrics['iep_iep_mean'] = iep_hours.mean()
            metrics['iep_non_iep_mean'] = non_iep_hours.mean()
            metrics['iep_iep_n'] = len(iep_hours)
            metrics['iep_non_iep_n'] = len(non_iep_hours)
    
    # Economic disadvantage
    if 'economic_disadvantage' in df.columns:
        econ_hours = df[df['economic_disadvantage'] == True]['total_hours'].dropna()
        non_econ_hours = df[df['economic_disadvantage'] == False]['total_hours'].dropna()
        if len(econ_hours) > 0 and len(non_econ_hours) > 0:
            metrics['econ_gap'] = econ_hours.mean() - non_econ_hours.mean()  # Positive = disadvantaged students get more
            metrics['econ_disadv_mean'] = econ_hours.mean()
            metrics['econ_adv_mean'] = non_econ_hours.mean()
            metrics['econ_disadv_n'] = len(econ_hours)
            metrics['econ_adv_n'] = len(non_econ_hours)
    
    # High-need students vs total students reaching target dosage
    target_dosage = st.session_state.get('full_dosage_threshold', 60.0)
    high_need_mask = (
        (df.get('ell', pd.Series([False] * len(df))) == True) |
        (df.get('iep', pd.Series([False] * len(df))) == True) |
        (df.get('economic_disadvantage', pd.Series([False] * len(df))) == True)
    )
    high_need_students = df[high_need_mask]
    if len(high_need_students) > 0:
        metrics['high_need_full_dosage_pct'] = (
            (high_need_students['total_hours'] >= target_dosage).sum() / len(high_need_students) * 100
        )
        metrics['high_need_n'] = len(high_need_students)
    # Total students at target dosage
    total_at_target = (df['total_hours'] >= target_dosage).sum()
    metrics['total_full_dosage_pct'] = total_at_target / len(df) * 100 if len(df) > 0 else 0
    metrics['total_n'] = len(df)
    
    return metrics


def calculate_outcome_metrics(df: pd.DataFrame) -> Dict:
    """Calculate outcome metrics for ELA and Math."""
    metrics = {}
    
    # ELA metrics
    ela_va = df['ela_value_added'].dropna()
    ela_raw = df['ela_raw_gain'].dropna()
    
    if len(ela_va) > 0:
        metrics['ela_va_mean'] = ela_va.mean()
        metrics['ela_va_median'] = ela_va.median()
        metrics['ela_va_std'] = ela_va.std()
        metrics['ela_va_positive_pct'] = (ela_va > 0).sum() / len(ela_va) * 100
        metrics['ela_va_n'] = len(ela_va)
        
        # Statistical significance
        if len(ela_va) > 1:
            t_stat, p_value = stats.ttest_1samp(ela_va, 0)
            metrics['ela_va_pvalue'] = p_value
            metrics['ela_va_significant'] = p_value < 0.05
            
            # Standardized effect size (Cohen's d)
            if metrics['ela_va_std'] > 0:
                metrics['ela_va_effect_size'] = metrics['ela_va_mean'] / metrics['ela_va_std']
                # Weeks of learning: ~0.1 SD per month → 1 SD = 10 months; 1 month ≈ 4.3 weeks
                # So 1 SD = 10 * 4.3 = 43 weeks → weeks = effect_size * 43
                metrics['ela_va_weeks_learning'] = metrics['ela_va_effect_size'] * 43.0
    
    if len(ela_raw) > 0:
        metrics['ela_raw_mean'] = ela_raw.mean()
        metrics['ela_raw_positive_pct'] = (ela_raw > 0).sum() / len(ela_raw) * 100
        metrics['ela_raw_n'] = len(ela_raw)
        
        # Standardized effect size for raw gains
        if len(ela_raw) > 1 and ela_raw.std() > 0:
            metrics['ela_raw_effect_size'] = ela_raw.mean() / ela_raw.std()
            metrics['ela_raw_weeks_learning'] = metrics['ela_raw_effect_size'] * 43.0
    
    # Math metrics
    math_va = df['math_value_added'].dropna()
    math_raw = df['math_raw_gain'].dropna()
    
    if len(math_va) > 0:
        metrics['math_va_mean'] = math_va.mean()
        metrics['math_va_median'] = math_va.median()
        metrics['math_va_std'] = math_va.std()
        metrics['math_va_positive_pct'] = (math_va > 0).sum() / len(math_va) * 100
        metrics['math_va_n'] = len(math_va)
        
        # Statistical significance
        if len(math_va) > 1:
            t_stat, p_value = stats.ttest_1samp(math_va, 0)
            metrics['math_va_pvalue'] = p_value
            metrics['math_va_significant'] = p_value < 0.05
            
            # Standardized effect size (Cohen's d)
            if metrics['math_va_std'] > 0:
                metrics['math_va_effect_size'] = metrics['math_va_mean'] / metrics['math_va_std']
                # Weeks of learning: ~0.1 SD per month → 1 SD = 43 weeks (see ELA comment)
                metrics['math_va_weeks_learning'] = metrics['math_va_effect_size'] * 43.0
    
    if len(math_raw) > 0:
        metrics['math_raw_mean'] = math_raw.mean()
        metrics['math_raw_positive_pct'] = (math_raw > 0).sum() / len(math_raw) * 100
        metrics['math_raw_n'] = len(math_raw)
        
        # Standardized effect size for raw gains
        if len(math_raw) > 1 and math_raw.std() > 0:
            metrics['math_raw_effect_size'] = math_raw.mean() / math_raw.std()
            metrics['math_raw_weeks_learning'] = metrics['math_raw_effect_size'] * 43.0
    
    return metrics


def calculate_cost_metrics(
    df: pd.DataFrame,
    total_cost: float,
    target_dosage: float,
    reference_df: Optional[pd.DataFrame] = None,
) -> Dict:
    """Calculate cost-effectiveness metrics."""
    metrics = {}
    analysis_df = get_tutored_students(df)
    n_students = len(analysis_df)
    
    if n_students == 0:
        return metrics

    total_hours = tutoring_hours_series(analysis_df).sum()
    reference_hours = tutoring_hours_series(
        get_tutored_students(reference_df if reference_df is not None else df)
    ).sum()
    allocated_cost = float(total_cost)
    if reference_hours > 0 and total_hours > 0:
        allocated_cost = float(total_cost) * (total_hours / reference_hours)

    metrics['allocated_cost'] = allocated_cost
    metrics['tutored_students'] = n_students
    metrics['students_at_target_dosage'] = int((tutoring_hours_series(analysis_df) >= target_dosage).sum())
    metrics['total_tutoring_hours'] = total_hours
    metrics['cost_allocation_share'] = (total_hours / reference_hours) if reference_hours > 0 else None
    metrics['cost_per_student'] = allocated_cost / n_students if n_students > 0 else 0
    metrics['cost_per_hour'] = allocated_cost / total_hours if total_hours > 0 else 0
    
    # Calculate total value-added points (sum across tutored students)
    ela_va_sum = analysis_df['ela_value_added'].dropna().sum()
    math_va_sum = analysis_df['math_value_added'].dropna().sum()
    total_va_points = ela_va_sum + math_va_sum
    
    # Calculate total raw gain points
    ela_raw_sum = analysis_df['ela_raw_gain'].dropna().sum()
    math_raw_sum = analysis_df['math_raw_gain'].dropna().sum()
    total_raw_points = ela_raw_sum + math_raw_sum
    
    if total_va_points > 0:
        metrics['cost_per_va_point'] = allocated_cost / total_va_points
    else:
        metrics['cost_per_va_point'] = None
    
    if total_raw_points > 0:
        metrics['cost_per_raw_point'] = allocated_cost / total_raw_points
    else:
        metrics['cost_per_raw_point'] = None
    
    return metrics


# ============================================================================
# VISUALIZATION FUNCTIONS
# ============================================================================

def plot_dosage_distribution(df: pd.DataFrame, target_dosage: float):
    """Create dosage distribution visualization."""
    df_viz = get_tutored_students(df)
    hours = tutoring_hours_series(df_viz)

    if len(df_viz) == 0:
        st.warning("No dosage data available for visualization.")
        return
    
    # Create histogram with dosage categories (quartiles)
    df_viz['dosage_category'] = pd.cut(
        hours,
        bins=[0, target_dosage * 0.25, target_dosage * 0.5, target_dosage * 0.75, target_dosage, float('inf')],
        labels=['<25%', '25-50%', '50-75%', '75-99%', '100%+']
    )
    
    fig = px.histogram(
        df_viz,
        x='total_hours',
        color='dosage_category',
        nbins=30,
        labels={'total_hours': 'Tutoring Hours', 'count': 'Number of Students'},
        title='Distribution of Tutoring Hours per Student',
        color_discrete_map={
            '<25%': '#dc3545',
            '25-50%': '#ffc107',
            '50-75%': '#17a2b8',
            '75-99%': '#0d6efd',
            '100%+': '#28a745'
        }
    )
    
    fig.add_vline(
        x=target_dosage,
        line_dash="dash",
        line_color="orange",
        annotation_text=f"Target: {target_dosage} hrs",
        annotation_position="top right"
    )
    
    fig.update_layout(
        showlegend=True,
        legend_title="Dosage Category",
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)


def plot_equity_comparison(df: pd.DataFrame):
    """Create equity comparison visualizations."""
    equity_data = []
    
    # ELL comparison
    if 'ell' in df.columns:
        ell_avg = df[df['ell'] == True]['total_hours'].mean()
        non_ell_avg = df[df['ell'] == False]['total_hours'].mean()
        ell_n = len(df[df['ell'] == True])
        non_ell_n = len(df[df['ell'] == False])
        if not pd.isna(ell_avg) and not pd.isna(non_ell_avg):
            equity_data.append({
                'Group': 'ELL',
                'Subgroup': 'ELL Students',
                'Average Hours': ell_avg,
                'N': ell_n
            })
            equity_data.append({
                'Group': 'ELL',
                'Subgroup': 'Non-ELL Students',
                'Average Hours': non_ell_avg,
                'N': non_ell_n
            })
    
    # IEP comparison
    if 'iep' in df.columns:
        iep_avg = df[df['iep'] == True]['total_hours'].mean()
        non_iep_avg = df[df['iep'] == False]['total_hours'].mean()
        iep_n = len(df[df['iep'] == True])
        non_iep_n = len(df[df['iep'] == False])
        if not pd.isna(iep_avg) and not pd.isna(non_iep_avg):
            equity_data.append({
                'Group': 'IEP',
                'Subgroup': 'IEP Students',
                'Average Hours': iep_avg,
                'N': iep_n
            })
            equity_data.append({
                'Group': 'IEP',
                'Subgroup': 'Non-IEP Students',
                'Average Hours': non_iep_avg,
                'N': non_iep_n
            })
    
    # Economic disadvantage comparison
    if 'economic_disadvantage' in df.columns:
        econ_avg = df[df['economic_disadvantage'] == True]['total_hours'].mean()
        non_econ_avg = df[df['economic_disadvantage'] == False]['total_hours'].mean()
        econ_n = len(df[df['economic_disadvantage'] == True])
        non_econ_n = len(df[df['economic_disadvantage'] == False])
        if not pd.isna(econ_avg) and not pd.isna(non_econ_avg):
            equity_data.append({
                'Group': 'Economic Status',
                'Subgroup': 'Economically Disadvantaged',
                'Average Hours': econ_avg,
                'N': econ_n
            })
            equity_data.append({
                'Group': 'Economic Status',
                'Subgroup': 'Not Economically Disadvantaged',
                'Average Hours': non_econ_avg,
                'N': non_econ_n
            })
    
    if not equity_data:
        st.info("Insufficient data for equity comparison.")
        return
    
    equity_df = pd.DataFrame(equity_data)
    
    fig = px.bar(
        equity_df,
        x='Group',
        y='Average Hours',
        color='Subgroup',
        barmode='group',
        labels={'Average Hours': 'Average Tutoring Hours', 'Group': 'Student Group'},
        title='Average Dosage by Student Subgroup',
        text='N'
    )
    
    fig.update_traces(texttemplate='n=%{text}', textposition='outside')
    fig.update_layout(height=400)
    
    st.plotly_chart(fig, use_container_width=True)


def plot_outcome_distributions(df: pd.DataFrame, subject: str):
    """Plot distribution of outcomes for ELA or Math."""
    va_col = f'{subject.lower()}_value_added'
    raw_col = f'{subject.lower()}_raw_gain'
    
    if va_col not in df.columns or raw_col not in df.columns:
        return
    
    va_data = df[va_col].dropna()
    raw_data = df[raw_col].dropna()
    
    if len(va_data) == 0 and len(raw_data) == 0:
        return
    
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=(f'{subject.upper()} Value-Added Distribution', f'{subject.upper()} Raw Gain Distribution'),
        horizontal_spacing=0.15
    )
    
    if len(va_data) > 0:
        fig.add_trace(
            go.Histogram(x=va_data, name='Value-Added', nbinsx=20, marker_color='#1f77b4'),
            row=1, col=1
        )
        fig.add_vline(x=0, line_dash="dash", line_color="red", row=1, col=1)
        fig.add_vline(x=va_data.mean(), line_dash="dot", line_color="green", row=1, col=1)
    
    if len(raw_data) > 0:
        fig.add_trace(
            go.Histogram(x=raw_data, name='Raw Gain', nbinsx=20, marker_color='#ff7f0e'),
            row=1, col=2
        )
        fig.add_vline(x=0, line_dash="dash", line_color="red", row=1, col=2)
        fig.add_vline(x=raw_data.mean(), line_dash="dot", line_color="green", row=1, col=2)
    
    fig.update_layout(height=400, showlegend=False)
    fig.update_xaxes(title_text="Points", row=1, col=1)
    fig.update_xaxes(title_text="Points", row=1, col=2)
    fig.update_yaxes(title_text="Number of Students", row=1, col=1)
    fig.update_yaxes(title_text="Number of Students", row=1, col=2)
    
    st.plotly_chart(fig, use_container_width=True)


# ============================================================================
# SCHEMA-AWARE OVERRIDES
# ============================================================================

def get_latest_outcome_series(df: pd.DataFrame, subject: str) -> pd.Series:
    latest_column = f"{subject}_latest_outcome"
    if latest_column in df.columns:
        return pd.to_numeric(df[latest_column], errors='coerce')

    measure_fields = [field for field in get_outcome_measure_fields(subject) if field in df.columns]
    if not measure_fields:
        return pd.Series(np.nan, index=df.index)

    latest_values = df[list(reversed(measure_fields))].bfill(axis=1).iloc[:, 0]
    return pd.to_numeric(latest_values, errors='coerce')


def weighted_metric_average(
    metrics: Mapping[str, Any],
    value_weight_pairs: Sequence[Tuple[str, str]],
) -> Optional[float]:
    weighted_sum = 0.0
    total_weight = 0.0

    for value_key, weight_key in value_weight_pairs:
        value = metrics.get(value_key)
        weight = metrics.get(weight_key)
        if value is None or weight is None or pd.isna(value) or pd.isna(weight):
            continue
        weight_value = float(weight)
        if weight_value <= 0:
            continue
        weighted_sum += float(value) * weight_value
        total_weight += weight_value

    if total_weight == 0:
        return None
    return weighted_sum / total_weight


def calculate_equity_metrics(df: pd.DataFrame) -> Dict:
    """Calculate equity gaps in dosage while treating blank subgroup flags as unknown."""
    analysis_df = get_tutored_students(df)
    if analysis_df.empty:
        return {}

    metrics = {}

    if 'ell' in analysis_df.columns:
        ell_hours = tutoring_hours_series(analysis_df[flag_equals(analysis_df, 'ell', True)])
        non_ell_hours = tutoring_hours_series(analysis_df[flag_equals(analysis_df, 'ell', False)])
        if len(ell_hours) > 0 and len(non_ell_hours) > 0:
            metrics['ell_gap'] = ell_hours.mean() - non_ell_hours.mean()
            metrics['ell_ell_mean'] = ell_hours.mean()
            metrics['ell_non_ell_mean'] = non_ell_hours.mean()
            metrics['ell_ell_n'] = len(ell_hours)
            metrics['ell_non_ell_n'] = len(non_ell_hours)

    if 'iep' in analysis_df.columns:
        iep_hours = tutoring_hours_series(analysis_df[flag_equals(analysis_df, 'iep', True)])
        non_iep_hours = tutoring_hours_series(analysis_df[flag_equals(analysis_df, 'iep', False)])
        if len(iep_hours) > 0 and len(non_iep_hours) > 0:
            metrics['iep_gap'] = iep_hours.mean() - non_iep_hours.mean()
            metrics['iep_iep_mean'] = iep_hours.mean()
            metrics['iep_non_iep_mean'] = non_iep_hours.mean()
            metrics['iep_iep_n'] = len(iep_hours)
            metrics['iep_non_iep_n'] = len(non_iep_hours)

    if 'economic_disadvantage' in analysis_df.columns:
        econ_hours = tutoring_hours_series(analysis_df[flag_equals(analysis_df, 'economic_disadvantage', True)])
        non_econ_hours = tutoring_hours_series(analysis_df[flag_equals(analysis_df, 'economic_disadvantage', False)])
        if len(econ_hours) > 0 and len(non_econ_hours) > 0:
            metrics['econ_gap'] = econ_hours.mean() - non_econ_hours.mean()
            metrics['econ_disadv_mean'] = econ_hours.mean()
            metrics['econ_adv_mean'] = non_econ_hours.mean()
            metrics['econ_disadv_n'] = len(econ_hours)
            metrics['econ_adv_n'] = len(non_econ_hours)

    target_dosage = st.session_state.get('full_dosage_threshold', 60.0)
    high_need_mask = (
        flag_equals(analysis_df, 'ell', True) |
        flag_equals(analysis_df, 'iep', True) |
        flag_equals(analysis_df, 'economic_disadvantage', True)
    )
    high_need_students = analysis_df[high_need_mask]
    if len(high_need_students) > 0:
        metrics['high_need_full_dosage_pct'] = (
            (high_need_students['total_hours'] >= target_dosage).sum() / len(high_need_students) * 100
        )
        metrics['high_need_n'] = len(high_need_students)

    total_at_target = (tutoring_hours_series(analysis_df) >= target_dosage).sum()
    metrics['total_full_dosage_pct'] = total_at_target / len(analysis_df) * 100 if len(analysis_df) > 0 else 0
    metrics['total_n'] = len(analysis_df)
    return metrics


def calculate_outcome_metrics(df: pd.DataFrame) -> Dict:
    """Calculate ordered numeric outcome metrics for each supported subject."""
    analysis_df = get_tutored_students(df)
    metrics = {}

    for subject in OUTCOME_SUBJECTS:
        va_key = f'{subject}_value_added'
        raw_key = f'{subject}_raw_gain'

        if va_key in analysis_df.columns:
            va_data = analysis_df[va_key].dropna()
            if len(va_data) > 0:
                metrics[f'{subject}_va_mean'] = va_data.mean()
                metrics[f'{subject}_va_median'] = va_data.median()
                metrics[f'{subject}_va_std'] = va_data.std()
                metrics[f'{subject}_va_positive_pct'] = (va_data > 0).sum() / len(va_data) * 100
                metrics[f'{subject}_va_n'] = len(va_data)
                if len(va_data) > 1:
                    _, p_value = stats.ttest_1samp(va_data, 0)
                    metrics[f'{subject}_va_pvalue'] = p_value
                    metrics[f'{subject}_va_significant'] = p_value < 0.05
                    if metrics[f'{subject}_va_std'] > 0:
                        metrics[f'{subject}_va_effect_size'] = metrics[f'{subject}_va_mean'] / metrics[f'{subject}_va_std']
                        metrics[f'{subject}_va_weeks_learning'] = metrics[f'{subject}_va_effect_size'] * 43.0

        if raw_key in analysis_df.columns:
            raw_data = analysis_df[raw_key].dropna()
            if len(raw_data) > 0:
                metrics[f'{subject}_raw_mean'] = raw_data.mean()
                metrics[f'{subject}_raw_positive_pct'] = (raw_data > 0).sum() / len(raw_data) * 100
                metrics[f'{subject}_raw_n'] = len(raw_data)
                if len(raw_data) > 1 and raw_data.std() > 0:
                    metrics[f'{subject}_raw_effect_size'] = raw_data.mean() / raw_data.std()
                    metrics[f'{subject}_raw_weeks_learning'] = metrics[f'{subject}_raw_effect_size'] * 43.0

    return metrics


def plot_equity_comparison(df: pd.DataFrame):
    """Create equity comparison visualizations without treating missing flags as false."""
    analysis_df = get_tutored_students(df)
    if analysis_df.empty:
        st.info("Insufficient tutored-student data for equity comparison.")
        return

    equity_data = []

    if 'ell' in analysis_df.columns:
        ell_mask = flag_equals(analysis_df, 'ell', True)
        non_ell_mask = flag_equals(analysis_df, 'ell', False)
        ell_avg = analysis_df.loc[ell_mask, 'total_hours'].mean()
        non_ell_avg = analysis_df.loc[non_ell_mask, 'total_hours'].mean()
        ell_n = int(ell_mask.sum())
        non_ell_n = int(non_ell_mask.sum())
        if not pd.isna(ell_avg) and not pd.isna(non_ell_avg):
            equity_data.append({'Group': 'ELL', 'Subgroup': 'ELL Students', 'Average Hours': ell_avg, 'N': ell_n})
            equity_data.append({'Group': 'ELL', 'Subgroup': 'Non-ELL Students', 'Average Hours': non_ell_avg, 'N': non_ell_n})

    if 'iep' in analysis_df.columns:
        iep_mask = flag_equals(analysis_df, 'iep', True)
        non_iep_mask = flag_equals(analysis_df, 'iep', False)
        iep_avg = analysis_df.loc[iep_mask, 'total_hours'].mean()
        non_iep_avg = analysis_df.loc[non_iep_mask, 'total_hours'].mean()
        iep_n = int(iep_mask.sum())
        non_iep_n = int(non_iep_mask.sum())
        if not pd.isna(iep_avg) and not pd.isna(non_iep_avg):
            equity_data.append({'Group': 'IEP', 'Subgroup': 'IEP Students', 'Average Hours': iep_avg, 'N': iep_n})
            equity_data.append({'Group': 'IEP', 'Subgroup': 'Non-IEP Students', 'Average Hours': non_iep_avg, 'N': non_iep_n})

    if 'economic_disadvantage' in analysis_df.columns:
        econ_mask = flag_equals(analysis_df, 'economic_disadvantage', True)
        non_econ_mask = flag_equals(analysis_df, 'economic_disadvantage', False)
        econ_avg = analysis_df.loc[econ_mask, 'total_hours'].mean()
        non_econ_avg = analysis_df.loc[non_econ_mask, 'total_hours'].mean()
        econ_n = int(econ_mask.sum())
        non_econ_n = int(non_econ_mask.sum())
        if not pd.isna(econ_avg) and not pd.isna(non_econ_avg):
            equity_data.append({'Group': 'Economic Status', 'Subgroup': 'Economically Disadvantaged', 'Average Hours': econ_avg, 'N': econ_n})
            equity_data.append({'Group': 'Economic Status', 'Subgroup': 'Not Economically Disadvantaged', 'Average Hours': non_econ_avg, 'N': non_econ_n})

    if not equity_data:
        st.info("Insufficient data for equity comparison.")
        return

    equity_df = pd.DataFrame(equity_data)
    fig = px.bar(
        equity_df,
        x='Group',
        y='Average Hours',
        color='Subgroup',
        barmode='group',
        labels={'Average Hours': 'Average Tutoring Hours', 'Group': 'Student Group'},
        title='Average Dosage by Student Subgroup',
        text='N'
    )
    fig.update_traces(texttemplate='n=%{text}', textposition='outside')
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)


# ============================================================================
# UI HELPER FUNCTIONS
# ============================================================================

def load_example_data():
    """Load bundled example data from the repository so it always matches the current schema."""
    try:
        example_dir = REPO_ROOT / "utils"
        session_path = example_dir / "example_session_dataset.csv"
        student_path = example_dir / "example_student_dataset.csv"

        if not session_path.exists() or not student_path.exists():
            subprocess.run(
                [sys.executable, str(example_dir / "generate_datasets.py")],
                cwd=example_dir,
                check=True,
                capture_output=True,
                text=True,
            )

        _, session_df, _, _ = load_dataset(session_path, 'session')
        _, student_df, _, _ = load_dataset(student_path, 'student')
        return session_df, student_df
    except Exception as e:
        st.error(f"Error loading example data: {str(e)}")
        return None, None


@st.cache_data(show_spinner=False)
def get_prepared_data_cached(session_df: pd.DataFrame, student_df: pd.DataFrame) -> pd.DataFrame:
    return prepare_data(session_df, student_df)


@st.cache_data(show_spinner=False)
def get_module_readiness_cached(
    prepared_df: pd.DataFrame,
    session_df: pd.DataFrame,
    student_df: pd.DataFrame,
) -> pd.DataFrame:
    return build_module_readiness(prepared_df, session_df, student_df)


def initialize_session_state() -> None:
    defaults: Dict[str, Any] = {
        "session_data": None,
        "student_data": None,
        "session_input_data": None,
        "student_input_data": None,
        "session_normalization_report": {},
        "student_normalization_report": {},
        "session_validation_errors": {},
        "student_validation_errors": {},
        "session_validation_warnings": False,
        "student_validation_warnings": False,
        "last_processed_files": None,
        "mapping_profile_payload": None,
        "mapping_profile_name": None,
        "mapping_profile_signature": None,
        "mapping_profile_error": None,
        "full_dosage_threshold": 60.0,
        "total_cost": 0.0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def clear_loaded_data() -> None:
    for key in (
        "session_data",
        "student_data",
        "session_input_data",
        "student_input_data",
        "last_processed_files",
    ):
        st.session_state[key] = None

    for key in (
        "session_normalization_report",
        "student_normalization_report",
        "session_validation_errors",
        "student_validation_errors",
    ):
        st.session_state[key] = {}

    st.session_state["session_validation_warnings"] = False
    st.session_state["student_validation_warnings"] = False


def load_mapping_profile_file(uploaded_file) -> None:
    if uploaded_file is None:
        st.session_state["mapping_profile_payload"] = None
        st.session_state["mapping_profile_name"] = None
        st.session_state["mapping_profile_signature"] = None
        st.session_state["mapping_profile_error"] = None
        return

    try:
        payload = uploaded_file.read()
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        profile = parse_mapping_profile_text(payload)
        st.session_state["mapping_profile_payload"] = profile
        st.session_state["mapping_profile_name"] = uploaded_file.name
        st.session_state["mapping_profile_signature"] = (uploaded_file.name, getattr(uploaded_file, "size", None))
        st.session_state["mapping_profile_error"] = None
    except Exception as exc:
        st.session_state["mapping_profile_payload"] = None
        st.session_state["mapping_profile_name"] = None
        st.session_state["mapping_profile_signature"] = None
        st.session_state["mapping_profile_error"] = str(exc)


def get_loaded_context() -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame]]:
    session_df = st.session_state.get("session_data")
    student_df = st.session_state.get("student_data")
    if session_df is None or student_df is None:
        return None, None
    prepared_df = get_prepared_data_cached(session_df, student_df)
    readiness_df = get_module_readiness_cached(prepared_df, session_df, student_df)
    return prepared_df, readiness_df


def render_compact_filters(df: pd.DataFrame, module: str, prefix: str) -> Dict[str, object]:
    filter_specs = get_filter_specs(df, module)
    defaults: Dict[str, object] = {}
    current_values: Dict[str, object] = {}

    for spec in filter_specs:
        field = str(spec["field"])
        key = f"{prefix}_{field}"
        default = spec["default"]
        defaults[key] = list(default) if isinstance(default, list) else default
        if key not in st.session_state:
            st.session_state[key] = list(default) if isinstance(default, list) else default
        current_values[field] = st.session_state[key]

    active_summary = summarize_active_filters(current_values, filter_specs)
    active_count = active_summary.count(";") + 1 if active_summary else 0

    control_col, clear_col = st.columns([1, 1])
    with control_col:
        with st.popover(f"Filters ({active_count})" if active_count else "Filters"):
            if st.button("Clear all filters", key=f"{prefix}_clear_filters"):
                for key, default in defaults.items():
                    st.session_state[key] = list(default) if isinstance(default, list) else default
                st.rerun()

            for spec in filter_specs:
                field = str(spec["field"])
                label = str(spec["label"])
                kind = str(spec["kind"])
                key = f"{prefix}_{field}"
                options = spec["options"]

                if kind == "single":
                    st.selectbox(label, options, key=key)
                elif kind == "tri_state":
                    st.selectbox(label, options, key=key)
                else:
                    st.multiselect(label, options, key=key)

    with clear_col:
        if active_summary:
            st.caption("Active")

    if active_summary:
        st.caption(f"Active filters: {active_summary}")

    return {str(spec["field"]): st.session_state[f"{prefix}_{spec['field']}"] for spec in filter_specs}


def render_tab_readiness_message(tab_key: str, readiness_df: Optional[pd.DataFrame]) -> None:
    if readiness_df is None:
        return
    status, details = get_tab_readiness_notes(readiness_df, TAB_LABELS[tab_key])
    if not details:
        return
    if status == "Partial":
        st.info("Some sections in this tab are unavailable for the current upload.")
    elif status == "Unavailable":
        st.warning("Most tracked sections in this tab are unavailable for the current upload.")
    with st.expander("What is unavailable in this tab?", expanded=False):
        for detail in details:
            st.markdown(f"- {detail}")


def show_data_quality_warning():
    """Display a warning banner if data has validation issues."""
    has_warnings = (
        st.session_state.get('session_validation_warnings', False) or
        st.session_state.get('student_validation_warnings', False)
    )
    
    if has_warnings:
        st.warning("⚠️ **Data Quality Notice:** Your data loaded with validation warnings. Some results may be affected. Review validation messages in the Upload & Schema tab for details.")


# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    # Header
    st.markdown('<div class="main-header">📊 DATAS Analysis Toolkit</div>', unsafe_allow_html=True)
    st.markdown("---")
    
    # Initialize session state
    initialize_session_state()
    
    # Sidebar for parameters
    with st.sidebar:
        st.header("⚙️ Program Parameters")
        st.session_state['full_dosage_threshold'] = st.number_input(
            "Target Dosage (hours)",
            min_value=0.0,
            value=st.session_state['full_dosage_threshold'],
            step=1.0,
            help="The target number of tutoring hours per student"
        )
        st.session_state['total_cost'] = st.number_input(
            "Total Program Cost ($)",
            min_value=0.0,
            value=st.session_state['total_cost'],
            step=1000.0,
            format="%.2f",
            help="Total program cost for cost-effectiveness calculations"
        )
        st.markdown("---")
        
        # Data status
        st.header("📁 Data Status")
        session_data = st.session_state.get('session_data')
        student_data = st.session_state.get('student_data')
        
        # Check if data is loaded (verify it's not None and is a DataFrame with data)
        data_loaded = (
            session_data is not None and 
            student_data is not None and
            isinstance(session_data, pd.DataFrame) and
            isinstance(student_data, pd.DataFrame) and
            len(session_data) > 0 and
            len(student_data) > 0
        )
        
        if data_loaded:
            # Check for validation warnings
            has_warnings = (
                st.session_state.get('session_validation_warnings', False) or
                st.session_state.get('student_validation_warnings', False)
            )
            
            if has_warnings:
                st.warning("⚠ Data loaded (with warnings)")
            else:
                st.success("✓ Data loaded")
            
            # Display key metrics
            try:
                prepared_status_df = get_prepared_data_cached(session_data, student_data)
                total_students = len(prepared_status_df)
                tutored_status_df = get_tutored_students(prepared_status_df)
                tutored_students = len(tutored_status_df)
                avg_hours = tutoring_hours_series(tutored_status_df).mean() if tutored_students > 0 else 0
                
                st.caption(f"**Total Students:** {total_students:,}")
                st.caption(f"**Tutored Students:** {tutored_students:,}")
                st.caption(f"**Avg Hours/Tutored Student:** {avg_hours:.1f}")
            except Exception:
                st.caption("See the Upload & Schema tab for detailed statistics")
        else:
            st.warning("⚠ Data not loaded")
            st.caption("Load data in the Upload & Schema tab")
    
    prepared_context_df, readiness_df = get_loaded_context()

    # Main tabs
    tab_overview, tab_dosage, tab_equity, tab_outcomes, tab_cost = st.tabs([
        "Upload & Schema",
        "📊 Dosage & Access",
        "⚖️ Equity Analysis",
        "📈 Outcomes",
        "💰 Cost Analytics"
    ])
    
    # ========================================================================
    # DATA OVERVIEW TAB
    # ========================================================================
    with tab_overview:
        st.header("Upload & Schema")
        
        st.caption("Most users can upload a session file and student file. Advanced column-mapping options stay tucked away unless you need them.")

        # Keep the upload path flat and obvious.
        st.markdown("### Upload or Replace Data")
        if st.session_state['session_data'] is not None and st.session_state['student_data'] is not None:
            st.info("💡 **Data already loaded.** Upload new files below to replace the current data, or clear the current session first.")
            if st.button("🗑️ Clear Current Data", type="secondary"):
                clear_loaded_data()
                st.success("Data cleared. Please upload new files.")
                st.rerun()

        supported_types = ['csv', 'xlsx', 'xls', 'json']
        session_file = st.file_uploader("Upload Session Data", type=supported_types, key='session_upload')
        student_file = st.file_uploader("Upload Student Data", type=supported_types, key='student_upload')

        # Keep mapping profiles behind a hidden-on-demand control.
        # Most users should only need the two file uploaders above.
        mapping_label = "Advanced: reuse a saved column mapping"
        if st.session_state.get("mapping_profile_error"):
            mapping_label = "Advanced: reuse a saved column mapping (check error)"
        elif st.session_state.get("mapping_profile_name"):
            mapping_label = "Advanced: reuse a saved column mapping (active)"
        with st.popover(mapping_label):
            st.caption("Most users can ignore this. Use a local mapping profile only for recurring uploads with non-standard headers. The app does not store this file.")
            mapping_profile_file = st.file_uploader(
                "Upload local mapping profile (JSON)",
                type=["json"],
                key="mapping_profile_upload",
                help="Optional. Upload a locally saved DATAS mapping profile to reapply prior column mappings in this session.",
            )
            current_mapping_signature = (
                mapping_profile_file.name,
                getattr(mapping_profile_file, "size", None),
            ) if mapping_profile_file is not None else None
            if current_mapping_signature != st.session_state.get("mapping_profile_signature"):
                load_mapping_profile_file(mapping_profile_file)
            elif mapping_profile_file is None and st.session_state.get("mapping_profile_signature") is not None:
                load_mapping_profile_file(None)

            if st.session_state.get("mapping_profile_error"):
                st.error(f"Mapping profile error: {st.session_state['mapping_profile_error']}")
            elif st.session_state.get("mapping_profile_name"):
                st.success(f"Using local mapping profile: {st.session_state['mapping_profile_name']}")
        
        if session_file and student_file:
            # Check if we've already processed these files (prevent infinite loop)
            profile_signature = json.dumps(st.session_state.get("mapping_profile_payload") or {}, sort_keys=True)
            current_file_ids = (
                session_file.name,
                student_file.name,
                session_file.size,
                student_file.size,
                profile_signature,
            )
            last_processed = st.session_state.get('last_processed_files', None)
            
            if current_file_ids != last_processed:
                try:
                    session_custom_map = get_profile_column_map(st.session_state.get("mapping_profile_payload"), "session")
                    student_custom_map = get_profile_column_map(st.session_state.get("mapping_profile_payload"), "student")

                    # Load data with schema-aware normalization and optional local profile mappings
                    session_input_df, session_df, session_errors, session_report = load_dataset(
                        session_file,
                        'session',
                        custom_column_map=session_custom_map,
                    )
                    student_input_df, student_df, student_errors, student_report = load_dataset(
                        student_file,
                        'student',
                        custom_column_map=student_custom_map,
                    )
                    
                    # Validate data
                    st.markdown("### 🔍 Validating Data...")
                    
                    # Store validation errors in session state for persistent display
                    st.session_state['session_validation_errors'] = session_errors
                    st.session_state['student_validation_errors'] = student_errors
                    st.session_state['session_validation_warnings'] = len(session_errors.get('warnings', [])) > 0 or len(session_errors.get('critical', [])) > 0
                    st.session_state['student_validation_warnings'] = len(student_errors.get('warnings', [])) > 0 or len(student_errors.get('critical', [])) > 0
                    st.session_state['session_input_data'] = session_input_df
                    st.session_state['student_input_data'] = student_input_df
                    st.session_state['session_normalization_report'] = session_report
                    st.session_state['student_normalization_report'] = student_report
                    
                    # Display validation results (but don't block)
                    session_has_issues = display_validation_errors(session_errors, 'Session')
                    student_has_issues = display_validation_errors(student_errors, 'Student')
                    
                    # Always load data, even with errors
                    st.session_state['session_data'] = session_df
                    st.session_state['student_data'] = student_df
                    
                    # Mark these files as processed
                    st.session_state['last_processed_files'] = current_file_ids
                    
                    if session_has_issues or student_has_issues:
                        st.warning("⚠️ **Data loaded with validation issues.** Analysis will proceed, but some results may be affected. Please review the validation messages above.")
                    else:
                        st.success("✅ **Data loaded and validated successfully!**")
                        st.balloons()
                    
                    st.rerun()
                except pd.errors.EmptyDataError:
                    st.error("❌ **Error:** One or both files are empty. Please check your CSV files.")
                except pd.errors.ParserError as e:
                    st.error(f"❌ **Error parsing CSV:** {str(e)}\n\nPlease check that your files are valid CSV format.")
                except Exception as e:
                    st.error(f"❌ **Error loading data:** {str(e)}\n\nPlease check your file format and try again.")
        
        # Load Example Data button (below upload section)
        if st.button("Load Example Data", type="secondary", use_container_width=True):
            with st.spinner("Loading example data..."):
                session_df, student_df = load_example_data()
                if session_df is not None and student_df is not None:
                    # Validate and load
                    session_errors = validate_data_comprehensive(session_df, 'session')
                    student_errors = validate_data_comprehensive(student_df, 'student')
                    
                    # Store validation errors in session state for persistent display
                    st.session_state['session_validation_errors'] = session_errors
                    st.session_state['student_validation_errors'] = student_errors
                    st.session_state['session_validation_warnings'] = len(session_errors.get('warnings', [])) > 0 or len(session_errors.get('critical', [])) > 0
                    st.session_state['student_validation_warnings'] = len(student_errors.get('warnings', [])) > 0 or len(student_errors.get('critical', [])) > 0
                    
                    display_validation_errors(session_errors, 'Session')
                    display_validation_errors(student_errors, 'Student')
                    
                    st.session_state['session_input_data'] = session_df.copy()
                    st.session_state['student_input_data'] = student_df.copy()
                    st.session_state['session_normalization_report'] = {}
                    st.session_state['student_normalization_report'] = {}
                    st.session_state['session_data'] = session_df
                    st.session_state['student_data'] = student_df
                    
                    st.success("✅ **Example data loaded successfully!**")
                    st.rerun()
                else:
                    st.error("❌ Failed to load example data. Please try again or load files manually.")
        
        if st.session_state['session_data'] is None or st.session_state['student_data'] is None:
            st.info("""
            **Data Loading Instructions:**
            
            Please upload your session and student data files using the uploader above, or use the example data button.
            
            Once uploaded, the data will be available for analysis across all tabs.
            """)
        else:
            show_data_quality_warning()
            
            # Prepare data
            try:
                prepared_df = prepared_context_df if prepared_context_df is not None else get_prepared_data_cached(
                    st.session_state['session_data'],
                    st.session_state['student_data']
                )
            except Exception as e:
                st.error(f"❌ **Error preparing data for analysis:** {str(e)}")
                st.info("This error may be due to data quality issues. Please review your data files and try again.")
                st.stop()

            normalization_summary = pd.concat(
                [
                    build_normalization_summary_rows(
                        "session",
                        st.session_state.get("session_input_data"),
                        st.session_state.get("session_data"),
                        st.session_state.get("session_normalization_report"),
                        st.session_state.get("session_validation_errors"),
                    ),
                    build_normalization_summary_rows(
                        "student",
                        st.session_state.get("student_input_data"),
                        st.session_state.get("student_data"),
                        st.session_state.get("student_normalization_report"),
                        st.session_state.get("student_validation_errors"),
                    ),
                ],
                ignore_index=True,
            )
            normalization_details = pd.concat(
                [
                    build_normalization_detail_rows("session", st.session_state.get("session_normalization_report")),
                    build_normalization_detail_rows("student", st.session_state.get("student_normalization_report")),
                ],
                ignore_index=True,
            )
            readiness_summary = pd.DataFrame()
            if readiness_df is not None and not readiness_df.empty:
                readiness_summary = readiness_df[readiness_df["section"] == "Tab summary"].copy()

            # Summary statistics
            st.markdown("### Program Overview")
            tutored_overview_df = get_tutored_students(prepared_df)
            tutored_students = len(tutored_overview_df)
            total_hours = tutoring_hours_series(tutored_overview_df).sum()
            avg_hours = tutoring_hours_series(tutored_overview_df).mean() if tutored_students > 0 else 0.0
            schools_served = tutored_overview_df['school_name'].nunique() if 'school_name' in tutored_overview_df.columns else 0
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Students Tutored", f"{tutored_students:,}")
            
            with col2:
                st.metric("Total Tutoring Hours", f"{total_hours:,.0f}")
            
            with col3:
                st.metric("Average Hours/Tutored Student", f"{avg_hours:.1f}")
            
            with col4:
                st.metric("Schools Served", f"{schools_served}")

            st.caption(
                f"Student roster in upload: **{len(prepared_df):,}** students. "
                f"Intervention sample used for tutoring summaries: **{tutored_students:,}** students."
            )

            st.markdown("---")
            
            # Session Records Statistics
            st.markdown("### Session Records")
            try:
                session_df = st.session_state['session_data']
                session_col1, session_col2, session_col3, session_col4 = st.columns(4)
                
                with session_col1:
                    st.metric("Total Sessions", f"{len(session_df):,}")
                
                with session_col2:
                    if 'session_topic' in session_df.columns:
                        try:
                            math_sessions = len(session_df[session_df['session_topic'].astype(str).str.lower() == 'math'])
                            ela_sessions = len(session_df[session_df['session_topic'].astype(str).str.lower() == 'ela'])
                            st.metric("Math Sessions", f"{math_sessions:,}")
                        except:
                            st.metric("Math Sessions", "N/A")
                    else:
                        st.metric("Math Sessions", "N/A")
                
                with session_col3:
                    if 'session_topic' in session_df.columns:
                        try:
                            ela_sessions = len(session_df[session_df['session_topic'].astype(str).str.lower() == 'ela'])
                            st.metric("ELA Sessions", f"{ela_sessions:,}")
                        except:
                            st.metric("ELA Sessions", "N/A")
                    else:
                        st.metric("ELA Sessions", "N/A")
                
                with session_col4:
                    if 'tutor_id' in session_df.columns:
                        try:
                            unique_tutors = session_df['tutor_id'].nunique()
                            st.metric("Unique Tutors", f"{unique_tutors:,}")
                        except:
                            st.metric("Unique Tutors", "N/A")
                    else:
                        st.metric("Unique Tutors", "N/A")
                
                if 'session_date' in session_df.columns:
                    try:
                        session_dates = pd.to_datetime(session_df['session_date'], errors='coerce')
                        valid_dates = session_dates.dropna()
                        if len(valid_dates) > 0:
                            date_range = f"{valid_dates.min().strftime('%Y-%m-%d')} to {valid_dates.max().strftime('%Y-%m-%d')}"
                            st.caption(f"**Date Range:** {date_range}")
                        avg_session_minutes = pd.to_numeric(session_df.get('session_duration'), errors='coerce').mean()
                        if not pd.isna(avg_session_minutes):
                            st.caption(f"**Average Session Duration:** {avg_session_minutes:.1f} minutes")
                    except:
                        pass
            except Exception:
                st.warning("Session statistics unavailable")
            
            st.markdown("---")
            
            # Student Records Statistics
            st.markdown("### Student Records")
            try:
                student_df = st.session_state['student_data']
                student_col1, student_col2, student_col3, student_col4 = st.columns(4)
                
                with student_col1:
                    st.metric("Total Students", f"{len(student_df):,}")
                
                with student_col2:
                    st.metric("Students Tutored", f"{tutored_students:,}")
                
                with student_col3:
                    if 'school_name' in student_df.columns:
                        try:
                            schools = student_df['school_name'].nunique()
                            st.metric("Schools", f"{schools:,}")
                        except:
                            st.metric("Schools", "N/A")
                    else:
                        st.metric("Schools", "N/A")
                
                with student_col4:
                    if 'district_name' in student_df.columns:
                        try:
                            districts = student_df['district_name'].nunique()
                            st.metric("Districts", f"{districts:,}")
                        except:
                            if 'district_id' in student_df.columns:
                                try:
                                    districts = student_df['district_id'].nunique()
                                    st.metric("Districts", f"{districts:,}")
                                except:
                                    st.metric("Districts", "N/A")
                            else:
                                st.metric("Districts", "N/A")
                    elif 'district_id' in student_df.columns:
                        try:
                            districts = student_df['district_id'].nunique()
                            st.metric("Districts", f"{districts:,}")
                        except:
                            st.metric("Districts", "N/A")
                    else:
                        st.metric("Districts", "N/A")
                
                if 'current_grade_level' in student_df.columns:
                    try:
                        grades = sorted(student_df['current_grade_level'].dropna().unique().tolist())
                        st.caption(f"**Grade Levels:** {len(grades)}")
                    except:
                        pass
            except Exception:
                st.warning("Student statistics unavailable")
            
            st.markdown("---")

            st.markdown("### Upload Support & Normalization")
            if not readiness_summary.empty:
                st.markdown("#### What This Upload Supports")
                st.dataframe(readiness_summary, use_container_width=True, hide_index=True)
            if readiness_df is not None and not readiness_df.empty:
                with st.expander("Section-by-section availability", expanded=False):
                    st.dataframe(
                        readiness_df[readiness_df["section"] != "Tab summary"],
                        use_container_width=True,
                        hide_index=True,
                    )

            st.markdown("#### Normalization Summary")
            st.dataframe(normalization_summary, use_container_width=True, hide_index=True)

            if not normalization_details.empty:
                with st.expander("Column normalization details", expanded=False):
                    st.dataframe(normalization_details, use_container_width=True, hide_index=True)

            # Display validation errors if they exist
            session_errors = st.session_state.get('session_validation_errors', {})
            student_errors = st.session_state.get('student_validation_errors', {})
            
            has_session_issues = len(session_errors.get('critical', [])) > 0 or len(session_errors.get('warnings', [])) > 0
            has_student_issues = len(student_errors.get('critical', [])) > 0 or len(student_errors.get('warnings', [])) > 0
            
            if has_session_issues or has_student_issues:
                st.markdown("### 🔍 Data Validation Results")
                if has_session_issues:
                    display_validation_errors(session_errors, 'Session')
                if has_student_issues:
                    display_validation_errors(student_errors, 'Student')
                st.markdown("---")
            
            # Data preview
            with st.expander("📊 Data Preview", expanded=False):
                st.subheader("Student Data Sample")
                st.caption("Sample rows from the merged student roster, including students with zero recorded tutoring hours.")
                st.dataframe(prepared_df.head(10), use_container_width=True)
                
                st.subheader("Data Summary")
                preview_summary_df = get_tutored_students(prepared_df)
                if preview_summary_df.empty:
                    preview_summary_df = prepared_df
                st.caption("Numeric summary below is based on the tutored-student analysis sample when available.")
                st.dataframe(preview_summary_df.describe(), use_container_width=True)
    
    # ========================================================================
    # DOSAGE & ACCESS TAB
    # ========================================================================
    with tab_dosage:
        if st.session_state['session_data'] is None or st.session_state['student_data'] is None:
            st.warning("Please load data in the Upload & Schema tab first.")
        else:
            show_data_quality_warning()
            st.header("Dosage & Access Analysis")
            st.caption("Understanding how much tutoring participating students are receiving")
            render_tab_readiness_message("dosage", readiness_df)
            
            # Prepare data
            prepared_df = prepared_context_df if prepared_context_df is not None else get_prepared_data_cached(
                st.session_state['session_data'],
                st.session_state['student_data']
            )
            
            filters = render_compact_filters(prepared_df, "dosage", "dosage_filter")
            filtered_df = apply_filter_values(prepared_df, filters)
            dosage_population = summarize_analysis_population(filtered_df)
            dosage_df = dosage_population['analysis_df']
            
            if dosage_population['matched_students'] == 0:
                st.warning("No students match the selected filters.")
            elif dosage_population['tutored_students'] == 0:
                st.warning("Students match the selected filters, but none of them received tutoring in the uploaded session data.")
            else:
                st.info(
                    f"📊 Matched **{dosage_population['matched_students']:,} students**; "
                    f"**{dosage_population['tutored_students']:,}** received tutoring "
                    f"({dosage_population['pct_tutored']:.1f}%) and are included in dosage calculations."
                )
                # Calculate metrics
                dosage_metrics = calculate_dosage_metrics(
                    dosage_df,
                    st.session_state['full_dosage_threshold']
                )

                # Visualization at the top
                st.markdown("### Distribution of Tutoring Hours")
                st.caption("**What to look for:** This distribution includes only students who received tutoring. A right-skewed pattern suggests most tutored students receive below-target dosage.")
                plot_dosage_distribution(dosage_df, st.session_state['full_dosage_threshold'])
                
                st.markdown("---")
                
                # School and Subject Distribution Table
                st.markdown("### Dosage Distribution by School and Subject")
                try:
                    # Merge session data to get subject info
                    session_df = st.session_state['session_data'].copy()
                    session_df['student_id'] = session_df['student_id'].astype(str).str.strip()
                    session_df['session_duration_hours'] = pd.to_numeric(session_df.get('session_duration', 0), errors='coerce') / 60
                    
                    # Calculate hours per student per subject
                    if 'session_topic' in session_df.columns:
                        # Calculate total hours per student per subject
                        hours_per_student_subject = session_df.groupby(['student_id', 'session_topic'])['session_duration_hours'].sum().reset_index()
                        hours_per_student_subject.columns = ['student_id', 'subject', 'subject_hours']
                        
                        # Pivot to get ELA and Math hours separately
                        hours_pivot = hours_per_student_subject.pivot_table(
                            index='student_id',
                            columns='subject',
                            values='subject_hours',
                            fill_value=0
                        ).reset_index()
                        
                        # Rename columns to handle case variations
                        hours_pivot.columns = [col.lower() if col != 'student_id' else col for col in hours_pivot.columns]
                        
                        # Merge with student data
                        student_with_subject_hours = filtered_df.merge(hours_pivot, on='student_id', how='left')
                        
                        # Fill NaN with 0 for subjects
                        for col in ['ela', 'math']:
                            if col in student_with_subject_hours.columns:
                                student_with_subject_hours[col] = student_with_subject_hours[col].fillna(0)
                        
                        # Create distribution table by school
                        if 'school_name' in student_with_subject_hours.columns:
                            school_dist = []
                            for school in student_with_subject_hours['school_name'].dropna().unique():
                                school_data = student_with_subject_hours[student_with_subject_hours['school_name'] == school]
                                total = len(school_data)
                                if total > 0:
                                    # Calculate % of students who received tutoring
                                    tutored_count = (school_data['total_hours'] > 0).sum()
                                    pct_tutored = (tutored_count / total) * 100
                                    
                                    # Filter to only students who received tutoring for dosage calculations
                                    tutored_data = school_data[school_data['total_hours'] > 0]
                                    tutored_total = len(tutored_data)
                                    
                                    if tutored_total > 0:
                                        below_25 = (tutored_data['total_hours'] < st.session_state['full_dosage_threshold'] * 0.25).sum() / tutored_total * 100
                                        pct_25_50 = ((tutored_data['total_hours'] >= st.session_state['full_dosage_threshold'] * 0.25) & 
                                                    (tutored_data['total_hours'] < st.session_state['full_dosage_threshold'] * 0.5)).sum() / tutored_total * 100
                                        pct_50_75 = ((tutored_data['total_hours'] >= st.session_state['full_dosage_threshold'] * 0.5) & 
                                                    (tutored_data['total_hours'] < st.session_state['full_dosage_threshold'] * 0.75)).sum() / tutored_total * 100
                                        pct_75_99 = ((tutored_data['total_hours'] >= st.session_state['full_dosage_threshold'] * 0.75) & 
                                                    (tutored_data['total_hours'] < st.session_state['full_dosage_threshold'])).sum() / tutored_total * 100
                                        full_dosage = (tutored_data['total_hours'] >= st.session_state['full_dosage_threshold']).sum() / tutored_total * 100
                                    else:
                                        below_25 = pct_25_50 = pct_50_75 = pct_75_99 = full_dosage = 0.0
                                    
                                    school_dist.append({
                                        'School': school,
                                        '< 25%': f"{below_25:.1f}%",
                                        '25-50%': f"{pct_25_50:.1f}%",
                                        '50-75%': f"{pct_50_75:.1f}%",
                                        '75-99%': f"{pct_75_99:.1f}%",
                                        '100%+': f"{full_dosage:.1f}%",
                                        'Total Students': total,
                                        'Students Tutored': f"{tutored_count} ({pct_tutored:.1f}%)",
                                        '_sort_key': full_dosage  # For sorting
                                    })
                            
                            if school_dist:
                                school_df = pd.DataFrame(school_dist)
                                # Sort by full dosage percentage (highest to lowest)
                                school_df = school_df.sort_values('_sort_key', ascending=False)
                                # Remove sort key before displaying
                                school_df = school_df.drop(columns=['_sort_key'])
                                st.dataframe(school_df, use_container_width=True, hide_index=True)
                        
                        # Subject distribution
                        subject_dist = []
                        total_all_students = len(student_with_subject_hours)
                        
                        for subject in ['ela', 'math']:
                            if subject in student_with_subject_hours.columns:
                                subject_col = subject
                                subject_name = subject.upper()
                            else:
                                # Try to find case-insensitive match
                                matching_cols = [col for col in student_with_subject_hours.columns if col.lower() == subject]
                                if matching_cols:
                                    subject_col = matching_cols[0]
                                    subject_name = subject_col.upper()
                                else:
                                    continue
                            
                            # Calculate % of all students who received tutoring in this subject
                            tutored_in_subject = (student_with_subject_hours[subject_col] > 0).sum()
                            pct_tutored = (tutored_in_subject / total_all_students) * 100 if total_all_students > 0 else 0
                            
                            # Filter to only students who received tutoring in this subject for dosage calculations
                            subject_data = student_with_subject_hours[student_with_subject_hours[subject_col] > 0]
                            tutored_total = len(subject_data)
                            
                            if tutored_total > 0:
                                below_25 = (subject_data[subject_col] < st.session_state['full_dosage_threshold'] * 0.25).sum() / tutored_total * 100
                                pct_25_50 = ((subject_data[subject_col] >= st.session_state['full_dosage_threshold'] * 0.25) & 
                                            (subject_data[subject_col] < st.session_state['full_dosage_threshold'] * 0.5)).sum() / tutored_total * 100
                                pct_50_75 = ((subject_data[subject_col] >= st.session_state['full_dosage_threshold'] * 0.5) & 
                                            (subject_data[subject_col] < st.session_state['full_dosage_threshold'] * 0.75)).sum() / tutored_total * 100
                                pct_75_99 = ((subject_data[subject_col] >= st.session_state['full_dosage_threshold'] * 0.75) & 
                                            (subject_data[subject_col] < st.session_state['full_dosage_threshold'])).sum() / tutored_total * 100
                                full_dosage = (subject_data[subject_col] >= st.session_state['full_dosage_threshold']).sum() / tutored_total * 100
                            else:
                                below_25 = pct_25_50 = pct_50_75 = pct_75_99 = full_dosage = 0.0
                            
                            subject_dist.append({
                                'Subject': subject_name,
                                '< 25%': f"{below_25:.1f}%",
                                '25-50%': f"{pct_25_50:.1f}%",
                                '50-75%': f"{pct_50_75:.1f}%",
                                '75-99%': f"{pct_75_99:.1f}%",
                                '100%+': f"{full_dosage:.1f}%",
                                'Total Students': total_all_students,
                                'Students Tutored': f"{tutored_in_subject} ({pct_tutored:.1f}%)",
                                '_sort_key': full_dosage  # For sorting
                            })
                        
                        if subject_dist:
                            st.markdown("#### By Subject")
                            subject_df = pd.DataFrame(subject_dist)
                            # Sort by full dosage percentage (highest to lowest)
                            subject_df = subject_df.sort_values('_sort_key', ascending=False)
                            # Remove sort key before displaying
                            subject_df = subject_df.drop(columns=['_sort_key'])
                            st.dataframe(subject_df, use_container_width=True, hide_index=True)
                    else:
                        st.info("Subject distribution requires 'session_topic' column in session data.")
                except Exception as e:
                    st.info(f"School and subject distribution table unavailable. Check that required columns are present. Error: {str(e)}")
                
                st.markdown("---")
                
                # Time-based chart (by time of day)
                st.markdown("### Implementation Fidelity by Time of Day")
                try:
                    session_df = st.session_state['session_data'].copy()
                    if 'session_date' in session_df.columns and 'session_duration' in session_df.columns:
                        # Try to extract time if available, otherwise use session_date as proxy
                        session_df['session_date'] = pd.to_datetime(session_df['session_date'], errors='coerce')
                        session_df = session_df.dropna(subset=['session_date'])
                        session_df['hour'] = session_df['session_date'].dt.hour
                        session_df['session_duration_hours'] = pd.to_numeric(session_df['session_duration'], errors='coerce') / 60
                        
                        # Group by hour and calculate total tutoring hours and session count
                        hourly_data = session_df.groupby('hour').agg({
                            'session_duration_hours': 'sum',
                            'student_id': 'count'
                        }).reset_index()
                        hourly_data.columns = ['Hour of Day', 'Total Hours', 'Session Count']
                        
                        if len(hourly_data) > 0:
                            fig = px.bar(
                                hourly_data,
                                x='Hour of Day',
                                y='Total Hours',
                                title='Total Tutoring Hours by Hour of Day',
                                labels={'Total Hours': 'Total Tutoring Hours', 'Hour of Day': 'Hour of Day (0-23)'},
                                text='Session Count'
                            )
                            fig.update_traces(texttemplate='%{text} sessions', textposition='outside')
                            fig.update_layout(height=400)
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.info("Time-based data not available. Session dates may not include time information.")
                    else:
                        st.info("Time-based analysis requires session_date column.")
                except Exception:
                    st.info("Time-based chart unavailable.")
                
                st.markdown("---")
                
                # Date-based chart (implementation fidelity over time)
                st.markdown("### Implementation Fidelity Over Time")
                try:
                    session_df = st.session_state['session_data'].copy()
                    if 'session_date' in session_df.columns and 'session_duration' in session_df.columns:
                        session_df['session_date'] = pd.to_datetime(session_df['session_date'], errors='coerce')
                        session_df = session_df.dropna(subset=['session_date'])
                        session_df['session_duration_hours'] = pd.to_numeric(session_df['session_duration'], errors='coerce') / 60
                        session_df['date'] = session_df['session_date'].dt.date
                        
                        # Group by date and calculate metrics
                        daily_data = session_df.groupby('date').agg({
                            'session_duration_hours': ['mean', 'sum', 'count'],
                            'student_id': 'nunique'
                        }).reset_index()
                        daily_data.columns = ['Date', 'Avg Duration', 'Total Hours', 'Session Count', 'Unique Students']
                        
                        if len(daily_data) > 0:
                            # Convert Date to datetime for proper sorting and rolling calculation
                            daily_data['Date'] = pd.to_datetime(daily_data['Date'])
                            daily_data = daily_data.sort_values('Date')
                            
                            # Calculate 7-day rolling average
                            daily_data['7-Day Rolling Avg'] = daily_data['Avg Duration'].rolling(window=7, min_periods=1).mean()
                            
                            # Create figure with both daily average and rolling average
                            fig = go.Figure()
                            
                            # Add daily average line (very subtle, background-like)
                            fig.add_trace(go.Scatter(
                                x=daily_data['Date'],
                                y=daily_data['Avg Duration'],
                                mode='lines',
                                name='Daily Average',
                                line=dict(color='lightgray', width=0.5, dash='dot'),
                                opacity=0.3,
                                showlegend=False,
                                hoverinfo='skip'
                            ))
                            
                            # Add 7-day rolling average line (hero, prominent)
                            fig.add_trace(go.Scatter(
                                x=daily_data['Date'],
                                y=daily_data['7-Day Rolling Avg'],
                                mode='lines',
                                name='7-Day Rolling Average',
                                line=dict(color='#1f77b4', width=3),
                                hovertemplate='<b>7-Day Rolling Average</b><br>Date: %{x}<br>Duration: %{y:.2f} hours<extra></extra>'
                            ))
                            
                            fig.update_layout(
                                title='Average Session Duration Over Time',
                                xaxis_title='Date',
                                yaxis_title='Average Duration (hours)',
                                height=400,
                                hovermode='x unified'
                            )
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.info("Date-based data not available.")
                    else:
                        st.info("Date-based analysis requires session_date column.")
                except Exception:
                    st.info("Date-based chart unavailable.")
    
    # ========================================================================
    # EQUITY ANALYSIS TAB
    # ========================================================================
    with tab_equity:
        if st.session_state['session_data'] is None or st.session_state['student_data'] is None:
            st.warning("Please load data in the Upload & Schema tab first.")
        else:
            show_data_quality_warning()
            st.header("Equity Analysis")
            st.caption("Examining dosage gaps across tutored student subgroups")
            render_tab_readiness_message("equity", readiness_df)
            
            # Prepare data
            prepared_df = prepared_context_df if prepared_context_df is not None else get_prepared_data_cached(
                st.session_state['session_data'],
                st.session_state['student_data']
            )
            
            filters = render_compact_filters(prepared_df, "equity", "equity_filter")
            filtered_equity_df = apply_filter_values(prepared_df, filters)
            equity_population = summarize_analysis_population(filtered_equity_df)
            equity_df = equity_population['analysis_df']
            
            if equity_population['matched_students'] == 0:
                st.warning("No students match the selected filters.")
            elif equity_population['tutored_students'] == 0:
                st.warning("Students match the selected filters, but none of them received tutoring in the uploaded session data.")
            else:
                st.info(
                    f"📊 Matched **{equity_population['matched_students']:,} students**; "
                    f"**{equity_population['tutored_students']:,}** received tutoring "
                    f"({equity_population['pct_tutored']:.1f}%) and are included in equity calculations."
                )
                # Calculate equity metrics
                equity_metrics = calculate_equity_metrics(equity_df)

                unknown_notes = build_unknown_denominator_notes(
                    equity_df,
                    {
                        "ell": "ELL",
                        "iep": "IEP",
                        "economic_disadvantage": "Economic disadvantage",
                    },
                )
                if unknown_notes:
                    st.caption("Unknown subgroup values remain in the overall population but are excluded from subgroup-specific gap calculations.")
                    for note in unknown_notes:
                        st.caption(note)
                
                # Equity gaps
                st.markdown("### Equity Gaps in Dosage")
                st.caption("Positive gaps indicate disadvantaged groups receive more tutoring hours among tutored students. Negative gaps indicate they receive fewer hours.")
                
                gap_col1, gap_col2, gap_col3 = st.columns(3)
                
                if 'ell_gap' in equity_metrics:
                    with gap_col1:
                        gap = equity_metrics['ell_gap']
                        ell_mean = equity_metrics.get('ell_ell_mean', 0)
                        non_ell_mean = equity_metrics.get('ell_non_ell_mean', 0)
                        st.metric(
                            "ELL Gap",
                            f"{gap:+.1f} hours",
                            help=build_metric_help(
                                [
                                    "Gap_ELL = mean(Hours | ELL = Yes) - mean(Hours | ELL = No)",
                                ],
                                f"ELL students average {ell_mean:.1f} hours versus {non_ell_mean:.1f} hours for non-ELL students in the current tutored sample.",
                                ["Positive values mean ELL students received more tutoring hours in this view."],
                            )
                        )
                        if equity_metrics.get('ell_ell_n', 0) < 30 or equity_metrics.get('ell_non_ell_n', 0) < 30:
                            st.caption("⚠️ Small sample size")
                
                if 'iep_gap' in equity_metrics:
                    with gap_col2:
                        gap = equity_metrics['iep_gap']
                        iep_mean = equity_metrics.get('iep_iep_mean', 0)
                        non_iep_mean = equity_metrics.get('iep_non_iep_mean', 0)
                        st.metric(
                            "IEP Gap",
                            f"{gap:+.1f} hours",
                            help=build_metric_help(
                                [
                                    "Gap_IEP = mean(Hours | IEP = Yes) - mean(Hours | IEP = No)",
                                ],
                                f"Students with IEPs average {iep_mean:.1f} hours versus {non_iep_mean:.1f} hours for students without IEPs in the current tutored sample.",
                                ["Positive values mean students with IEPs received more tutoring hours in this view."],
                            )
                        )
                        if equity_metrics.get('iep_iep_n', 0) < 30 or equity_metrics.get('iep_non_iep_n', 0) < 30:
                            st.caption("⚠️ Small sample size")
                
                if 'econ_gap' in equity_metrics:
                    with gap_col3:
                        gap = equity_metrics['econ_gap']
                        econ_disadv_mean = equity_metrics.get('econ_disadv_mean', 0)
                        econ_adv_mean = equity_metrics.get('econ_adv_mean', 0)
                        st.metric(
                            "Economic Gap",
                            f"{gap:+.1f} hours",
                            help=build_metric_help(
                                [
                                    "Gap_Econ = mean(Hours | Econ = Yes) - mean(Hours | Econ = No)",
                                ],
                                f"Economically disadvantaged students average {econ_disadv_mean:.1f} hours versus {econ_adv_mean:.1f} hours for other tutored students in the current view.",
                                ["Positive values mean economically disadvantaged students received more tutoring hours in this view."],
                            )
                        )
                        if equity_metrics.get('econ_disadv_n', 0) < 30 or equity_metrics.get('econ_adv_n', 0) < 30:
                            st.caption("⚠️ Small sample size")
                
                st.markdown("---")
                
                # High-need vs total students reaching target dosage
                if 'high_need_full_dosage_pct' in equity_metrics:
                    st.markdown("### Students Reaching Target Dosage")
                    high_need_pct = equity_metrics['high_need_full_dosage_pct']
                    high_need_n = equity_metrics.get('high_need_n', 0)
                    total_pct = equity_metrics.get('total_full_dosage_pct', 0)
                    total_n = equity_metrics.get('total_n', 0)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric(
                            "High-need students at target dosage",
                            f"{high_need_pct:.1f}%",
                            delta=f"{int(high_need_pct * high_need_n / 100)} of {high_need_n} students",
                            help=build_metric_help(
                                [
                                    "HighNeed = ELL OR IEP OR EconomicDisadvantage",
                                    "% at Target = count(Hours >= Target) / n_high_need",
                                ],
                                "A student is counted as high-need if any of those three subgroup flags are marked yes in the uploaded student file.",
                            )
                        )
                        if high_need_n < 30:
                            st.caption("⚠️ Small sample size")
                    with col2:
                        st.metric(
                            "Total students at target dosage",
                            f"{total_pct:.1f}%",
                            delta=f"{int(total_pct * total_n / 100)} of {total_n} students",
                            help=build_metric_help(
                                [
                                    "% at Target = count(Hours >= Target) / n_tutored",
                                ],
                                "This percentage is calculated over tutored students in the current filtered view.",
                            )
                        )
                
                st.markdown("---")
                
                # Ethnicity analysis
                if 'ethnicity' in equity_df.columns:
                    st.markdown("### Dosage by Ethnicity")
                    try:
                        ethnicity_data = []
                        for ethnicity in equity_df['ethnicity'].dropna().unique():
                            eth_data = equity_df[equity_df['ethnicity'] == ethnicity]
                            if len(eth_data) > 0:
                                avg_hours = eth_data['total_hours'].mean()
                                median_hours = eth_data['total_hours'].median()
                                full_dosage_pct = (eth_data['total_hours'] >= st.session_state['full_dosage_threshold']).sum() / len(eth_data) * 100
                                ethnicity_data.append({
                                    'Ethnicity': ethnicity,
                                    'Avg Hours': f"{avg_hours:.1f}",
                                    'Median Hours': f"{median_hours:.1f}",
                                    '% at Full Dosage': f"{full_dosage_pct:.1f}%",
                                    'N': len(eth_data)
                                })
                        
                        if ethnicity_data:
                            ethnicity_df = pd.DataFrame(ethnicity_data)
                            st.dataframe(ethnicity_df, use_container_width=True, hide_index=True)
                            
                            # Visualization - use aggregated data
                            ethnicity_df['Avg Hours Numeric'] = pd.to_numeric(ethnicity_df['Avg Hours'], errors='coerce')
                            fig = px.bar(
                                ethnicity_df,
                                x='Ethnicity',
                                y='Avg Hours Numeric',
                                title='Average Dosage by Ethnicity',
                                labels={'Avg Hours Numeric': 'Average Tutoring Hours', 'Ethnicity': 'Ethnicity'},
                                color='Ethnicity',
                                text='N'
                            )
                            fig.update_traces(texttemplate='n=%{text}', textposition='outside')
                            fig.add_hline(
                                y=st.session_state['full_dosage_threshold'],
                                line_dash="dash",
                                line_color="orange",
                                annotation_text="Target"
                            )
                            fig.update_layout(height=400, showlegend=False)
                            st.plotly_chart(fig, use_container_width=True)
                    except Exception:
                        st.info("Ethnicity analysis unavailable.")
                
                st.markdown("---")
                
                # Visualization
                st.markdown("### Equity Comparison Chart")
                plot_equity_comparison(equity_df)
                
                st.markdown("---")

                st.markdown("### Dosage by Proficiency Level")
                st.caption("This view stays focused on tutored students. Higher dosage for lower-proficiency groups suggests the program is concentrating support where need is greatest.")

                try:
                    perf_col = 'performance_level_most_recent'
                    if perf_col in equity_df.columns:
                        proficiency_order = [
                            'far below basic', 'below basic', 'basic', 'approaching', 'proficient', 'advanced', 'exceeds',
                            'level 1', 'level 2', 'level 3', 'level 4', 'level 5',
                            'novice', 'developing', 'proficient', 'distinguished',
                        ]

                        def get_proficiency_index(level):
                            level_lower = str(level).lower()
                            for i, order_level in enumerate(proficiency_order):
                                if order_level in level_lower:
                                    return i
                            return 999

                        proficiency_data = []
                        for perf_level in equity_df[perf_col].dropna().unique():
                            perf_data = equity_df[equity_df[perf_col] == perf_level]
                            if len(perf_data) == 0:
                                continue
                            hours = tutoring_hours_series(perf_data)
                            proficiency_data.append({
                                'Proficiency Level': perf_level,
                                'Average Hours': hours.mean(),
                                '% at Full Dosage': (hours >= st.session_state['full_dosage_threshold']).sum() / len(perf_data) * 100,
                                'N': len(perf_data),
                                '_sort_key': get_proficiency_index(perf_level),
                            })

                        if proficiency_data:
                            proficiency_df = pd.DataFrame(proficiency_data).sort_values(['_sort_key', 'Proficiency Level'])
                            ordered_levels = proficiency_df['Proficiency Level'].tolist()

                            display_df = proficiency_df.drop(columns=['_sort_key']).copy()
                            display_df['Average Hours'] = display_df['Average Hours'].map(lambda value: f"{value:.1f}")
                            display_df['% at Full Dosage'] = display_df['% at Full Dosage'].map(lambda value: f"{value:.1f}%")
                            st.dataframe(display_df, use_container_width=True, hide_index=True)

                            fig = px.bar(
                                proficiency_df,
                                x='Proficiency Level',
                                y='Average Hours',
                                text='N',
                                labels={'Average Hours': 'Average Tutoring Hours', 'Proficiency Level': 'Most Recent Performance Level'},
                                title='Average Dosage by Most Recent Performance Level',
                                category_orders={'Proficiency Level': ordered_levels},
                            )
                            fig.update_traces(texttemplate='n=%{text}', textposition='outside')
                            fig.add_hline(
                                y=st.session_state['full_dosage_threshold'],
                                line_dash="dash",
                                line_color="orange",
                                annotation_text="Target",
                            )
                            fig.update_layout(height=400, showlegend=False)
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.info("Performance-level dosage analysis requires at least one populated most recent performance level.")
                    else:
                        st.info("Performance-level dosage analysis requires `performance_level_most_recent`.")
                except Exception as e:
                    st.info(f"Performance-level dosage analysis unavailable: {str(e)}")
    
    # ========================================================================
    # OUTCOMES TAB
    # ========================================================================
    with tab_outcomes:
        if st.session_state['session_data'] is None or st.session_state['student_data'] is None:
            st.warning("Please load data in the Upload & Schema tab first.")
        else:
            show_data_quality_warning()
            st.header("Outcomes Analysis")
            st.caption("These results are descriptive and do not establish causality. Outcome summaries use tutored students with valid outcome histories, and many factors beyond tutoring influence the results.")
            render_tab_readiness_message("outcomes", readiness_df)
            
            # Prepare data
            prepared_df = prepared_context_df if prepared_context_df is not None else get_prepared_data_cached(
                st.session_state['session_data'],
                st.session_state['student_data']
            )
            
            filters = render_compact_filters(prepared_df, "outcomes", "outcome_filter")
            filtered_outcome_df = apply_filter_values(prepared_df, filters)
            outcome_population = summarize_analysis_population(filtered_outcome_df)
            outcome_df = outcome_population['analysis_df']
            
            if outcome_population['matched_students'] == 0:
                st.warning("No students match the selected filters.")
            elif outcome_population['tutored_students'] == 0:
                st.warning("Students match the selected filters, but none of them received tutoring in the uploaded session data.")
            else:
                st.info(
                    f"📊 Matched **{outcome_population['matched_students']:,} students**; "
                    f"**{outcome_population['tutored_students']:,}** received tutoring "
                    f"({outcome_population['pct_tutored']:.1f}%) and are included in outcome calculations."
                )
                # Calculate outcome metrics
                outcome_metrics = calculate_outcome_metrics(outcome_df)

                unknown_notes = build_unknown_denominator_notes(
                    outcome_df,
                    {
                        "ell": "ELL",
                        "iep": "IEP",
                        "economic_disadvantage": "Economic disadvantage",
                    },
                )
                if unknown_notes:
                    st.caption("Unknown subgroup values remain in the outcome sample but are excluded from subgroup-specific filters and comparisons when selected.")
                    for note in unknown_notes:
                        st.caption(note)
                
                # Overall Outcomes Summary
                st.markdown("### Overall Outcomes Summary")
                overall_col1, overall_col2, overall_col3 = st.columns(3)
                
                with overall_col1:
                    avg_va = weighted_metric_average(
                        outcome_metrics,
                        (
                            ('ela_va_mean', 'ela_va_n'),
                            ('math_va_mean', 'math_va_n'),
                        ),
                    )
                    st.metric(
                        "Average Value-Added",
                        f"{avg_va:+.2f} points" if avg_va is not None else "N/A",
                        help=build_metric_help(
                            [
                                "VA_subject = mean((M3 - M2) - (M2 - M1))",
                                "Overall VA = weighted_mean(VA_ELA, VA_Math; n_ELA, n_Math)",
                            ],
                            "This combines ELA and Math using the number of tutored students with valid histories in each subject.",
                            [OUTCOME_MEASURE_HELP_NOTE],
                        )
                    )
                
                with overall_col2:
                    avg_effect_size = weighted_metric_average(
                        outcome_metrics,
                        (
                            ('ela_va_effect_size', 'ela_va_n'),
                            ('math_va_effect_size', 'math_va_n'),
                        ),
                    )
                    st.metric(
                        "Average Effect Size",
                        f"{avg_effect_size:+.3f} SD" if avg_effect_size is not None else "N/A",
                        help=build_metric_help(
                            [
                                "EffectSize_subject = mean(VA) / sd(VA)",
                                "Overall Effect Size = weighted_mean(ES_ELA, ES_Math; n_ELA, n_Math)",
                            ],
                            "This expresses value-added in standard-deviation units and then averages across subjects using available tutored-student counts.",
                            [OUTCOME_MEASURE_HELP_NOTE],
                        )
                    )
                
                with overall_col3:
                    avg_weeks = weighted_metric_average(
                        outcome_metrics,
                        (
                            ('ela_va_weeks_learning', 'ela_va_n'),
                            ('math_va_weeks_learning', 'math_va_n'),
                        ),
                    )
                    st.metric(
                        "Estimated Additional Weeks",
                        f"{avg_weeks:.1f} weeks" if avg_weeks is not None else "N/A",
                        help=build_metric_help(
                            [
                                "Weeks_subject = EffectSize_subject x 43",
                                "Overall Weeks = weighted_mean(Weeks_ELA, Weeks_Math; n_ELA, n_Math)",
                            ],
                            "The 43-week conversion is a rough translation from standard deviations to instructional weeks.",
                            [OUTCOME_MEASURE_HELP_NOTE],
                        )
                    )
                
                st.markdown("---")
                
                # ELA Panel
                st.markdown("### 📚 English Language Arts (ELA)")
                
                # Value-added metrics
                st.markdown("#### Value-Added Analysis")
                ela_va_col1, ela_va_col2, ela_va_col3 = st.columns(3)
                
                with ela_va_col1:
                    va_mean = outcome_metrics.get('ela_va_mean', 0)
                    st.metric(
                        "Average Value-Added",
                        f"{va_mean:+.2f} points",
                        help=build_metric_help(
                            [
                                "VA_i = (M3_i - M2_i) - (M2_i - M1_i)",
                                "Average VA = mean(VA_i)",
                            ],
                            "This asks whether the most recent score gain exceeded the earlier score gain for tutored students with valid histories.",
                            [OUTCOME_MEASURE_HELP_NOTE],
                        )
                    )
                    if outcome_metrics.get('ela_va_significant', False):
                        st.caption("✓ Statistically significant (p < 0.05)")
                    elif outcome_metrics.get('ela_va_pvalue', 1) < 0.10:
                        st.caption("~ Marginally significant (p < 0.10)")
                
                with ela_va_col2:
                    va_effect_size = outcome_metrics.get('ela_va_effect_size')
                    if va_effect_size is not None:
                        st.metric(
                            "Tutoring Effect (Standardized)",
                            f"{va_effect_size:+.3f} SD",
                            help=build_metric_help(
                                [
                                    "Effect Size = mean(VA_i) / sd(VA_i)",
                                ],
                                "This standardizes value-added so different outcome scales can be interpreted on a common SD scale within the same assessment.",
                                [OUTCOME_MEASURE_HELP_NOTE],
                            )
                        )
                    else:
                        st.metric(
                            "Tutoring Effect (Standardized)",
                            "N/A"
                        )
                
                with ela_va_col3:
                    va_weeks = outcome_metrics.get('ela_va_weeks_learning')
                    if va_weeks is not None:
                        st.metric(
                            "Estimated Additional Weeks of Learning",
                            f"{va_weeks:.1f} weeks",
                            help=build_metric_help(
                                [
                                    "Weeks = Effect Size x 43",
                                ],
                                "This is a rough translation of the standardized effect into instructional weeks, not a direct observed calendar measure.",
                            )
                        )
                    else:
                        st.metric(
                            "Estimated Additional Weeks of Learning",
                            "N/A"
                        )
                
                # Raw gain metrics
                st.markdown("#### Raw Score Improvement")
                ela_raw_col1, ela_raw_col2 = st.columns(2)
                
                with ela_raw_col1:
                    raw_mean = outcome_metrics.get('ela_raw_mean', 0)
                    st.metric(
                        "Average Raw Gain",
                        f"{raw_mean:+.2f} points",
                        help=build_metric_help(
                            [
                                "RawGain_i = M3_i - M1_i",
                                "Average Raw Gain = mean(RawGain_i)",
                            ],
                            "This is the straight score change from the earliest to the most recent measure for tutored students with valid histories.",
                            [OUTCOME_MEASURE_HELP_NOTE],
                        )
                    )
                
                with ela_raw_col2:
                    raw_positive = outcome_metrics.get('ela_raw_positive_pct', 0)
                    st.metric(
                        "% with Positive Gain",
                        f"{raw_positive:.1f}%",
                        help=build_metric_help(
                            [
                                "% Positive Gain = count(M3_i > M1_i) / n",
                            ],
                            "This is the share of tutored students whose most recent score is higher than their earliest score.",
                            [OUTCOME_MEASURE_HELP_NOTE],
                        )
                    )
                
                # Interpretation
                if va_mean < 1:
                    st.warning("⚠️ **Note:** Average value-added is less than 1 point. This suggests limited improvement beyond typical growth patterns.")
                elif va_mean >= 1:
                    st.success("✓ **Directionally positive:** Average value-added indicates improvement beyond typical growth.")
                
                # ELA distributions
                plot_outcome_distributions(outcome_df, 'ELA')
                
                st.markdown("---")
                
                # Math Panel
                st.markdown("### 🔢 Mathematics")
                
                # Value-added metrics
                st.markdown("#### Value-Added Analysis")
                math_va_col1, math_va_col2, math_va_col3 = st.columns(3)
                
                with math_va_col1:
                    va_mean = outcome_metrics.get('math_va_mean', 0)
                    st.metric(
                        "Average Value-Added",
                        f"{va_mean:+.2f} points",
                        help=build_metric_help(
                            [
                                "VA_i = (M3_i - M2_i) - (M2_i - M1_i)",
                                "Average VA = mean(VA_i)",
                            ],
                            "This asks whether the most recent score gain exceeded the earlier score gain for tutored students with valid histories.",
                            [OUTCOME_MEASURE_HELP_NOTE],
                        )
                    )
                    if outcome_metrics.get('math_va_significant', False):
                        st.caption("✓ Statistically significant (p < 0.05)")
                    elif outcome_metrics.get('math_va_pvalue', 1) < 0.10:
                        st.caption("~ Marginally significant (p < 0.10)")
                
                with math_va_col2:
                    va_effect_size = outcome_metrics.get('math_va_effect_size')
                    if va_effect_size is not None:
                        st.metric(
                            "Tutoring Effect (Standardized)",
                            f"{va_effect_size:+.3f} SD",
                            help=build_metric_help(
                                [
                                    "Effect Size = mean(VA_i) / sd(VA_i)",
                                ],
                                "This standardizes value-added so different outcome scales can be interpreted on a common SD scale within the same assessment.",
                                [OUTCOME_MEASURE_HELP_NOTE],
                            )
                        )
                    else:
                        st.metric(
                            "Tutoring Effect (Standardized)",
                            "N/A"
                        )
                
                with math_va_col3:
                    va_weeks = outcome_metrics.get('math_va_weeks_learning')
                    if va_weeks is not None:
                        st.metric(
                            "Estimated Additional Weeks of Learning",
                            f"{va_weeks:.1f} weeks",
                            help=build_metric_help(
                                [
                                    "Weeks = Effect Size x 43",
                                ],
                                "This is a rough translation of the standardized effect into instructional weeks, not a direct observed calendar measure.",
                            )
                        )
                    else:
                        st.metric(
                            "Estimated Additional Weeks of Learning",
                            "N/A"
                        )
                
                # Raw gain metrics
                st.markdown("#### Raw Score Improvement")
                math_raw_col1, math_raw_col2 = st.columns(2)
                
                with math_raw_col1:
                    raw_mean = outcome_metrics.get('math_raw_mean', 0)
                    st.metric(
                        "Average Raw Gain",
                        f"{raw_mean:+.2f} points",
                        help=build_metric_help(
                            [
                                "RawGain_i = M3_i - M1_i",
                                "Average Raw Gain = mean(RawGain_i)",
                            ],
                            "This is the straight score change from the earliest to the most recent measure for tutored students with valid histories.",
                            [OUTCOME_MEASURE_HELP_NOTE],
                        )
                    )
                
                with math_raw_col2:
                    raw_positive = outcome_metrics.get('math_raw_positive_pct', 0)
                    st.metric(
                        "% with Positive Gain",
                        f"{raw_positive:.1f}%",
                        help=build_metric_help(
                            [
                                "% Positive Gain = count(M3_i > M1_i) / n",
                            ],
                            "This is the share of tutored students whose most recent score is higher than their earliest score.",
                            [OUTCOME_MEASURE_HELP_NOTE],
                        )
                    )
                
                # Interpretation
                if va_mean < 1:
                    st.warning("⚠️ **Note:** Average value-added is less than 1 point. This suggests limited improvement beyond typical growth patterns.")
                elif va_mean >= 1:
                    st.success("✓ **Directionally positive:** Average value-added indicates improvement beyond typical growth.")
                
                # Math distributions
                plot_outcome_distributions(outcome_df, 'Math')
                
    
    # ========================================================================
    # COST ANALYTICS TAB
    # ========================================================================
    with tab_cost:
        if st.session_state['session_data'] is None or st.session_state['student_data'] is None:
            st.warning("Please load data in the Upload & Schema tab first.")
        else:
            show_data_quality_warning()
            st.header("Cost Analytics")
            st.caption("Understanding program costs for tutored students")
            render_tab_readiness_message("cost", readiness_df)
            
            if st.session_state['total_cost'] == 0:
                st.warning("⚠️ Total program cost is set to $0. Please set the cost in the sidebar to view cost-effectiveness metrics.")
            
            # Prepare data
            prepared_df = prepared_context_df if prepared_context_df is not None else get_prepared_data_cached(
                st.session_state['session_data'],
                st.session_state['student_data']
            )
            
            filters = render_compact_filters(prepared_df, "cost", "cost_filter")
            filtered_cost_df = apply_filter_values(prepared_df, filters)
            cost_population = summarize_analysis_population(filtered_cost_df)
            cost_df = cost_population['analysis_df']
            
            if cost_population['matched_students'] == 0:
                st.warning("No students match the selected filters.")
            elif cost_population['tutored_students'] == 0:
                st.warning("Students match the selected filters, but none of them received tutoring in the uploaded session data.")
            else:
                st.info(
                    f"📊 Matched **{cost_population['matched_students']:,} students**; "
                    f"**{cost_population['tutored_students']:,}** received tutoring "
                    f"({cost_population['pct_tutored']:.1f}%) and are included in cost calculations."
                )
                # Calculate cost metrics
                cost_metrics = calculate_cost_metrics(
                    cost_df,
                    st.session_state['total_cost'],
                    st.session_state['full_dosage_threshold'],
                    reference_df=prepared_df,
                )
                
                # Basic cost metrics
                st.markdown("### Basic Cost Metrics")
                st.caption("When filters are active, the app allocates the total program cost to the current tutored sample in proportion to its share of all delivered tutoring hours.")
                share = cost_metrics.get('cost_allocation_share')
                if share is not None:
                    st.caption(
                        f"Current view is assigned **{share:.1%}** of the entered total program cost based on delivered tutoring hours."
                    )
                cost_col1, cost_col2 = st.columns(2)

                with cost_col1:
                    st.metric(
                        "Cost per Tutored Student",
                        f"${cost_metrics.get('cost_per_student', 0):,.2f}",
                        help=build_metric_help(
                            [
                                "Allocated Cost = Total Cost x (Hours in View / Hours in Full Tutored Sample)",
                                "Cost per Tutored Student = Allocated Cost / n_tutored",
                            ],
                            "This is the average program cost assigned to each tutored student in the current view.",
                        )
                    )
                
                with cost_col2:
                    st.metric(
                        "Cost per Tutoring Hour",
                        f"${cost_metrics.get('cost_per_hour', 0):,.2f}",
                        help=build_metric_help(
                            [
                                "Allocated Cost = Total Cost x (Hours in View / Hours in Full Tutored Sample)",
                                "Cost per Hour = Allocated Cost / Total Tutoring Hours",
                            ],
                            "This is the cost assigned to each tutoring hour delivered in the current tutored sample.",
                        )
                    )
                
                st.markdown("---")
                
                # Cost per outcome
                st.markdown("### Cost per Outcome")
                st.caption("**What to look for:** Lower values indicate better cost-effectiveness. Compare to benchmarks if available.")
                
                outcome_col1, outcome_col2 = st.columns(2)
                
                with outcome_col1:
                    cost_per_va = cost_metrics.get('cost_per_va_point')
                    if cost_per_va is not None:
                        st.metric(
                            "Cost per Value-Added Point",
                            f"${cost_per_va:,.2f}",
                            help=build_metric_help(
                                [
                                    "VA_i = (M3_i - M2_i) - (M2_i - M1_i)",
                                    "Cost per VA Point = Allocated Cost / sum(VA_i)",
                                ],
                                "This spreads the allocated program cost across the total positive value-added points observed in the current tutored sample.",
                                [OUTCOME_MEASURE_HELP_NOTE],
                            )
                        )
                    else:
                        st.metric(
                            "Cost per Value-Added Point",
                            "N/A",
                            help=build_metric_help(
                                [
                                    "Cost per VA Point = Allocated Cost / sum(VA_i)",
                                ],
                                "This metric is unavailable when the summed value-added points in the current view are not positive.",
                                [OUTCOME_MEASURE_HELP_NOTE],
                            )
                        )
                
                with outcome_col2:
                    cost_per_raw = cost_metrics.get('cost_per_raw_point')
                    if cost_per_raw is not None:
                        st.metric(
                            "Cost per Raw Point Gained",
                            f"${cost_per_raw:,.2f}",
                            help=build_metric_help(
                                [
                                    "RawGain_i = M3_i - M1_i",
                                    "Cost per Raw Point = Allocated Cost / sum(RawGain_i)",
                                ],
                                "This spreads the allocated program cost across the total raw-score points gained in the current tutored sample.",
                                [OUTCOME_MEASURE_HELP_NOTE],
                            )
                        )
                    else:
                        st.metric(
                            "Cost per Raw Point Gained",
                            "N/A",
                            help=build_metric_help(
                                [
                                    "Cost per Raw Point = Allocated Cost / sum(RawGain_i)",
                                ],
                                "This metric is unavailable when the summed raw-gain points in the current view are not positive.",
                                [OUTCOME_MEASURE_HELP_NOTE],
                            )
                        )
                
                st.markdown("---")
                st.markdown("These are basic metrics only. For a complete cost analysis, please use [Accelerate's Cost Tool](https://accelerate.us/cost-tool/).")

    # Footer caveat
    st.markdown("---")
    st.caption("This tool can be run locally if you prefer not to upload data to a hosted app. Please feel free to run it [locally](https://github.com/accelerate-usa/tutor-data-standard/tree/main/toolkit). If you use a hosted version, all data are erased upon refresh.")
    render_runtime_diagnostics()


if __name__ == "__main__":
    main()
