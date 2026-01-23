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
from typing import Dict, List, Tuple, Optional
import re
from datetime import datetime
import requests
from io import StringIO

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

def prepare_data(session_df: pd.DataFrame, student_df: pd.DataFrame) -> pd.DataFrame:
    """Merge and prepare data for analysis. Handles missing columns gracefully."""
    session_df = session_df.copy()
    student_df = student_df.copy()
    
    # Standardize student_id if it exists
    if 'student_id' in session_df.columns:
        session_df['student_id'] = session_df['student_id'].astype(str).str.strip()
    if 'student_id' in student_df.columns:
        student_df['student_id'] = student_df['student_id'].astype(str).str.strip()
    else:
        # If student_id is missing, we can't proceed
        return student_df
    
    # Convert session duration to hours if column exists
    if 'session_duration' in session_df.columns:
        try:
            session_df['session_duration_hours'] = pd.to_numeric(session_df['session_duration'], errors='coerce') / 60
        except:
            session_df['session_duration_hours'] = 0
    else:
        session_df['session_duration_hours'] = 0
    
    # Merge datasets
    try:
        merged_df = session_df.merge(student_df, on='student_id', how='inner')
    except:
        # If merge fails, return student_df with zero hours
        student_df['total_hours'] = 0
        return student_df
    
    # Calculate tutoring hours per student
    if 'session_duration_hours' in merged_df.columns:
        try:
            hours_per_student = (
                merged_df.groupby('student_id')['session_duration_hours']
                .sum()
                .reset_index()
                .rename(columns={'session_duration_hours': 'total_hours'})
            )
        except:
            hours_per_student = pd.DataFrame({'student_id': student_df['student_id'].unique(), 'total_hours': 0})
    else:
        hours_per_student = pd.DataFrame({'student_id': student_df['student_id'].unique(), 'total_hours': 0})
    
    # Merge hours back
    try:
        student_with_hours = student_df.merge(hours_per_student, on='student_id', how='left')
        student_with_hours['total_hours'] = student_with_hours['total_hours'].fillna(0)
    except:
        student_with_hours = student_df.copy()
        student_with_hours['total_hours'] = 0
    
    # Calculate value-added metrics (only if required columns exist)
    ela_score_cols = ['ela_state_score_current_year', 'ela_state_score_one_year_ago', 'ela_state_score_two_years_ago']
    math_score_cols = ['math_state_score_current_year', 'math_state_score_one_year_ago', 'math_state_score_two_years_ago']
    
    if all(col in student_with_hours.columns for col in ela_score_cols):
        try:
            student_with_hours['ela_value_added'] = (
                (pd.to_numeric(student_with_hours['ela_state_score_current_year'], errors='coerce') - 
                 pd.to_numeric(student_with_hours['ela_state_score_one_year_ago'], errors='coerce')) -
                (pd.to_numeric(student_with_hours['ela_state_score_one_year_ago'], errors='coerce') - 
                 pd.to_numeric(student_with_hours['ela_state_score_two_years_ago'], errors='coerce'))
            )
            student_with_hours['ela_raw_gain'] = (
                pd.to_numeric(student_with_hours['ela_state_score_current_year'], errors='coerce') - 
                pd.to_numeric(student_with_hours['ela_state_score_two_years_ago'], errors='coerce')
            )
        except:
            student_with_hours['ela_value_added'] = np.nan
            student_with_hours['ela_raw_gain'] = np.nan
    else:
        student_with_hours['ela_value_added'] = np.nan
        student_with_hours['ela_raw_gain'] = np.nan
    
    if all(col in student_with_hours.columns for col in math_score_cols):
        try:
            student_with_hours['math_value_added'] = (
                (pd.to_numeric(student_with_hours['math_state_score_current_year'], errors='coerce') - 
                 pd.to_numeric(student_with_hours['math_state_score_one_year_ago'], errors='coerce')) -
                (pd.to_numeric(student_with_hours['math_state_score_one_year_ago'], errors='coerce') - 
                 pd.to_numeric(student_with_hours['math_state_score_two_years_ago'], errors='coerce'))
            )
            student_with_hours['math_raw_gain'] = (
                pd.to_numeric(student_with_hours['math_state_score_current_year'], errors='coerce') - 
                pd.to_numeric(student_with_hours['math_state_score_two_years_ago'], errors='coerce')
            )
        except:
            student_with_hours['math_value_added'] = np.nan
            student_with_hours['math_raw_gain'] = np.nan
    else:
        student_with_hours['math_value_added'] = np.nan
        student_with_hours['math_raw_gain'] = np.nan
    
    # Normalize boolean fields
    bool_fields = ['ell', 'iep', 'gifted_flag', 'homeless_flag', 'disability', 'economic_disadvantage']
    for field in bool_fields:
        if field in student_with_hours.columns:
            try:
                student_with_hours[field] = student_with_hours[field].astype(str).str.lower()
                student_with_hours[field] = student_with_hours[field].isin(['true', '1', 'yes', 't', 'y'])
            except:
                student_with_hours[field] = False
    
    return student_with_hours


