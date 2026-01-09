#%%
"""
Combined Dataset Generator for Tutoring Research Data

This script generates two CSV files:
1. student_data.csv - Student-level data with demographics and test scores
2. session_data.csv - Session-level tutoring data

Key features:
- Students who received tutoring show configurable SD more learning than control
- Dosage follows a right-skewed Gaussian (log-normal) distribution
- Subgroup-specific enrollment rates and treatment effects
- Implementation fidelity variability by school or provider
- Fully configurable parameters
"""

import random
import string
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# =============================================================================
# CONFIGURABLE PARAMETERS - Adjust these to customize the generated data
# =============================================================================

CONFIG = {
    # Student counts
    "num_students": 10000,              # Total number of students
    "treatment_proportion": 0.5,        # Base proportion receiving tutoring
    
    # Dosage parameters (for tutored students)
    "dosage_median_hours": 55,          # Median total hours of tutoring
    "dosage_skew": 0.4,                 # Log-normal sigma (higher = more right skew)
    "dosage_min_hours": 5,              # Minimum hours (floor)
    "dosage_max_hours": 150,            # Maximum hours (ceiling)
    
    # Session parameters
    "session_duration_mean": 60,        # Mean session duration in minutes
    "session_duration_std": 15,         # Std dev of session duration
    
    # Treatment effect
    "treatment_effect_sd": 0.25,        # Base treatment effect in standard deviations
    
    # Baseline score parameters
    "baseline_score_mean": 725,         # Mean baseline test score
    "baseline_score_std": 30,           # Std dev of baseline test score
    "score_min": 650,                   # Minimum possible score
    "score_max": 800,                   # Maximum possible score
    
    # Natural growth (for control group)
    "natural_growth_mean": 10,          # Mean score growth without tutoring
    "natural_growth_std": 15,           # Std dev of natural growth
    
    # =========================================================================
    # SUBGROUP-SPECIFIC EFFECTS
    # =========================================================================
    # Each subgroup can have:
    #   - enrollment_multiplier: multiplier on base treatment_proportion (1.2 = 20% more likely)
    #   - effect_multiplier: multiplier on treatment effect (1.1 = 10% larger effect)
    # 
    # Set to 1.0 for no effect, or omit the subgroup entirely
    "subgroup_effects": {
        "ell": {
            "enrollment_multiplier": 1.2,   # ELL students 20% more likely to be tutored
            "effect_multiplier": 1.1,       # ELL students benefit 10% more
        },
        "iep": {
            "enrollment_multiplier": 1.1,   # IEP students 10% more likely
            "effect_multiplier": 1.0,       # Same effect as general population
        },
        "economic_disadvantage": {
            "enrollment_multiplier": 1.15,  # 15% more likely
            "effect_multiplier": 1.0,
        },
        "gifted_flag": {
            "enrollment_multiplier": 0.8,   # 20% less likely
            "effect_multiplier": 0.9,       # 10% smaller effect
        },
        "homeless_flag": {
            "enrollment_multiplier": 1.3,   # 30% more likely
            "effect_multiplier": 0.95,      # Slightly smaller effect
        },
        "disability": {
            "enrollment_multiplier": 1.1,
            "effect_multiplier": 1.0,
        },
    },
    
    # =========================================================================
    # IMPLEMENTATION FIDELITY VARIABILITY
    # =========================================================================
    # Controls how consistent implementation is across schools/providers
    #
    # vary_by: "school", "provider", or "none"
    #   - "school": Each school has its own fidelity level
    #   - "provider": Each tutor has their own fidelity level  
    #   - "none": All implementation is equally consistent
    #
    # between_variability: How much schools/providers differ from each other (0-1)
    #   - 0.0 = all schools/providers are identical
    #   - 0.5 = moderate differences between schools/providers
    #   - 1.0 = large differences between schools/providers
    #
    # This affects: session duration consistency, dosage completion rates
    "implementation_fidelity": {
        "vary_by": "school",            # "school", "provider", or "none"
        "between_variability": 0.3,     # How different schools/providers are from each other
    },
    
    # Number of schools and providers
    "num_schools": 10,
    "num_providers": 5,                 # Tutoring organizations/providers
    
    # =========================================================================
    # SESSION SUBJECT DISTRIBUTION BY GRADE
    # =========================================================================
    # Define what percentage of sessions are math vs ela for each grade range
    # Format: { (min_grade, max_grade): {"math": prob, "ela": prob} }
    # Probabilities should sum to 1.0
    # Grades not covered default to 50/50
    "subject_by_grade": {
        (-1, 3): {"math": 0.80, "ela": 0.20},   # Pre-K to 3rd: 80% math
        (4, 5):  {"math": 0.60, "ela": 0.40},   # 4th-5th: 60% math
        (6, 8):  {"math": 0.50, "ela": 0.50},   # Middle school: 50/50
        (9, 12): {"math": 0.55, "ela": 0.45},   # High school: 55% math
    },
    
    # =========================================================================
    # SESSION TIME CONSTRAINTS
    # =========================================================================
    # Sessions occur during school hours
    "session_hours": {
        "start_hour": 9,    # 9 AM
        "end_hour": 15,     # 3 PM (15:00)
    },
    
    # Missing data
    "add_missing_data": False,          # Whether to add missing values
    "missing_percentage_range": (5, 15),# Range of missing data percentage per column
    
    # Output files
    "student_data_file": "example_student_data.csv",
    "session_data_file": "example_session_data.csv",
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def generate_student_id(used_ids):
    """Generate a unique 10-digit student ID."""
    while True:
        student_id = ''.join(random.choices(string.digits, k=10))
        if student_id not in used_ids:
            used_ids.add(student_id)
            return student_id


def generate_tutor_id():
    """Generate a tutor ID (T + 5 digits)."""
    return 'T' + ''.join(random.choices(string.digits, k=5))


def generate_skewed_dosage(n, median_hours, sigma, min_hours, max_hours):
    """
    Generate right-skewed dosage distribution using log-normal.
    """
    mu = np.log(median_hours)
    dosage = np.random.lognormal(mean=mu, sigma=sigma, size=n)
    dosage = np.clip(dosage, min_hours, max_hours)
    return dosage


def random_date(start, end):
    """Generate a random date between start and end."""
    delta = end - start
    random_days = random.randint(0, delta.days)
    return start + timedelta(days=random_days)


def random_datetime_school_hours(start_date, end_date, start_hour=9, end_hour=15):
    """
    Generate a random datetime between start_date and end_date,
    constrained to school hours (e.g., 9am-3pm).
    
    Returns: datetime object
    """
    # Pick a random date
    delta = end_date - start_date
    random_days = random.randint(0, delta.days)
    session_date = start_date + timedelta(days=random_days)
    
    # Pick a random time within school hours
    # start_hour to end_hour, random minute
    hour = random.randint(start_hour, end_hour - 1)  # -1 because session needs time to complete
    minute = random.randint(0, 59)
    
    return datetime.combine(session_date, datetime.min.time().replace(hour=hour, minute=minute))


def get_subject_for_grade(grade, subject_by_grade):
    """
    Select a session subject based on the student's grade level.
    
    Parameters:
    - grade: student's current grade level (-1 to 12)
    - subject_by_grade: dict mapping (min_grade, max_grade) to {"math": prob, "ela": prob}
    
    Returns: "math" or "ela"
    """
    # Find the matching grade range
    for (min_grade, max_grade), probs in subject_by_grade.items():
        if min_grade <= grade <= max_grade:
            # Weighted random choice
            if random.random() < probs.get("math", 0.5):
                return "math"
            else:
                return "ela"
    
    # Default to 50/50 if no range matches
    return random.choice(["math", "ela"])


def add_missing_data(df, missing_percentage_range=(10, 50), exclude_cols=None):
    """Add missing values to a dataframe."""
    exclude_cols = exclude_cols or []
    df = df.copy()
    for col in df.columns:
        if col in exclude_cols:
            continue
        missing_percentage = random.randint(*missing_percentage_range)
        num_missing = int(len(df) * missing_percentage / 100)
        if num_missing > 0:
            missing_indices = random.sample(range(len(df)), num_missing)
            df.loc[missing_indices, col] = np.nan
    return df


def calculate_enrollment_probability(base_prob, student_flags, subgroup_effects):
    """
    Calculate enrollment probability based on student characteristics.
    
    Uses multiplicative adjustment: P = base * product(multipliers for TRUE flags)
    Capped at 0.95 to avoid certainty.
    """
    prob = base_prob
    
    for flag_name, effects in subgroup_effects.items():
        if student_flags.get(flag_name) == 'TRUE':
            prob *= effects.get('enrollment_multiplier', 1.0)
    
    return min(prob, 0.95)


def calculate_effect_multiplier(student_flags, subgroup_effects):
    """
    Calculate treatment effect multiplier based on student characteristics.
    
    Uses multiplicative adjustment for students with multiple flags.
    """
    multiplier = 1.0
    
    for flag_name, effects in subgroup_effects.items():
        if student_flags.get(flag_name) == 'TRUE':
            multiplier *= effects.get('effect_multiplier', 1.0)
    
    return multiplier


def generate_school_fidelity_map(school_ids, between_variability):
    """
    Generate a fidelity score for each school.
    
    Returns dict mapping school_id to fidelity_score (0.5 to 1.5 range).
    Higher variability = larger differences between schools.
    """
    fidelity_map = {}
    for school_id in school_ids:
        # Fidelity centered at 1.0, with variability determining spread
        fidelity = np.random.normal(1.0, between_variability * 0.3)
        fidelity = np.clip(fidelity, 0.5, 1.5)  # Keep within reasonable bounds
        fidelity_map[school_id] = fidelity
    return fidelity_map


def generate_provider_fidelity_map(tutor_ids, between_variability):
    """
    Generate a fidelity score for each tutor/provider.
    """
    fidelity_map = {}
    for tutor_id in tutor_ids:
        fidelity = np.random.normal(1.0, between_variability * 0.3)
        fidelity = np.clip(fidelity, 0.5, 1.5)
        fidelity_map[tutor_id] = fidelity
    return fidelity_map


# =============================================================================
# MAIN GENERATION FUNCTIONS
# =============================================================================

def generate_student_data(config):
    """
    Generate student-level data with demographics and test scores.
    
    Treatment assignment is based on:
    - Base treatment proportion
    - Subgroup-specific enrollment multipliers
    
    Treatment effect is modified by:
    - Base treatment effect
    - Subgroup-specific effect multipliers
    
    Returns: tuple of (students_list, treatment_info, school_assignments)
    """
    
    num_students = config["num_students"]
    base_treatment_prop = config["treatment_proportion"]
    base_effect_sd = config["treatment_effect_sd"]
    subgroup_effects = config.get("subgroup_effects", {})
    num_schools = config.get("num_schools", 10)
    
    # Define categorical options
    boolean_values = ['TRUE', 'FALSE']
    ethnicities = [
        'White', 'Black or African American', 'Hispanic or Latino',
        'Asian', 'American Indian or Alaska Native', 
        'Native Hawaiian or Pacific Islander', 'Two or More Races',
        'Other', 'Unknown', 'Declined to State'
    ]
    performance_levels = ['Below Basic', 'Basic', 'Proficient', 'Advanced', 'Distinguished', 'Exceeds']
    district_names = [
        'Denver Public Schools', 'Aurora Public Schools', 'Jefferson County Schools',
        'Cherry Creek School District', 'Douglas County School District'
    ]
    school_names = [
        'Washington Elementary', 'Lincoln Middle School', 'Roosevelt High School',
        'Kennedy Academy', 'Jefferson STEM School', 'Madison Preparatory',
        'Franklin Learning Center', 'Adams Elementary', 'Monroe Middle School',
        'Hamilton High School'
    ]
    leaids = ['0100001', '0200001', '0400001', '0500001', '0600001', 
              '0800001', '0900001', '1000001', '1100001', '1200001']
    
    # Pre-generate school IDs
    school_ids = [''.join(random.choices(string.digits, k=6)) for _ in range(num_schools)]
    
    used_student_ids = set()
    students = []
    treatment_info = {}
    school_assignments = {}  # student_id -> school_id
    
    for i in range(num_students):
        student_id = generate_student_id(used_student_ids)
        
        # Assign to a school
        school_id = random.choice(school_ids)
        school_assignments[student_id] = school_id
        
        # Generate demographic flags FIRST (needed for enrollment decision)
        student_flags = {
            "ell": random.choice(boolean_values),
            "iep": random.choice(boolean_values),
            "gifted_flag": random.choice(boolean_values),
            "homeless_flag": random.choice(boolean_values),
            "disability": random.choice(boolean_values),
            "economic_disadvantage": random.choice(boolean_values),
        }
        
        # Calculate enrollment probability based on subgroup membership
        enrollment_prob = calculate_enrollment_probability(
            base_treatment_prop, student_flags, subgroup_effects
        )
        is_treated = random.random() < enrollment_prob
        
        # Generate baseline scores
        baseline_mean = config["baseline_score_mean"]
        baseline_std = config["baseline_score_std"]
        score_min = config["score_min"]
        score_max = config["score_max"]
        
        student_ability = np.random.normal(baseline_mean, baseline_std)
        
        ela_two_years = np.clip(
            student_ability + np.random.normal(0, 10), score_min, score_max)
        ela_one_year = np.clip(
            student_ability + np.random.normal(5, 10), score_min, score_max)
        math_two_years = np.clip(
            student_ability + np.random.normal(0, 10), score_min, score_max)
        math_one_year = np.clip(
            student_ability + np.random.normal(5, 10), score_min, score_max)
        
        # Current year scores with treatment effect
        natural_growth = np.random.normal(
            config["natural_growth_mean"], config["natural_growth_std"])
        
        if is_treated:
            # Calculate subgroup-specific effect multiplier
            effect_multiplier = calculate_effect_multiplier(student_flags, subgroup_effects)
            adjusted_effect_sd = base_effect_sd * effect_multiplier
            
            growth_std = config["natural_growth_std"]
            treatment_boost = adjusted_effect_sd * growth_std
            
            # Generate dosage (will be refined in session generation)
            dosage = generate_skewed_dosage(
                1,
                config["dosage_median_hours"],
                config["dosage_skew"],
                config["dosage_min_hours"],
                config["dosage_max_hours"]
            )[0]
            
            ela_current = np.clip(
                ela_one_year + natural_growth + treatment_boost, score_min, score_max)
            math_current = np.clip(
                math_one_year + natural_growth + treatment_boost, score_min, score_max)
            
            # Generate grade level here so we can include in treatment_info
            grade_level = random.randint(-1, 12)
            
            treatment_info[student_id] = {
                'is_treated': True, 
                'dosage': dosage,
                'effect_multiplier': effect_multiplier,
                'flags': student_flags,
                'grade': grade_level
            }
        else:
            ela_current = np.clip(
                ela_one_year + natural_growth, score_min, score_max)
            math_current = np.clip(
                math_one_year + natural_growth, score_min, score_max)
            
            # Generate grade level here so we can include in treatment_info
            grade_level = random.randint(-1, 12)
            
            treatment_info[student_id] = {
                'is_treated': False, 
                'dosage': 0,
                'effect_multiplier': 0,
                'flags': student_flags,
                'grade': grade_level
            }
        
        # Performance levels based on scores
        def score_to_level(score):
            if score < 680: return 'Below Basic'
            elif score < 710: return 'Basic'
            elif score < 740: return 'Proficient'
            elif score < 770: return 'Advanced'
            elif score < 790: return 'Distinguished'
            else: return 'Exceeds'
        
        perf_prior = score_to_level((ela_one_year + math_one_year) / 2)
        perf_current = score_to_level((ela_current + math_current) / 2)
        
        # Build student record
        student = {
            "student_id": student_id,
            "district_id": random.choice(leaids),
            "district_name": random.choice(district_names),
            "school_id": school_id,
            "school_name": random.choice(school_names),
            "current_grade_level": grade_level,
            "gender": random.choice(boolean_values),
            "ethnicity": random.choice(ethnicities),
            "ell": student_flags["ell"],
            "iep": student_flags["iep"],
            "gifted_flag": student_flags["gifted_flag"],
            "homeless_flag": student_flags["homeless_flag"],
            "disability": student_flags["disability"],
            "economic_disadvantage": student_flags["economic_disadvantage"],
            "ela_state_score_two_years_ago": int(ela_two_years),
            "ela_state_score_one_year_ago": int(ela_one_year),
            "ela_state_score_current_year": int(ela_current),
            "math_state_score_two_years_ago": int(math_two_years),
            "math_state_score_one_year_ago": int(math_one_year),
            "math_state_score_current_year": int(math_current),
            "performance_level_prior_year": perf_prior,
            "performance_level_current_year": perf_current,
        }
        students.append(student)
    
    return students, treatment_info, school_assignments


def generate_session_data(treatment_info, school_assignments, config):
    """
    Generate session-level tutoring data for treated students.
    
    Features:
    - Implementation fidelity affects session consistency and dosage completion
    - Subject distribution varies by grade level
    - Session times constrained to school hours
    """
    
    session_duration_mean = config["session_duration_mean"]
    session_duration_std = config["session_duration_std"]
    fidelity_config = config.get("implementation_fidelity", {})
    vary_by = fidelity_config.get("vary_by", "none")
    between_var = fidelity_config.get("between_variability", 0.0)
    
    # Subject distribution by grade
    subject_by_grade = config.get("subject_by_grade", {})
    
    # Session time constraints
    session_hours = config.get("session_hours", {"start_hour": 9, "end_hour": 15})
    start_hour = session_hours.get("start_hour", 9)
    end_hour = session_hours.get("end_hour", 15)
    
    ratios = ['1:1', '1:2', '1:3', '2:1', '1:4', '1:5']
    
    # Date range for sessions (past 180 days, excluding weekends for realism)
    start_date = datetime.now().date() - timedelta(days=180)
    end_date = datetime.now().date()
    
    sessions_data = []
    
    # Generate tutor pool
    num_tutors = config.get("num_providers", 5) * 10  # 10 tutors per provider
    tutor_pool = [generate_tutor_id() for _ in range(num_tutors)]
    
    # Generate fidelity maps
    if vary_by == "school":
        school_ids = list(set(school_assignments.values()))
        fidelity_map = generate_school_fidelity_map(school_ids, between_var)
    elif vary_by == "provider":
        fidelity_map = generate_provider_fidelity_map(tutor_pool, between_var)
    else:
        fidelity_map = {}
    
    for student_id, info in treatment_info.items():
        if not info['is_treated']:
            continue
        
        total_hours = info['dosage']
        student_grade = info.get('grade', 5)  # Default to 5th grade
        school_id = school_assignments.get(student_id)
        
        # Get fidelity score for this student's context
        if vary_by == "school" and school_id:
            fidelity = fidelity_map.get(school_id, 1.0)
        elif vary_by == "provider":
            # Will apply per-tutor fidelity below
            fidelity = 1.0
        else:
            fidelity = 1.0
        
        # Fidelity affects dosage completion (high fidelity = hit target hours)
        # and session consistency (high fidelity = less duration variance)
        dosage_completion_rate = 0.7 + (fidelity - 0.5) * 0.6  # Range: 0.4 to 1.3
        dosage_completion_rate = np.clip(dosage_completion_rate, 0.5, 1.2)
        actual_hours = total_hours * dosage_completion_rate
        
        # Session duration variance scales inversely with fidelity
        duration_std_multiplier = 2.0 - fidelity  # High fidelity = lower multiplier
        adjusted_duration_std = session_duration_std * duration_std_multiplier
        
        # Calculate number of sessions
        avg_session_hours = session_duration_mean / 60
        num_sessions = max(1, int(actual_hours / avg_session_hours))
        
        # Assign primary tutor
        primary_tutor = random.choice(tutor_pool)
        
        remaining_hours = actual_hours
        
        for _ in range(num_sessions):
            if remaining_hours <= 0:
                break
            
            # Select tutor (80% primary, 20% other)
            tutor_id = primary_tutor if random.random() < 0.8 else random.choice(tutor_pool)
            
            # Apply tutor-level fidelity if vary_by == "provider"
            if vary_by == "provider":
                tutor_fidelity = fidelity_map.get(tutor_id, 1.0)
                final_duration_std = session_duration_std * (2.0 - tutor_fidelity)
            else:
                final_duration_std = adjusted_duration_std
            
            # Session duration with fidelity-adjusted variance
            duration = max(15, int(np.random.normal(session_duration_mean, final_duration_std)))
            duration = min(duration, int(remaining_hours * 60))
            remaining_hours -= duration / 60
            
            # Generate session datetime (constrained to school hours)
            session_datetime = random_datetime_school_hours(
                start_date, end_date, start_hour, end_hour
            )
            
            # Select subject based on grade
            subject = get_subject_for_grade(student_grade, subject_by_grade)
            
            sessions_data.append({
                'student_id': student_id,
                'session_topic': subject,
                'session_date': session_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                'session_duration': duration,
                'session_ratio': random.choice(ratios),
                'tutor_id': tutor_id
            })
    
    return sessions_data


def save_student_data(students, filename, add_missing=False, missing_range=(5, 15)):
    """Save student data to CSV."""
    df = pd.DataFrame(students)
    
    string_cols = ['student_id', 'district_id', 'school_id']
    for col in string_cols:
        df[col] = df[col].astype(str)
    
    if add_missing:
        exclude = ['student_id']
        df = add_missing_data(df, missing_range, exclude_cols=exclude)
    
    df.to_csv(filename, index=False)
    print(f"[OK] Student data saved to '{filename}' ({len(df)} students)")
    return df


def save_session_data(session_data, filename, add_missing=False, missing_range=(5, 15)):
    """Save session data to CSV."""
    df = pd.DataFrame(session_data)
    
    if add_missing:
        exclude = ['student_id', 'tutor_id', 'session_date']
        df = add_missing_data(df, missing_range, exclude_cols=exclude)
    
    df.to_csv(filename, index=False)
    print(f"[OK] Session data saved to '{filename}' ({len(df)} sessions)")
    return df


def print_summary(students_df, sessions_df, treatment_info, config):
    """Print summary statistics of generated data."""
    
    print("\n" + "="*70)
    print("GENERATED DATA SUMMARY")
    print("="*70)
    
    # Get treated/control
    treated_ids = [sid for sid, info in treatment_info.items() if info['is_treated']]
    control_ids = [sid for sid, info in treatment_info.items() if not info['is_treated']]
    
    treated = students_df[students_df['student_id'].isin(treated_ids)]
    control = students_df[students_df['student_id'].isin(control_ids)]
    
    print(f"\n[STUDENTS]")
    print(f"   Total students:    {len(students_df):,}")
    print(f"   Treated (tutored): {len(treated):,} ({100*len(treated)/len(students_df):.1f}%)")
    print(f"   Control:           {len(control):,} ({100*len(control)/len(students_df):.1f}%)")
    
    # Subgroup enrollment rates
    subgroup_effects = config.get("subgroup_effects", {})
    if subgroup_effects:
        print(f"\n[SUBGROUP ENROLLMENT RATES]")
        for flag in ['ell', 'iep', 'economic_disadvantage', 'gifted_flag', 'homeless_flag', 'disability']:
            if flag in students_df.columns:
                flag_students = students_df[students_df[flag] == 'TRUE']
                flag_treated = flag_students[flag_students['student_id'].isin(treated_ids)]
                if len(flag_students) > 0:
                    rate = 100 * len(flag_treated) / len(flag_students)
                    expected_mult = subgroup_effects.get(flag, {}).get('enrollment_multiplier', 1.0)
                    print(f"   {flag:25s}: {rate:5.1f}% tutored (multiplier: {expected_mult:.2f})")
    
    # Dosage summary
    dosages = [info['dosage'] for info in treatment_info.values() if info['is_treated']]
    dosage_series = pd.Series(dosages)
    
    print(f"\n[DOSAGE] (treated students only)")
    print(f"   Median hours:  {dosage_series.median():.1f}")
    print(f"   Mean hours:    {dosage_series.mean():.1f}")
    print(f"   Std dev:       {dosage_series.std():.1f}")
    print(f"   Min:           {dosage_series.min():.1f}")
    print(f"   Max:           {dosage_series.max():.1f}")
    
    # Learning outcomes
    print(f"\n[LEARNING OUTCOMES] (ELA score change from prior year)")
    treated_growth = treated['ela_state_score_current_year'] - treated['ela_state_score_one_year_ago']
    control_growth = control['ela_state_score_current_year'] - control['ela_state_score_one_year_ago']
    
    pooled_std = np.sqrt((treated_growth.std()**2 + control_growth.std()**2) / 2)
    effect_size = (treated_growth.mean() - control_growth.mean()) / pooled_std
    
    print(f"   Treated mean growth: {treated_growth.mean():.2f} (SD: {treated_growth.std():.2f})")
    print(f"   Control mean growth: {control_growth.mean():.2f} (SD: {control_growth.std():.2f})")
    print(f"   Effect size (Cohen's d): {effect_size:.3f}")
    print(f"   Target effect size:      {config['treatment_effect_sd']:.3f}")
    
    # Subgroup effect sizes
    if subgroup_effects:
        print(f"\n[SUBGROUP EFFECT SIZES] (ELA growth, treated vs control)")
        for flag in ['ell', 'iep', 'economic_disadvantage']:
            if flag in students_df.columns:
                flag_treated = treated[treated[flag] == 'TRUE']
                flag_control = control[control[flag] == 'TRUE']
                if len(flag_treated) > 50 and len(flag_control) > 50:
                    t_growth = flag_treated['ela_state_score_current_year'] - flag_treated['ela_state_score_one_year_ago']
                    c_growth = flag_control['ela_state_score_current_year'] - flag_control['ela_state_score_one_year_ago']
                    p_std = np.sqrt((t_growth.std()**2 + c_growth.std()**2) / 2)
                    if p_std > 0:
                        es = (t_growth.mean() - c_growth.mean()) / p_std
                        expected_mult = subgroup_effects.get(flag, {}).get('effect_multiplier', 1.0)
                        print(f"   {flag:25s}: d = {es:.3f} (effect mult: {expected_mult:.2f})")
    
    # Session/fidelity summary
    print(f"\n[SESSIONS]")
    print(f"   Total sessions: {len(sessions_df):,}")
    print(f"   Avg per student: {len(sessions_df)/len(treated):.1f}")
    
    # Subject distribution by grade
    print(f"\n[SUBJECT DISTRIBUTION BY GRADE]")
    # Merge session data with student grades
    student_grades = {sid: info['grade'] for sid, info in treatment_info.items()}
    sessions_with_grade = sessions_df.copy()
    sessions_with_grade['grade'] = sessions_with_grade['student_id'].map(student_grades)
    
    grade_ranges = [(-1, 3), (4, 5), (6, 8), (9, 12)]
    for min_g, max_g in grade_ranges:
        grade_sessions = sessions_with_grade[
            (sessions_with_grade['grade'] >= min_g) & 
            (sessions_with_grade['grade'] <= max_g)
        ]
        if len(grade_sessions) > 0:
            math_pct = 100 * (grade_sessions['session_topic'] == 'math').mean()
            grade_label = f"Grades {min_g}-{max_g}" if min_g >= 0 else f"Pre-K-{max_g}"
            print(f"   {grade_label:15s}: {math_pct:5.1f}% math, {100-math_pct:5.1f}% ela")
    
    # Session time stats
    print(f"\n[SESSION TIMES]")
    try:
        session_times = pd.to_datetime(sessions_df['session_date'])
        hours = session_times.dt.hour
        print(f"   Hour range: {hours.min()}:00 - {hours.max()}:59")
        print(f"   Most common hour: {hours.mode().iloc[0]}:00")
    except:
        print("   (datetime parsing not available)")
    
    fidelity_config = config.get("implementation_fidelity", {})
    vary_by = fidelity_config.get("vary_by", "none")
    between_var = fidelity_config.get("between_variability", 0.0)
    print(f"\n[IMPLEMENTATION FIDELITY]")
    print(f"   Vary by:              {vary_by}")
    print(f"   Between variability:  {between_var:.2f}")
    
    if vary_by in ["school", "provider"]:
        duration_by_group = sessions_df.groupby('student_id')['session_duration'].std()
        print(f"   Session duration SD (within-student): {duration_by_group.mean():.1f} min")
    
    print("\n" + "="*70)


# =============================================================================
# MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    print("Tutoring Data Generator")
    print("-"*40)
    
    print("\nGenerating student data...")
    students, treatment_info, school_assignments = generate_student_data(CONFIG)
    
    print("Generating session data...")
    session_data = generate_session_data(treatment_info, school_assignments, CONFIG)
    
    print("\nSaving files...")
    students_df = save_student_data(
        students, 
        CONFIG["student_data_file"],
        add_missing=CONFIG["add_missing_data"],
        missing_range=CONFIG["missing_percentage_range"]
    )
    
    sessions_df = save_session_data(
        session_data,
        CONFIG["session_data_file"],
        add_missing=CONFIG["add_missing_data"],
        missing_range=CONFIG["missing_percentage_range"]
    )
    
    print_summary(students_df, sessions_df, treatment_info, CONFIG)

# %%