def apply_filters(df: pd.DataFrame, filters: Dict) -> pd.DataFrame:
    """Apply filters to dataframe."""
    filtered_df = df.copy()
    
    if filters.get('school') and filters['school'] != 'All':
        filtered_df = filtered_df[filtered_df['school_name'] == filters['school']]
    
    if filters.get('grades'):
        filtered_df = filtered_df[filtered_df['current_grade_level'].isin(filters['grades'])]
    
    if filters.get('ell') is not None:
        filtered_df = filtered_df[filtered_df['ell'] == filters['ell']]
    
    if filters.get('iep') is not None:
        filtered_df = filtered_df[filtered_df['iep'] == filters['iep']]
    
    if filters.get('economic_disadvantage') is not None:
        filtered_df = filtered_df[filtered_df['economic_disadvantage'] == filters['economic_disadvantage']]
    
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
    hours = df['total_hours'].dropna()
    
    if len(hours) == 0:
        return {}
    
    metrics = {
        'median_hours': hours.median(),
        'mean_hours': hours.mean(),
        'q25': hours.quantile(0.25),
        'q75': hours.quantile(0.75),
        'iqr': hours.quantile(0.75) - hours.quantile(0.25),
        'total_students': len(hours),
        'target_dosage': target_dosage
    }
    
    # Dosage categories (quartiles)
    metrics['pct_below_25'] = (hours < target_dosage * 0.25).sum() / len(hours) * 100
    metrics['pct_25_50'] = ((hours >= target_dosage * 0.25) & (hours < target_dosage * 0.5)).sum() / len(hours) * 100
    metrics['pct_50_75'] = ((hours >= target_dosage * 0.5) & (hours < target_dosage * 0.75)).sum() / len(hours) * 100
    metrics['pct_75_99'] = ((hours >= target_dosage * 0.75) & (hours < target_dosage)).sum() / len(hours) * 100
    metrics['pct_full_dosage'] = (hours >= target_dosage).sum() / len(hours) * 100
    
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
    
    # High-need students reaching full dosage
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
                # Weeks of learning (assuming ~0.1 SD per month, ~4.3 weeks per month)
                # Effect size * 4.3 gives approximate weeks
                metrics['ela_va_weeks_learning'] = metrics['ela_va_effect_size'] * 4.3
    
    if len(ela_raw) > 0:
        metrics['ela_raw_mean'] = ela_raw.mean()
        metrics['ela_raw_positive_pct'] = (ela_raw > 0).sum() / len(ela_raw) * 100
        metrics['ela_raw_n'] = len(ela_raw)
        
        # Standardized effect size for raw gains
        if len(ela_raw) > 1 and ela_raw.std() > 0:
            metrics['ela_raw_effect_size'] = ela_raw.mean() / ela_raw.std()
            metrics['ela_raw_weeks_learning'] = metrics['ela_raw_effect_size'] * 4.3
    
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
                # Weeks of learning
                metrics['math_va_weeks_learning'] = metrics['math_va_effect_size'] * 4.3
    
    if len(math_raw) > 0:
        metrics['math_raw_mean'] = math_raw.mean()
        metrics['math_raw_positive_pct'] = (math_raw > 0).sum() / len(math_raw) * 100
        metrics['math_raw_n'] = len(math_raw)
        
        # Standardized effect size for raw gains
        if len(math_raw) > 1 and math_raw.std() > 0:
            metrics['math_raw_effect_size'] = math_raw.mean() / math_raw.std()
            metrics['math_raw_weeks_learning'] = metrics['math_raw_effect_size'] * 4.3
    
    return metrics


def calculate_cost_metrics(df: pd.DataFrame, total_cost: float, target_dosage: float) -> Dict:
    """Calculate cost-effectiveness metrics."""
    metrics = {}
    n_students = len(df)
    
    if n_students == 0:
        return metrics
    
    total_hours = df['total_hours'].sum()
    
    metrics['cost_per_student'] = total_cost / n_students if n_students > 0 else 0
    metrics['cost_per_hour'] = total_cost / total_hours if total_hours > 0 else 0
    
    # Cost per point gained - use sum of all value-added points
    outcome_metrics = calculate_outcome_metrics(df)
    
    # Calculate total value-added points (sum across all students)
    ela_va_sum = df['ela_value_added'].dropna().sum()
    math_va_sum = df['math_value_added'].dropna().sum()
    total_va_points = ela_va_sum + math_va_sum
    
    # Calculate total raw gain points
    ela_raw_sum = df['ela_raw_gain'].dropna().sum()
    math_raw_sum = df['math_raw_gain'].dropna().sum()
    total_raw_points = ela_raw_sum + math_raw_sum
    
    if total_va_points > 0:
        metrics['cost_per_va_point'] = total_cost / total_va_points
    else:
        metrics['cost_per_va_point'] = None
    
    if total_raw_points > 0:
        metrics['cost_per_raw_point'] = total_cost / total_raw_points
    else:
        metrics['cost_per_raw_point'] = None
    
    return metrics


# ============================================================================
# VISUALIZATION FUNCTIONS
# ============================================================================

def plot_dosage_distribution(df: pd.DataFrame, target_dosage: float):
    """Create dosage distribution visualization."""
    hours = df['total_hours'].dropna()
    
    if len(hours) == 0:
        st.warning("No dosage data available for visualization.")
        return
    
    # Create histogram with dosage categories (quartiles)
    df_viz = df.copy()
    df_viz['dosage_category'] = pd.cut(
        df_viz['total_hours'],
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
# UI HELPER FUNCTIONS
# ============================================================================

def load_example_data():
    """Download and load example data from Google Drive."""
    try:
        # Google Drive file IDs
        session_file_id = "1ivNs9gFkIIgiABUHEOvsm8mCmvg9nKJ3"
        student_file_id = "1FjTLaWGRQd6zlgaXkqHkAU_Gj8kUzgGY"
        
        # Convert to direct download URLs
        session_url = f"https://drive.google.com/uc?export=download&id={session_file_id}"
        student_url = f"https://drive.google.com/uc?export=download&id={student_file_id}"
        
        # Download files
        session_response = requests.get(session_url, timeout=30)
        student_response = requests.get(student_url, timeout=30)
        
        if session_response.status_code == 200 and student_response.status_code == 200:
            # Load into DataFrames
            session_df = pd.read_csv(StringIO(session_response.text))
            student_df = pd.read_csv(StringIO(student_response.text))
            
            return session_df, student_df
        else:
            return None, None
    except Exception as e:
        st.error(f"Error loading example data: {str(e)}")
        return None, None


def show_data_quality_warning():
    """Display a warning banner if data has validation issues."""
    has_warnings = (
        st.session_state.get('session_validation_warnings', False) or
        st.session_state.get('student_validation_warnings', False)
    )
    
    if has_warnings:
        st.warning("⚠️ **Data Quality Notice:** Your data loaded with validation warnings. Some results may be affected. Review validation messages in the Data Overview tab for details.")


# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    # Header
    st.markdown('<div class="main-header">📊 DATAS Analysis Toolkit</div>', unsafe_allow_html=True)
    st.markdown("---")
    
    # Initialize session state
    if 'session_data' not in st.session_state:
        st.session_state['session_data'] = None
    if 'student_data' not in st.session_state:
        st.session_state['student_data'] = None
    if 'full_dosage_threshold' not in st.session_state:
        st.session_state['full_dosage_threshold'] = 60.0
    if 'total_cost' not in st.session_state:
        st.session_state['total_cost'] = 0.0
    
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
                total_students = len(student_data)
                
                # Calculate tutored students
                if 'student_id' in session_data.columns and 'student_id' in student_data.columns:
                    tutored_students = session_data['student_id'].nunique()
                else:
                    tutored_students = 0
                
                # Calculate average hours per student
                if 'session_duration' in session_data.columns:
                    total_minutes = pd.to_numeric(session_data['session_duration'], errors='coerce').sum()
                    total_hours = total_minutes / 60 if not pd.isna(total_minutes) else 0
                    if total_students > 0:
                        avg_hours = total_hours / total_students
                    else:
                        avg_hours = 0
                else:
                    avg_hours = 0
                
                st.caption(f"**Total Students:** {total_students:,}")
                st.caption(f"**Tutored Students:** {tutored_students:,}")
                st.caption(f"**Avg Hours/Student:** {avg_hours:.1f}")
            except Exception:
                st.caption("See Data Overview tab for detailed statistics")
        else:
            st.warning("⚠ Data not loaded")
            st.caption("Load data in the Data Overview tab")
    
    # Main tabs
    tab_overview, tab_dosage, tab_equity, tab_outcomes, tab_cost = st.tabs([
        "📋 Data Overview",
        "📊 Dosage & Access",
        "⚖️ Equity Analysis",
        "📈 Outcomes",
        "💰 Cost Analytics"
    ])
    
    # ========================================================================
    # DATA OVERVIEW TAB
    # ========================================================================
    with tab_overview:
        st.header("Data Overview")
        
        # Always show data upload option, even if data is already loaded
        with st.expander("📤 Upload or Replace Data", expanded=(st.session_state['session_data'] is None or st.session_state['student_data'] is None)):
            if st.session_state['session_data'] is not None and st.session_state['student_data'] is not None:
                st.info("💡 **Data already loaded.** Upload new files below to replace the current data.")
                if st.button("🗑️ Clear Current Data", type="secondary"):
                    st.session_state['session_data'] = None
                    st.session_state['student_data'] = None
                    st.session_state['last_processed_files'] = None  # Reset file tracking
                    st.success("Data cleared. Please upload new files.")
                    st.rerun()
            
            session_file = st.file_uploader("Upload Session Data (CSV)", type=['csv'], key='session_upload')
            student_file = st.file_uploader("Upload Student Data (CSV)", type=['csv'], key='student_upload')
            
            if session_file and student_file:
                # Check if we've already processed these files (prevent infinite loop)
                current_file_ids = (session_file.name, student_file.name, session_file.size, student_file.size)
                last_processed = st.session_state.get('last_processed_files', None)
                
                if current_file_ids != last_processed:
                    try:
                        # Load data
                        session_df = pd.read_csv(session_file)
                        student_df = pd.read_csv(student_file)
                        
                        # Validate data
                        st.markdown("### 🔍 Validating Data...")
                        
                        session_errors = validate_data_comprehensive(session_df, 'session')
                        student_errors = validate_data_comprehensive(student_df, 'student')
                        
                        # Display validation results (but don't block)
                        session_has_issues = display_validation_errors(session_errors, 'Session')
                        student_has_issues = display_validation_errors(student_errors, 'Student')
                        
                        # Always load data, even with errors
                        st.session_state['session_data'] = session_df
                        st.session_state['student_data'] = student_df
                        st.session_state['session_validation_warnings'] = len(session_errors.get('warnings', [])) > 0 or len(session_errors.get('critical', [])) > 0
                        st.session_state['student_validation_warnings'] = len(student_errors.get('warnings', [])) > 0 or len(student_errors.get('critical', [])) > 0
                        
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
            with st.spinner("Downloading example data..."):
                session_df, student_df = load_example_data()
                if session_df is not None and student_df is not None:
                    # Validate and load
                    session_errors = validate_data_comprehensive(session_df, 'session')
                    student_errors = validate_data_comprehensive(student_df, 'student')
                    
                    display_validation_errors(session_errors, 'Session')
                    display_validation_errors(student_errors, 'Student')
                    
                    st.session_state['session_data'] = session_df
                    st.session_state['student_data'] = student_df
                    st.session_state['session_validation_warnings'] = len(session_errors.get('warnings', [])) > 0 or len(session_errors.get('critical', [])) > 0
                    st.session_state['student_validation_warnings'] = len(student_errors.get('warnings', [])) > 0 or len(student_errors.get('critical', [])) > 0
                    
                    st.success("✅ **Example data loaded successfully!**")
                    st.rerun()
                else:
                    st.error("❌ Failed to load example data. Please try again or download manually.")
        
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
                prepared_df = prepare_data(
                    st.session_state['session_data'],
                    st.session_state['student_data']
                )
            except Exception as e:
                st.error(f"❌ **Error preparing data for analysis:** {str(e)}")
                st.info("This error may be due to data quality issues. Please review your data files and try again.")
                st.stop()
            
            # Summary statistics
            st.markdown("### Program Overview")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Students", f"{len(prepared_df):,}")
            
            with col2:
                total_hours = prepared_df['total_hours'].sum()
                st.metric("Total Tutoring Hours", f"{total_hours:,.0f}")
            
            with col3:
                avg_hours = prepared_df['total_hours'].mean()
                st.metric("Average Hours/Student", f"{avg_hours:.1f}")
            
            with col4:
                schools = prepared_df['school_name'].nunique() if 'school_name' in prepared_df.columns else 0
                st.metric("Schools", f"{schools}")
            
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
                    if 'student_id' in session_df.columns and 'student_id' in student_df.columns:
                        try:
                            tutored_students = session_df['student_id'].nunique()
                            st.metric("Students Tutored", f"{tutored_students:,}")
                        except:
                            st.metric("Students Tutored", "N/A")
                    else:
                        st.metric("Students Tutored", "N/A")
                
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
            
            # Data preview
            with st.expander("📊 Data Preview", expanded=False):
                st.subheader("Student Data Sample")
                st.dataframe(prepared_df.head(10), use_container_width=True)
                
                st.subheader("Data Summary")
                st.dataframe(prepared_df.describe(), use_container_width=True)
    
    # ========================================================================
    # DOSAGE & ACCESS TAB
    # ========================================================================
    with tab_dosage:
        if st.session_state['session_data'] is None or st.session_state['student_data'] is None:
            st.warning("Please load data in the Data Overview tab first.")
        else:
            show_data_quality_warning()
            st.header("Dosage & Access Analysis")
            st.caption("Understanding how much tutoring students are receiving")
            
            # Prepare data
            prepared_df = prepare_data(
                st.session_state['session_data'],
                st.session_state['student_data']
            )
            
            # Filters
            with st.expander("🔍 Filters", expanded=False):
                col1, col2 = st.columns(2)
                
                with col1:
                    school_options = ['All'] + sorted(prepared_df['school_name'].dropna().unique().tolist()) if 'school_name' in prepared_df.columns else ['All']
                    selected_school = st.selectbox("School", school_options, key='dosage_school')
                    
                    grade_options = sorted(prepared_df['current_grade_level'].dropna().unique().tolist())
                    selected_grades = st.multiselect("Grade Levels", grade_options, default=grade_options, key='dosage_grades')
                
                with col2:
                    gender_options = prepared_df['gender'].dropna().unique().tolist() if 'gender' in prepared_df.columns else []
                    selected_gender = st.multiselect("Gender", gender_options, default=gender_options, key='dosage_gender')
                    
                    ethnicity_options = prepared_df['ethnicity'].dropna().unique().tolist() if 'ethnicity' in prepared_df.columns else []
                    selected_ethnicity = st.multiselect("Ethnicity", ethnicity_options, default=ethnicity_options, key='dosage_ethnicity')
            
            # Apply filters
            filters = {
                'school': selected_school,
                'grades': selected_grades,
                'gender': selected_gender,
                'ethnicity': selected_ethnicity
            }
            
            filtered_df = apply_filters(prepared_df, filters)
            
            # Show filtered count
            st.info(f"📊 Analyzing **{len(filtered_df):,} students** (after filters)")
            
            if len(filtered_df) == 0:
                st.warning("No students match the selected filters.")
            else:
                # Calculate metrics
                dosage_metrics = calculate_dosage_metrics(
                    filtered_df,
                    st.session_state['full_dosage_threshold']
                )
                
                # Visualization at the top
                st.markdown("### Distribution of Tutoring Hours")
                st.caption("**What to look for:** A right-skewed distribution suggests most students receive below-target dosage. Look for the vertical line marking your target.")
                plot_dosage_distribution(filtered_df, st.session_state['full_dosage_threshold'])
                
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
                                'Total Students': tutored_total,
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
            st.warning("Please load data in the Data Overview tab first.")
        else:
            show_data_quality_warning()
            st.header("Equity Analysis")
            st.caption("Examining dosage gaps across student subgroups")
            
            # Prepare data
            prepared_df = prepare_data(
                st.session_state['session_data'],
                st.session_state['student_data']
            )
            
            # Filters
            with st.expander("🔍 Filters", expanded=False):
                col1, col2 = st.columns(2)
                
                with col1:
                    school_options = ['All'] + sorted(prepared_df['school_name'].dropna().unique().tolist()) if 'school_name' in prepared_df.columns else ['All']
                    equity_school = st.selectbox("School", school_options, key='equity_school')
                    
                    grade_options = sorted(prepared_df['current_grade_level'].dropna().unique().tolist())
                    equity_grades = st.multiselect("Grade Levels", grade_options, default=grade_options, key='equity_grades')
                
                with col2:
                    ell_filter = st.selectbox("ELL Status", ['All', 'ELL Only', 'Non-ELL Only'], key='ell_filter')
                    iep_filter = st.selectbox("IEP Status", ['All', 'IEP Only', 'Non-IEP Only'], key='iep_filter')
                    econ_filter = st.selectbox("Economic Status", ['All', 'Disadvantaged Only', 'Not Disadvantaged'], key='econ_filter')
            
            # Apply filters
            equity_df = prepared_df.copy()
            if equity_school != 'All':
                equity_df = equity_df[equity_df['school_name'] == equity_school]
            
            equity_df = equity_df[equity_df['current_grade_level'].isin(equity_grades)]
            
            if ell_filter == 'ELL Only':
                equity_df = equity_df[equity_df.get('ell', pd.Series([False] * len(equity_df))) == True]
            elif ell_filter == 'Non-ELL Only':
                equity_df = equity_df[equity_df.get('ell', pd.Series([False] * len(equity_df))) == False]
            
            if iep_filter == 'IEP Only':
                equity_df = equity_df[equity_df.get('iep', pd.Series([False] * len(equity_df))) == True]
            elif iep_filter == 'Non-IEP Only':
                equity_df = equity_df[equity_df.get('iep', pd.Series([False] * len(equity_df))) == False]
            
            if econ_filter == 'Disadvantaged Only':
                equity_df = equity_df[equity_df.get('economic_disadvantage', pd.Series([False] * len(equity_df))) == True]
            elif econ_filter == 'Not Disadvantaged':
                equity_df = equity_df[equity_df.get('economic_disadvantage', pd.Series([False] * len(equity_df))) == False]
            
            st.info(f"📊 Analyzing **{len(equity_df):,} students**")
            
            if len(equity_df) == 0:
                st.warning("No students match the selected filters.")
            else:
                # Calculate equity metrics
                equity_metrics = calculate_equity_metrics(equity_df)
                
                # Equity gaps
                st.markdown("### Equity Gaps in Dosage")
                st.caption("Positive gaps indicate disadvantaged groups receive more hours. Negative gaps indicate they receive fewer hours.")
                
                gap_col1, gap_col2, gap_col3 = st.columns(3)
                
                if 'ell_gap' in equity_metrics:
                    with gap_col1:
                        gap = equity_metrics['ell_gap']
                        ell_mean = equity_metrics.get('ell_ell_mean', 0)
                        non_ell_mean = equity_metrics.get('ell_non_ell_mean', 0)
                        st.metric(
                            "ELL Gap",
                            f"{gap:+.1f} hours",
                            help=f"Formula: Gap = ELL Mean - Non-ELL Mean\n\nELL students average {ell_mean:.1f} hrs vs {non_ell_mean:.1f} hrs for non-ELL. Positive gap indicates ELL students receive more hours (equitable)."
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
                            help=f"Formula: Gap = IEP Mean - Non-IEP Mean\n\nIEP students average {iep_mean:.1f} hrs vs {non_iep_mean:.1f} hrs for non-IEP. Positive gap indicates IEP students receive more hours (equitable)."
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
                            help=f"Formula: Gap = Disadvantaged Mean - Not Disadvantaged Mean\n\nEconomically disadvantaged students average {econ_disadv_mean:.1f} hrs vs {econ_adv_mean:.1f} hrs for others. Positive gap indicates disadvantaged students receive more hours (equitable)."
                        )
                        if equity_metrics.get('econ_disadv_n', 0) < 30 or equity_metrics.get('econ_adv_n', 0) < 30:
                            st.caption("⚠️ Small sample size")
                
                st.markdown("---")
                
                # High-need students reaching full dosage
                if 'high_need_full_dosage_pct' in equity_metrics:
                    st.markdown("### High-Need Students Reaching Full Dosage")
                    pct = equity_metrics['high_need_full_dosage_pct']
                    n = equity_metrics.get('high_need_n', 0)
                    
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.metric(
                            "High-Need Students at Full Dosage",
                            f"{pct:.1f}%",
                            delta=f"{int(pct * n / 100)} of {n} high-need students"
                        )
                    with col2:
                        if n < 30:
                            st.warning("⚠️ Small sample size")
                
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
                
                # Tutoring Participation by Proficiency Level
                st.markdown("### Tutoring Participation by Proficiency Level")
                st.caption("**What to look for:** Higher participation rates for low-proficiency students indicate equitable targeting. Lower rates suggest high-proficiency students may be receiving more tutoring.")
                
                # Get session data to determine who received tutoring
                try:
                    session_df = st.session_state['session_data'].copy()
                    session_df['student_id'] = session_df['student_id'].astype(str).str.strip()
                    tutored_student_ids = set(session_df['student_id'].unique())
                    
                    # Add tutoring flag to equity_df
                    equity_df['received_tutoring'] = equity_df['student_id'].astype(str).isin(tutored_student_ids)
                    
                    # Analysis by Performance Level (current year only) - styled like equity comparison
                    perf_col = 'performance_level_current_year'
                    if perf_col in equity_df.columns:
                        try:
                            st.markdown(f"#### By {perf_col.replace('_', ' ').title()}")
                            
                            proficiency_data = []
                            for perf_level in equity_df[perf_col].dropna().unique():
                                perf_data = equity_df[equity_df[perf_col] == perf_level]
                                total = len(perf_data)
                                tutored = perf_data['received_tutoring'].sum()
                                untutored = total - tutored
                                
                                proficiency_data.append({
                                    'Proficiency Level': perf_level,
                                    'Tutored': tutored,
                                    'Untutored': untutored
                                })
                            
                            if proficiency_data:
                                # Define proficiency order (least to most proficient)
                                proficiency_order = [
                                    'below basic', 'basic', 'approaching', 'proficient', 'advanced', 'exceeds',
                                    'level 1', 'level 2', 'level 3', 'level 4', 'level 5',
                                    'novice', 'developing', 'proficient', 'distinguished',
                                    'far below basic', 'below basic', 'basic', 'proficient', 'advanced'
                                ]
                                
                                # Sort proficiency data by order
                                def get_proficiency_index(level):
                                    level_lower = str(level).lower()
                                    for i, order_level in enumerate(proficiency_order):
                                        if order_level in level_lower:
                                            return i
                                    return 999  # Unknown levels go to end
                                
                                proficiency_data.sort(key=lambda x: get_proficiency_index(x['Proficiency Level']))
                                
                                # Get ordered list of proficiency levels
                                ordered_levels = [item['Proficiency Level'] for item in proficiency_data]
                                
                                # Create chart similar to equity comparison
                                chart_data = []
                                for item in proficiency_data:
                                    chart_data.append({
                                        'Proficiency Level': item['Proficiency Level'],
                                        'Student Count': item['Tutored'],
                                        'Status': 'Tutored'
                                    })
                                    chart_data.append({
                                        'Proficiency Level': item['Proficiency Level'],
                                        'Student Count': item['Untutored'],
                                        'Status': 'Untutored'
                                    })
                                
                                chart_df = pd.DataFrame(chart_data)
                                
                                fig = px.bar(
                                    chart_df,
                                    x='Proficiency Level',
                                    y='Student Count',
                                    color='Status',
                                    barmode='group',
                                    labels={'Student Count': 'Number of Students', 'Proficiency Level': 'Proficiency Level'},
                                    title=f'Number of Tutored vs Untutored Students by {perf_col.replace("_", " ").title()}',
                                    color_discrete_map={
                                        'Tutored': '#36A2EB',
                                        'Untutored': '#FF6384'
                                    },
                                    category_orders={'Proficiency Level': ordered_levels}
                                )
                                fig.update_layout(height=400)
                                st.plotly_chart(fig, use_container_width=True)
                        except Exception as e:
                            st.info(f"Proficiency analysis by {perf_col} unavailable.")
                    
                    # Test Score Analysis - Line chart showing averaged likelihood by score
                    st.markdown("#### Likelihood of Receiving Tutoring by Test Score")
                    
                    ela_likelihood = []
                    math_likelihood = []
                    
                    # ELA Score Analysis
                    if 'ela_state_score_current_year' in equity_df.columns:
                        try:
                            ela_scores = pd.to_numeric(equity_df['ela_state_score_current_year'], errors='coerce')
                            equity_df['ela_score'] = ela_scores
                            
                            # Create bins for smoothing
                            score_range = ela_scores.dropna()
                            if len(score_range) > 0:
                                min_score = score_range.min()
                                max_score = score_range.max()
                                
                                # Create bins (20 bins across the range)
                                bins = np.linspace(min_score, max_score, 21)
                                equity_df['ela_score_bin'] = pd.cut(ela_scores, bins=bins, include_lowest=True)
                                
                                # Calculate likelihood for each bin
                                for bin_val in equity_df['ela_score_bin'].dropna().unique():
                                    bin_data = equity_df[equity_df['ela_score_bin'] == bin_val]
                                    total = len(bin_data)
                                    if total >= 5:  # Only include bins with at least 5 students
                                        tutored = bin_data['received_tutoring'].sum()
                                        pct_tutored = (tutored / total * 100) if total > 0 else 0
                                        bin_mid = bin_val.mid
                                        
                                        ela_likelihood.append({
                                            'Score': bin_mid,
                                            'Likelihood (%)': pct_tutored,
                                            'N': total
                                        })
                        except Exception:
                            pass
                    
                    # Math Score Analysis
                    if 'math_state_score_current_year' in equity_df.columns:
                        try:
                            math_scores = pd.to_numeric(equity_df['math_state_score_current_year'], errors='coerce')
                            equity_df['math_score'] = math_scores
                            
                            # Create bins for smoothing
                            score_range = math_scores.dropna()
                            if len(score_range) > 0:
                                min_score = score_range.min()
                                max_score = score_range.max()
                                
                                # Create bins (20 bins across the range)
                                bins = np.linspace(min_score, max_score, 21)
                                equity_df['math_score_bin'] = pd.cut(math_scores, bins=bins, include_lowest=True)
                                
                                # Calculate likelihood for each bin
                                for bin_val in equity_df['math_score_bin'].dropna().unique():
                                    bin_data = equity_df[equity_df['math_score_bin'] == bin_val]
                                    total = len(bin_data)
                                    if total >= 5:  # Only include bins with at least 5 students
                                        tutored = bin_data['received_tutoring'].sum()
                                        pct_tutored = (tutored / total * 100) if total > 0 else 0
                                        bin_mid = bin_val.mid
                                        
                                        math_likelihood.append({
                                            'Score': bin_mid,
                                            'Likelihood (%)': pct_tutored,
                                            'N': total
                                        })
                        except Exception:
                            pass
                    
                    # Combine ELA and Math into averaged line
                    if ela_likelihood or math_likelihood:
                        # Create a combined score range
                        all_scores = []
                        if ela_likelihood:
                            all_scores.extend([item['Score'] for item in ela_likelihood])
                        if math_likelihood:
                            all_scores.extend([item['Score'] for item in math_likelihood])
                        
                        if all_scores:
                            # Create unified bins across the full score range
                            min_score = min(all_scores)
                            max_score = max(all_scores)
                            unified_bins = np.linspace(min_score, max_score, 21)
                            
                            # Map each subject's data to unified bins
                            combined_likelihood = {}
                            
                            for subject_data, subject_name in [(ela_likelihood, 'ELA'), (math_likelihood, 'Math')]:
                                if subject_data:
                                    for item in subject_data:
                                        score = item['Score']
                                        # Find the closest unified bin
                                        bin_idx = np.digitize(score, unified_bins) - 1
                                        bin_idx = max(0, min(bin_idx, len(unified_bins) - 2))
                                        bin_center = (unified_bins[bin_idx] + unified_bins[bin_idx + 1]) / 2
                                        
                                        if bin_center not in combined_likelihood:
                                            combined_likelihood[bin_center] = {'likelihoods': [], 'counts': []}
                                        
                                        combined_likelihood[bin_center]['likelihoods'].append(item['Likelihood (%)'])
                                        combined_likelihood[bin_center]['counts'].append(item['N'])
                            
                            # Calculate averaged likelihood for each bin
                            averaged_data = []
                            for score in sorted(combined_likelihood.keys()):
                                data = combined_likelihood[score]
                                if len(data['likelihoods']) > 0:
                                    avg_likelihood = np.mean(data['likelihoods'])
                                    total_n = sum(data['counts'])
                                    averaged_data.append({
                                        'Score': score,
                                        'Likelihood (%)': avg_likelihood,
                                        'N': total_n
                                    })
                            
                            if averaged_data:
                                avg_df = pd.DataFrame(averaged_data)
                                avg_df = avg_df.sort_values('Score')
                                
                                fig = go.Figure()
                                fig.add_trace(go.Scatter(
                                    x=avg_df['Score'],
                                    y=avg_df['Likelihood (%)'],
                                    mode='lines+markers',
                                    name='Average (ELA & Math)',
                                    line=dict(width=2),
                                    marker=dict(size=4),
                                    text=avg_df['N'],
                                    hovertemplate='<b>Average (ELA & Math)</b><br>Score: %{x}<br>Likelihood: %{y:.1f}%<br>N: %{text}<extra></extra>'
                                ))
                                
                                fig.update_layout(
                                    title='Likelihood of Receiving Tutoring by Most Recent Test Score (Averaged)',
                                    xaxis_title='Test Score',
                                    yaxis_title='Likelihood of Receiving Tutoring (%)',
                                    height=400,
                                    hovermode='x unified'
                                )
                                st.plotly_chart(fig, use_container_width=True)
                            else:
                                st.info("Test score analysis requires current year test score columns.")
                        else:
                            st.info("Test score analysis requires current year test score columns.")
                    else:
                        st.info("Test score analysis requires current year test score columns.")
                        
                except Exception as e:
                    st.info(f"Proficiency analysis unavailable: {str(e)}")
    
    # ========================================================================
    # OUTCOMES TAB
    # ========================================================================
    with tab_outcomes:
        if st.session_state['session_data'] is None or st.session_state['student_data'] is None:
            st.warning("Please load data in the Data Overview tab first.")
        else:
            show_data_quality_warning()
            st.header("Outcomes Analysis")
            st.caption("Examining student achievement gains")
            
            # Prepare data
            prepared_df = prepare_data(
                st.session_state['session_data'],
                st.session_state['student_data']
            )
            
            # Filters
            with st.expander("🔍 Filters", expanded=False):
                col1, col2 = st.columns(2)
                
                with col1:
                    outcome_school = st.selectbox(
                        "School",
                        ['All'] + sorted(prepared_df['school_name'].dropna().unique().tolist()) if 'school_name' in prepared_df.columns else ['All'],
                        key='outcome_school'
                    )
                    outcome_grades = st.multiselect(
                        "Grade Levels",
                        sorted(prepared_df['current_grade_level'].dropna().unique().tolist()),
                        default=sorted(prepared_df['current_grade_level'].dropna().unique().tolist()),
                        key='outcome_grades'
                    )
                
                with col2:
                    outcome_ell = st.selectbox("ELL Status", ['All', 'ELL Only', 'Non-ELL Only'], key='outcome_ell')
                    outcome_iep = st.selectbox("IEP Status", ['All', 'IEP Only', 'Non-IEP Only'], key='outcome_iep')
            
            # Apply filters
            outcome_df = prepared_df.copy()
            
            if outcome_school != 'All':
                outcome_df = outcome_df[outcome_df['school_name'] == outcome_school]
            
            outcome_df = outcome_df[outcome_df['current_grade_level'].isin(outcome_grades)]
            
            if outcome_ell == 'ELL Only':
                outcome_df = outcome_df[outcome_df.get('ell', pd.Series([False] * len(outcome_df))) == True]
            elif outcome_ell == 'Non-ELL Only':
                outcome_df = outcome_df[outcome_df.get('ell', pd.Series([False] * len(outcome_df))) == False]
            
            if outcome_iep == 'IEP Only':
                outcome_df = outcome_df[outcome_df.get('iep', pd.Series([False] * len(outcome_df))) == True]
            elif outcome_iep == 'Non-IEP Only':
                outcome_df = outcome_df[outcome_df.get('iep', pd.Series([False] * len(outcome_df))) == False]
            
            st.info(f"📊 Analyzing **{len(outcome_df):,} students**")
            
            if len(outcome_df) == 0:
                st.warning("No students match the selected filters.")
            else:
                # Calculate outcome metrics
                outcome_metrics = calculate_outcome_metrics(outcome_df)
                
                # Overall Outcomes Summary
                st.markdown("### Overall Outcomes Summary")
                overall_col1, overall_col2, overall_col3 = st.columns(3)
                
                with overall_col1:
                    avg_va = (outcome_metrics.get('ela_va_mean', 0) + outcome_metrics.get('math_va_mean', 0)) / 2
                    st.metric(
                        "Average Value-Added",
                        f"{avg_va:+.2f} points",
                        help="Average value-added across ELA and Math"
                    )
                
                with overall_col2:
                    ela_es = outcome_metrics.get('ela_va_effect_size') or 0
                    math_es = outcome_metrics.get('math_va_effect_size') or 0
                    if ela_es > 0 or math_es > 0:
                        avg_effect_size = (ela_es + math_es) / 2
                        st.metric(
                            "Average Effect Size",
                            f"{avg_effect_size:+.3f} SD",
                            help="Average standardized effect size across ELA and Math"
                        )
                    else:
                        st.metric("Average Effect Size", "N/A")
                
                with overall_col3:
                    ela_weeks = outcome_metrics.get('ela_va_weeks_learning') or 0
                    math_weeks = outcome_metrics.get('math_va_weeks_learning') or 0
                    if ela_weeks > 0 or math_weeks > 0:
                        avg_weeks = (ela_weeks + math_weeks) / 2
                        st.metric(
                            "Estimated Additional Weeks",
                            f"{avg_weeks:.1f} weeks",
                            help="Average estimated additional weeks of learning"
                        )
                    else:
                        st.metric("Estimated Additional Weeks", "N/A")
                
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
                        help="Formula: VA = (Current - Prior) - (Prior - Two Years Ago)\n\nAverage improvement beyond typical yearly change. Positive values indicate growth exceeding historical patterns."
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
                            help="Formula: Effect Size = Mean Value-Added / Standard Deviation\n\nStandardized effect size (Cohen's d) showing the magnitude of improvement in standard deviations. Values > 0.2 are considered meaningful."
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
                            help="Formula: Weeks = Effect Size × 4.3\n\nEstimated additional months/weeks of learning based on standardized effect size. Assumes ~0.1 SD per month of learning."
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
                        help="Formula: Raw Gain = Current Year Score - Two Years Ago Score\n\nAverage raw score improvement from two years ago to current year."
                    )
                
                with ela_raw_col2:
                    raw_positive = outcome_metrics.get('ela_raw_positive_pct', 0)
                    st.metric(
                        "% with Positive Gain",
                        f"{raw_positive:.1f}%",
                        help="Percentage of students who showed improvement from two years ago"
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
                        help="Formula: VA = (Current - Prior) - (Prior - Two Years Ago)\n\nAverage improvement beyond typical yearly change. Positive values indicate growth exceeding historical patterns."
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
                            help="Formula: Effect Size = Mean Value-Added / Standard Deviation\n\nStandardized effect size (Cohen's d) showing the magnitude of improvement in standard deviations. Values > 0.2 are considered meaningful."
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
                            help="Formula: Weeks = Effect Size × 4.3\n\nEstimated additional months/weeks of learning based on standardized effect size. Assumes ~0.1 SD per month of learning."
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
                        help="Formula: Raw Gain = Current Year Score - Two Years Ago Score\n\nAverage raw score improvement from two years ago to current year."
                    )
                
                with math_raw_col2:
                    raw_positive = outcome_metrics.get('math_raw_positive_pct', 0)
                    st.metric(
                        "% with Positive Gain",
                        f"{raw_positive:.1f}%",
                        help="Percentage of students who showed improvement from two years ago"
                    )
                
                # Interpretation
                if va_mean < 1:
                    st.warning("⚠️ **Note:** Average value-added is less than 1 point. This suggests limited improvement beyond typical growth patterns.")
                elif va_mean >= 1:
                    st.success("✓ **Directionally positive:** Average value-added indicates improvement beyond typical growth.")
                
                # Math distributions
                plot_outcome_distributions(outcome_df, 'Math')
                
                # Important note
                st.markdown("---")
                st.info("""
                **Important:** These results are descriptive and do not establish causality. 
                Value-added calculations compare current growth to historical growth patterns, 
                but many factors beyond tutoring may influence outcomes.
                """)
    
    # ========================================================================
    # COST ANALYTICS TAB
    # ========================================================================
    with tab_cost:
        if st.session_state['session_data'] is None or st.session_state['student_data'] is None:
            st.warning("Please load data in the Data Overview tab first.")
        else:
            show_data_quality_warning()
            st.header("Cost Analytics")
            st.caption("Understanding program costs relative to outcomes")
            
            if st.session_state['total_cost'] == 0:
                st.warning("⚠️ Total program cost is set to $0. Please set the cost in the sidebar to view cost-effectiveness metrics.")
            
            # Prepare data
            prepared_df = prepare_data(
                st.session_state['session_data'],
                st.session_state['student_data']
            )
            
            # Filters
            with st.expander("🔍 Filters", expanded=False):
                cost_school = st.selectbox(
                    "School",
                    ['All'] + sorted(prepared_df['school_name'].dropna().unique().tolist()) if 'school_name' in prepared_df.columns else ['All'],
                    key='cost_school'
                )
                cost_grades = st.multiselect(
                    "Grade Levels",
                    sorted(prepared_df['current_grade_level'].dropna().unique().tolist()),
                    default=sorted(prepared_df['current_grade_level'].dropna().unique().tolist()),
                    key='cost_grades'
                )
            
            # Apply filters
            cost_df = prepared_df.copy()
            
            if cost_school != 'All':
                cost_df = cost_df[cost_df['school_name'] == cost_school]
            
            cost_df = cost_df[cost_df['current_grade_level'].isin(cost_grades)]
            
            st.info(f"📊 Analyzing **{len(cost_df):,} students**")
            
            if len(cost_df) == 0:
                st.warning("No students match the selected filters.")
            else:
                # Calculate cost metrics
                cost_metrics = calculate_cost_metrics(
                    cost_df,
                    st.session_state['total_cost'],
                    st.session_state['full_dosage_threshold']
                )
                
                # Basic cost metrics
                st.markdown("### Basic Cost Metrics")
                cost_col1, cost_col2 = st.columns(2)
                
                with cost_col1:
                    st.metric(
                        "Cost per Student",
                        f"${cost_metrics.get('cost_per_student', 0):,.2f}",
                        help="Formula: Total Cost / Number of Students\n\nThis metric represents the average cost allocated for each student in the program."
                    )
                
                with cost_col2:
                    st.metric(
                        "Cost per Tutoring Hour",
                        f"${cost_metrics.get('cost_per_hour', 0):,.2f}",
                        help="Formula: Total Cost / Total Tutoring Hours Delivered\n\nThis metric shows the cost per hour of tutoring delivered across all students."
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
                            help="Formula: Total Cost / Sum of All Value-Added Points\n\nValue-Added = (Current - Prior) - (Prior - Two Years Ago)\n\nThis metric shows the cost for each point of value-added improvement across all students."
                        )
                    else:
                        st.metric(
                            "Cost per Value-Added Point",
                            "N/A",
                            help="Cannot calculate: total value-added points is not positive"
                        )
                
                with outcome_col2:
                    cost_per_raw = cost_metrics.get('cost_per_raw_point')
                    if cost_per_raw is not None:
                        st.metric(
                            "Cost per Raw Point Gained",
                            f"${cost_per_raw:,.2f}",
                            help="Formula: Total Cost / Sum of All Raw Gain Points\n\nRaw Gain = Current Year Score - Two Years Ago Score\n\nThis metric shows the cost for each point of raw score improvement across all students."
                        )
                    else:
                        st.metric(
                            "Cost per Raw Point Gained",
                            "N/A",
                            help="Cannot calculate: total raw gain points is not positive"
                        )

    # Footer caveat
    st.markdown("---")
    st.caption("This tool requires no data upload. Please feel free to run this tool [locally](https://github.com/accelerate-usa/tutor-data-standard/tree/main/toolkit). If you use this tool as is, all data are erased upon refresh.")


if __name__ == "__main__":
    main()

