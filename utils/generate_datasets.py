"""
Combined Dataset Generator for Tutoring Research Data

This script generates two CSV files:
1. student_data.csv - Student-level data with demographics and test scores
2. session_data.csv - Session-level tutoring data

Key features:
- Students who received tutoring show configurable SD more learning than control
- Dosage follows a right-skewed Gaussian (log-normal) distribution
- Dose-response relationship (more hours = larger effect)
- Subgroup-specific enrollment rates and treatment effects
- Implementation fidelity variability by school or provider
- Realistic demographic base rates and ethnicity distributions
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
    # =========================================================================
    # REPRODUCIBILITY
    # =========================================================================
    "random_seed": 42,                  # Set to None for random, or integer for reproducibility
    
    # =========================================================================
    # STUDENT COUNTS
    # =========================================================================
    "num_students": 1000,               # Total number of students
    "treatment_proportion": 0.5,        # Base proportion receiving tutoring
    
    # =========================================================================
    # DOSAGE PARAMETERS (for tutored students)
    # =========================================================================
    "dosage_mean_hours": 45,            # Mean total hours of tutoring
    "dosage_skew": 0.3,                 # Skew intensity (higher = more skewed)
    "dosage_skew_direction": "left",    # "left" (tail low, mass high) or "right" (tail high, mass low)
    "dosage_min_hours": 1,             # Minimum hours (floor)
    "dosage_max_hours": 75,             # Maximum hours (ceiling)
    
    # =========================================================================
    # DOSE-RESPONSE RELATIONSHIP
    # =========================================================================
    # Controls whether more tutoring hours leads to larger treatment effects
    # Without this, all treated students get the same effect regardless of dosage
    "dose_response": {
        "enabled": True,                # If False, effect is constant regardless of dosage
        "type": "logarithmic",          # "linear", "logarithmic", or "threshold"
        "reference_hours": 55,          # Hours at which student gets full treatment_effect_sd
        # For "threshold" type only:
        "threshold_hours": 30,          # Minimum hours to see any effect
    },
    
    # =========================================================================
    # SESSION PARAMETERS
    # =========================================================================
    "session_duration_mean": 60,        # Mean session duration in minutes
    "session_duration_std": 15,         # Std dev of session duration
    "session_date_range_days": 180,     # Sessions occur in past N days
    
    # Session ratio weights (probability of each ratio)
    "session_ratio_weights": {
        "1:1": 0.35,                    # 35% one-on-one
        "1:2": 0.25,                    # 25% pairs
        "1:3": 0.20,                    # 20% small group
        "1:4": 0.12,                    # 12% medium group
        "1:5": 0.08,                    # 8% larger group
    },
    
    # Tutor assignment consistency (probability of same tutor across sessions)
    "tutor_consistency": 0.8,           # 80% chance of same tutor
    
    # =========================================================================
    # TREATMENT EFFECT
    # =========================================================================
    "treatment_effect_sd": 0.25,        # Base treatment effect in standard deviations
    
    # =========================================================================
    # BASELINE SCORE PARAMETERS
    # =========================================================================
    "baseline_score_mean": 725,         # Mean baseline test score
    "baseline_score_std": 30,           # Std dev of baseline test score
    "score_min": 650,                   # Minimum possible score
    "score_max": 800,                   # Maximum possible score
    
    # ELA-Math correlation (how correlated student performance is across subjects)
    # Real data typically shows r ≈ 0.7-0.8
    "ela_math_correlation": 0.75,
    
    # =========================================================================
    # NATURAL GROWTH (for control group)
    # =========================================================================
    "natural_growth_mean": 10,          # Mean score growth without tutoring
    "natural_growth_std": 15,           # Std dev of natural growth
    
    # =========================================================================
    # DEMOGRAPHIC BASE RATES
    # =========================================================================
    # Realistic base rates for each demographic flag (probability of TRUE)
    "demographic_base_rates": {
        "ell": 0.15,                    # 15% English Language Learners
        "iep": 0.14,                    # 14% have IEP
        "gifted_flag": 0.08,            # 8% gifted
        "homeless_flag": 0.03,          # 3% homeless
        "disability": 0.12,             # 12% disability
        "economic_disadvantage": 0.45,  # 45% economically disadvantaged
    },
    
    # =========================================================================
    # ETHNICITY DISTRIBUTION
    # =========================================================================
    # Weights for ethnicity distribution (will be normalized to sum to 1)
    "ethnicity_weights": {
        "White": 0.45,
        "Hispanic or Latino": 0.27,
        "Black or African American": 0.14,
        "Asian": 0.06,
        "Two or More Races": 0.04,
        "American Indian or Alaska Native": 0.01,
        "Native Hawaiian or Pacific Islander": 0.01,
        "Other": 0.01,
        "Unknown": 0.005,
        "Declined to State": 0.005,
    },
    
    # =========================================================================
    # GRADE DISTRIBUTION
    # =========================================================================
    # Weights for grade distribution (will be normalized)
    # Format: { (min_grade, max_grade): weight }
    "grade_distribution": {
        (-1, 2): 0.25,                  # Pre-K to 2nd: 25%
        (3, 5): 0.30,                   # 3rd-5th: 30%
        (6, 8): 0.25,                   # 6th-8th: 25%
        (9, 12): 0.20,                  # 9th-12th: 20%
    },
    
    # =========================================================================
    # SUBGROUP-SPECIFIC EFFECTS
    # =========================================================================
    # Each subgroup can have:
    #   - enrollment_multiplier: multiplier on base treatment_proportion (1.2 = 20% more likely)
    #   - effect_multiplier: multiplier on treatment effect (1.1 = 10% larger effect)
    #   - dosage_multiplier: multiplier on dosage hours (1.15 = 15% more hours)
    # 
    # Set to 1.0 for no effect, or omit the subgroup entirely
    "subgroup_effects": {
        "ell": {
            "enrollment_multiplier": 1.2,   # ELL students 20% more likely to be tutored
            "effect_multiplier": 1.1,       # ELL students benefit 10% more
            "dosage_multiplier": 1.15,      # ELL students get 15% more hours
        },
        "iep": {
            "enrollment_multiplier": 1.1,   # IEP students 10% more likely
            "effect_multiplier": 1.0,       # Same effect as general population
            "dosage_multiplier": 1.2,       # IEP students get 20% more hours
        },
        "economic_disadvantage": {
            "enrollment_multiplier": 1.15,  # 15% more likely
            "effect_multiplier": 1.0,
            "dosage_multiplier": 1.1,       # Econ disadv students get 10% more hours
        },
        "gifted_flag": {
            "enrollment_multiplier": 0.8,   # 20% less likely
            "effect_multiplier": 0.9,       # 10% smaller effect
            "dosage_multiplier": 1.0,       # Same hours
        },
        "homeless_flag": {
            "enrollment_multiplier": 1.3,   # 30% more likely
            "effect_multiplier": 0.95,      # Slightly smaller effect
            "dosage_multiplier": 1.0,       # Same hours
        },
        "disability": {
            "enrollment_multiplier": 1.1,
            "effect_multiplier": 1.0,
            "dosage_multiplier": 1.0,       # Same hours
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
    # Sessions occur during school hours (weekends are automatically excluded)
    "session_hours": {
        "start_hour": 9,    # 9 AM
        "end_hour": 15,     # 3 PM (15:00)
    },
    
    # =========================================================================
    # MISSING DATA
    # =========================================================================
    "add_missing_data": False,          # Whether to add missing values
    "missing_percentage_range": (5, 15),# Range of missing data percentage per column
    
    # =========================================================================
    # OUTPUT FILES
    # =========================================================================
    "student_data_file": "example_student_dataset.csv",
    "session_data_file": "example_session_dataset.csv",
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def set_random_seed(seed):
    """Set random seed for reproducibility."""
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)


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


def generate_skewed_dosage(n, mean_hours, sigma, min_hours, max_hours, skew_direction="left"):
    """
    Generate skewed dosage distribution.
    
    Parameters:
    - n: number of samples
    - mean_hours: target mean hours (approximate)
    - sigma: controls variance (0.1 to 1.0, higher = more variance/spread)
    - min_hours: minimum hours (floor)
    - max_hours: maximum hours (ceiling)
    - skew_direction: "left" (tail low, mass high) or "right" (tail high, mass low)
    
    Returns: numpy array of dosage values
    """
    range_hours = max_hours - min_hours
    
    if skew_direction == "left":
        # Left-skewed using beta distribution (alpha > beta)
        # For beta: mean = alpha / (alpha + beta)
        # We want: mean_hours = min_hours + beta_mean * range_hours
        
        target_beta_mean = (mean_hours - min_hours) / range_hours
        target_beta_mean = np.clip(target_beta_mean, 0.2, 0.9)
        
        # For left skew, we need alpha > beta, which requires target_beta_mean > 0.5
        # If target_beta_mean < 0.5, we can't have true left skew - just use low variance
        
        # Concentration parameter (higher = less variance)
        # sigma controls variance inversely
        concentration = 3.0 + (1 - sigma) * 20  # sigma 0.3 -> concentration ~17
        
        # Calculate alpha and beta to achieve target mean exactly
        # mean = alpha / (alpha + beta) = m
        # So alpha = m * concentration, beta = (1-m) * concentration
        alpha_param = target_beta_mean * concentration
        beta_param = (1 - target_beta_mean) * concentration
        
        # Ensure valid parameters (alpha > 1, beta > 0.5 for smoothness)
        alpha_param = max(1.5, alpha_param)
        beta_param = max(0.8, beta_param)
        
        # Generate beta samples
        samples = np.random.beta(alpha_param, beta_param, size=n)
        
        # Scale to [min_hours, max_hours]
        dosage = min_hours + samples * range_hours
        
    else:  # right-skewed
        # Use log-normal for right skew
        # For log-normal: mean = exp(mu + sigma^2/2), so mu = ln(mean) - sigma^2/2
        mu = np.log(mean_hours) - (sigma ** 2) / 2
        dosage = np.random.lognormal(mean=mu, sigma=sigma, size=n)
    
    dosage = np.clip(dosage, min_hours, max_hours)
    return dosage


def calculate_dose_response_multiplier(dosage, config):
    """
    Calculate treatment effect multiplier based on dosage.
    
    Returns a multiplier (0 to ~1.5) that scales the treatment effect
    based on how many hours of tutoring the student received.
    """
    dose_config = config.get("dose_response", {})
    
    if not dose_config.get("enabled", False):
        return 1.0  # No dose-response, constant effect
    
    response_type = dose_config.get("type", "linear")
    reference_hours = dose_config.get("reference_hours", 55)
    
    if response_type == "linear":
        # Linear: effect proportional to hours
        # At reference_hours, multiplier = 1.0
        return dosage / reference_hours
    
    elif response_type == "logarithmic":
        # Logarithmic: diminishing returns
        # At reference_hours, multiplier = 1.0
        if dosage <= 0:
            return 0.0
        return np.log1p(dosage) / np.log1p(reference_hours)
    
    elif response_type == "threshold":
        # Threshold: no effect below threshold, then linear
        threshold = dose_config.get("threshold_hours", 20)
        if dosage < threshold:
            return 0.0
        effective_hours = dosage - threshold
        effective_reference = reference_hours - threshold
        return effective_hours / effective_reference if effective_reference > 0 else 1.0
    
    else:
        return 1.0


def random_weekday_datetime(start_date, end_date, start_hour=9, end_hour=15):
    """
    Generate a random datetime between start_date and end_date,
    constrained to school hours (e.g., 9am-3pm) on WEEKDAYS ONLY.
    
    Returns: datetime object
    """
    max_attempts = 100
    for _ in range(max_attempts):
        # Pick a random date
        delta = end_date - start_date
        random_days = random.randint(0, max(0, delta.days))
        session_date = start_date + timedelta(days=random_days)
        
        # Check if weekday (Monday=0, Sunday=6)
        if session_date.weekday() < 5:  # Monday-Friday
            # Pick a random time within school hours
            hour = random.randint(start_hour, end_hour - 1)
            minute = random.randint(0, 59)
            return datetime.combine(session_date, datetime.min.time().replace(hour=hour, minute=minute))
    
    # Fallback: just return a Monday
    session_date = start_date
    while session_date.weekday() >= 5:
        session_date += timedelta(days=1)
    hour = random.randint(start_hour, end_hour - 1)
    minute = random.randint(0, 59)
    return datetime.combine(session_date, datetime.min.time().replace(hour=hour, minute=minute))


def get_subject_for_grade(grade, subject_by_grade):
    """
    Select a session subject based on the student's grade level.
    """
    for (min_grade, max_grade), probs in subject_by_grade.items():
        if min_grade <= grade <= max_grade:
            if random.random() < probs.get("math", 0.5):
                return "math"
            else:
                return "ela"
    return random.choice(["math", "ela"])


def weighted_choice(weights_dict):
    """
    Make a weighted random choice from a dictionary of {item: weight}.
    """
    items = list(weights_dict.keys())
    weights = list(weights_dict.values())
    total = sum(weights)
    normalized = [w / total for w in weights]
    return np.random.choice(items, p=normalized)


def generate_grade_from_distribution(grade_distribution):
    """
    Generate a grade level based on the grade distribution config.
    """
    # First, select a grade range based on weights
    ranges = list(grade_distribution.keys())
    weights = list(grade_distribution.values())
    total = sum(weights)
    normalized = [w / total for w in weights]
    
    idx = np.random.choice(len(ranges), p=normalized)
    min_grade, max_grade = ranges[idx]
    
    # Then pick a random grade within that range
    return random.randint(min_grade, max_grade)


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


def calculate_dosage_multiplier(student_flags, subgroup_effects):
    """
    Calculate dosage hours multiplier based on student characteristics.
    
    Uses multiplicative adjustment for students with multiple flags.
    E.g., ELL + IEP student gets 1.15 * 1.2 = 1.38x hours
    """
    multiplier = 1.0
    
    for flag_name, effects in subgroup_effects.items():
        if student_flags.get(flag_name) == 'TRUE':
            multiplier *= effects.get('dosage_multiplier', 1.0)
    
    return multiplier


def generate_school_fidelity_map(school_ids, between_variability):
    """
    Generate a fidelity score for each school.
    """
    fidelity_map = {}
    for school_id in school_ids:
        fidelity = np.random.normal(1.0, between_variability * 0.3)
        fidelity = np.clip(fidelity, 0.5, 1.5)
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
    
    Features:
    - Realistic demographic base rates
    - Configurable grade distribution
    - Configurable ethnicity distribution
    - ELA-Math correlation
    - Dose-response relationship for treatment effects
    - Subgroup-specific enrollment and effects
    
    Returns: tuple of (students_list, treatment_info, school_assignments)
    """
    
    num_students = config["num_students"]
    base_treatment_prop = config["treatment_proportion"]
    base_effect_sd = config["treatment_effect_sd"]
    subgroup_effects = config.get("subgroup_effects", {})
    num_schools = config.get("num_schools", 10)
    
    # Get demographic base rates
    demo_rates = config.get("demographic_base_rates", {})
    
    # Get ethnicity weights
    ethnicity_weights = config.get("ethnicity_weights", {})
    if not ethnicity_weights:
        ethnicity_weights = {"Unknown": 1.0}
    
    # Get grade distribution
    grade_distribution = config.get("grade_distribution", {(-1, 12): 1.0})
    
    # Get ELA-Math correlation
    ela_math_corr = config.get("ela_math_correlation", 0.75)
    
    # Define other categorical options
    boolean_values = ['TRUE', 'FALSE']
    performance_levels = ['Below Basic', 'Basic', 'Proficient', 'Advanced', 'Distinguished', 'Exceeds']
    
    # District definitions (linked ID and name)
    district_definitions = [
        ('0100001', 'Denver Public Schools'),
        ('0200001', 'Aurora Public Schools'),
        ('0400001', 'Jefferson County Schools'),
        ('0500001', 'Cherry Creek School District'),
        ('0600001', 'Douglas County School District'),
    ]
    
    # School name pool
    school_name_pool = [
        'Washington Elementary', 'Lincoln Middle School', 'Roosevelt High School',
        'Kennedy Academy', 'Jefferson STEM School', 'Madison Preparatory',
        'Franklin Learning Center', 'Adams Elementary', 'Monroe Middle School',
        'Hamilton High School', 'Central High School', 'Westside Elementary',
        'Eastview Academy', 'Northgate Middle School', 'Southpark Elementary'
    ]
    
    # Create district lookup
    district_lookup = {did: dname for did, dname in district_definitions}
    
    # Pre-generate schools with linked IDs, names, and districts
    # Each school belongs to exactly one district
    school_definitions = {}  # school_id -> {'name': ..., 'district_id': ...}
    for i in range(num_schools):
        school_id = ''.join(random.choices(string.digits, k=6))
        school_name = school_name_pool[i % len(school_name_pool)]
        district_id, district_name = random.choice(district_definitions)
        school_definitions[school_id] = {
            'name': school_name,
            'district_id': district_id,
            'district_name': district_name
        }
    
    school_ids = list(school_definitions.keys())
    
    used_student_ids = set()
    students = []
    treatment_info = {}
    school_assignments = {}
    
    for i in range(num_students):
        student_id = generate_student_id(used_student_ids)
        
        # Assign to a school
        school_id = random.choice(school_ids)
        school_assignments[student_id] = school_id
        
        # Generate grade from distribution
        grade_level = generate_grade_from_distribution(grade_distribution)
        
        # Generate demographic flags based on base rates
        student_flags = {}
        for flag_name, base_rate in demo_rates.items():
            student_flags[flag_name] = 'TRUE' if random.random() < base_rate else 'FALSE'
        
        # Generate baseline scores FIRST (needed for enrollment decision)
        baseline_mean = config["baseline_score_mean"]
        baseline_std = config["baseline_score_std"]
        score_min = config["score_min"]
        score_max = config["score_max"]
        
        # Generate correlated ELA and Math abilities
        shared_ability = np.random.normal(0, 1)
        ela_specific = np.random.normal(0, 1)
        math_specific = np.random.normal(0, 1)
        
        ela_ability = baseline_mean + baseline_std * (
            np.sqrt(ela_math_corr) * shared_ability + 
            np.sqrt(1 - ela_math_corr) * ela_specific
        )
        math_ability = baseline_mean + baseline_std * (
            np.sqrt(ela_math_corr) * shared_ability + 
            np.sqrt(1 - ela_math_corr) * math_specific
        )
        
        ela_two_years = np.clip(ela_ability + np.random.normal(0, 10), score_min, score_max)
        ela_one_year = np.clip(ela_ability + np.random.normal(5, 10), score_min, score_max)
        math_two_years = np.clip(math_ability + np.random.normal(0, 10), score_min, score_max)
        math_one_year = np.clip(math_ability + np.random.normal(5, 10), score_min, score_max)
        
        # Calculate average prior year score for enrollment decision
        avg_prior_score = (ela_one_year + math_one_year) / 2
        
        # Calculate enrollment probability based on subgroup membership
        enrollment_prob = calculate_enrollment_probability(
            base_treatment_prop, student_flags, subgroup_effects
        )
        
        # Apply steep inverse relationship with test scores
        # Lower scores = much higher probability of tutoring
        # Normalize score to 0-1 range (0 = lowest, 1 = highest)
        normalized_score = (avg_prior_score - score_min) / (score_max - score_min)
        
        # Steep inverse: use exponential decay from high scores
        # score_modifier ranges from ~2.5 (for lowest scores) to ~0.1 (for highest scores)
        # This creates strong targeting of low-performing students
        score_modifier = np.exp(-3.0 * normalized_score) * 2.5
        
        # Apply score modifier to enrollment probability
        enrollment_prob = enrollment_prob * score_modifier
        enrollment_prob = min(enrollment_prob, 0.95)  # Cap at 95%
        
        is_treated = random.random() < enrollment_prob
        
        # Current year scores with treatment effect
        natural_growth_ela = np.random.normal(
            config["natural_growth_mean"], config["natural_growth_std"])
        natural_growth_math = np.random.normal(
            config["natural_growth_mean"], config["natural_growth_std"])
        
        if is_treated:
            # Generate base dosage
            base_dosage = generate_skewed_dosage(
                1,
                config["dosage_mean_hours"],
                config["dosage_skew"],
                config["dosage_min_hours"],
                config["dosage_max_hours"],
                config.get("dosage_skew_direction", "left")
            )[0]
            
            # Apply subgroup-specific dosage multiplier (ELL, IEP, etc. get more hours)
            dosage_mult = calculate_dosage_multiplier(student_flags, subgroup_effects)
            dosage = base_dosage * dosage_mult
            dosage = min(dosage, config["dosage_max_hours"])  # Cap at max
            
            # Calculate subgroup-specific effect multiplier
            subgroup_multiplier = calculate_effect_multiplier(student_flags, subgroup_effects)
            
            # Calculate dose-response multiplier
            dose_multiplier = calculate_dose_response_multiplier(dosage, config)
            
            # Combined effect
            adjusted_effect_sd = base_effect_sd * subgroup_multiplier * dose_multiplier
            growth_std = config["natural_growth_std"]
            treatment_boost = adjusted_effect_sd * growth_std
            
            ela_current = np.clip(
                ela_one_year + natural_growth_ela + treatment_boost, score_min, score_max)
            math_current = np.clip(
                math_one_year + natural_growth_math + treatment_boost, score_min, score_max)
            
            treatment_info[student_id] = {
                'is_treated': True, 
                'dosage': dosage,
                'subgroup_multiplier': subgroup_multiplier,
                'dose_multiplier': dose_multiplier,
                'flags': student_flags,
                'grade': grade_level
            }
        else:
            ela_current = np.clip(
                ela_one_year + natural_growth_ela, score_min, score_max)
            math_current = np.clip(
                math_one_year + natural_growth_math, score_min, score_max)
            
            treatment_info[student_id] = {
                'is_treated': False, 
                'dosage': 0,
                'subgroup_multiplier': 0,
                'dose_multiplier': 0,
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
        
        # Select ethnicity based on weights
        ethnicity = weighted_choice(ethnicity_weights)
        
        # Get school and district info from lookup
        school_info = school_definitions[school_id]
        
        # Build student record
        student = {
            "student_id": student_id,
            "district_id": school_info['district_id'],
            "district_name": school_info['district_name'],
            "school_id": school_id,
            "school_name": school_info['name'],
            "current_grade_level": grade_level,
            "gender": random.choice(boolean_values),
            "ethnicity": ethnicity,
            "ell": student_flags.get("ell", "FALSE"),
            "iep": student_flags.get("iep", "FALSE"),
            "gifted_flag": student_flags.get("gifted_flag", "FALSE"),
            "homeless_flag": student_flags.get("homeless_flag", "FALSE"),
            "disability": student_flags.get("disability", "FALSE"),
            "economic_disadvantage": student_flags.get("economic_disadvantage", "FALSE"),
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
    - Session times constrained to school hours on weekdays only
    - Configurable session ratios and tutor consistency
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
    
    # Session ratio weights
    ratio_weights = config.get("session_ratio_weights", {"1:1": 1.0})
    
    # Tutor consistency
    tutor_consistency = config.get("tutor_consistency", 0.8)
    
    # Date range for sessions
    date_range_days = config.get("session_date_range_days", 180)
    start_date = datetime.now().date() - timedelta(days=date_range_days)
    end_date = datetime.now().date()
    
    sessions_data = []
    
    # Generate tutor pool
    num_tutors = config.get("num_providers", 5) * 10
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
        student_grade = info.get('grade', 5)
        school_id = school_assignments.get(student_id)
        
        # Get fidelity score for this student's context
        if vary_by == "school" and school_id:
            fidelity = fidelity_map.get(school_id, 1.0)
        elif vary_by == "provider":
            fidelity = 1.0
        else:
            fidelity = 1.0
        
        # Fidelity affects dosage completion and session consistency
        dosage_completion_rate = 0.7 + (fidelity - 0.5) * 0.6
        dosage_completion_rate = np.clip(dosage_completion_rate, 0.5, 1.2)
        actual_hours = total_hours * dosage_completion_rate
        
        duration_std_multiplier = 2.0 - fidelity
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
            
            # Select tutor based on consistency setting
            if random.random() < tutor_consistency:
                tutor_id = primary_tutor
            else:
                tutor_id = random.choice(tutor_pool)
            
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
            
            # Generate session datetime (weekdays only, school hours)
            session_datetime = random_weekday_datetime(
                start_date, end_date, start_hour, end_hour
            )
            
            # Select subject based on grade
            subject = get_subject_for_grade(student_grade, subject_by_grade)
            
            # Select ratio based on weights
            session_ratio = weighted_choice(ratio_weights)
            
            sessions_data.append({
                'student_id': student_id,
                'session_topic': subject,
                'session_date': session_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                'session_duration': duration,
                'session_ratio': session_ratio,
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
    
    # Random seed
    seed = config.get("random_seed")
    print(f"\n[REPRODUCIBILITY]")
    print(f"   Random seed: {seed if seed is not None else 'None (random)'}")
    
    # Get treated/control
    treated_ids = [sid for sid, info in treatment_info.items() if info['is_treated']]
    control_ids = [sid for sid, info in treatment_info.items() if not info['is_treated']]
    
    treated = students_df[students_df['student_id'].isin(treated_ids)]
    control = students_df[students_df['student_id'].isin(control_ids)]
    
    print(f"\n[STUDENTS]")
    print(f"   Total students:    {len(students_df):,}")
    print(f"   Treated (tutored): {len(treated):,} ({100*len(treated)/len(students_df):.1f}%)")
    print(f"   Control:           {len(control):,} ({100*len(control)/len(students_df):.1f}%)")
    
    # Demographic base rates
    demo_rates = config.get("demographic_base_rates", {})
    if demo_rates:
        print(f"\n[DEMOGRAPHIC BASE RATES]")
        for flag in ['ell', 'iep', 'economic_disadvantage', 'gifted_flag', 'homeless_flag', 'disability']:
            if flag in students_df.columns:
                actual_rate = 100 * (students_df[flag] == 'TRUE').mean()
                expected_rate = 100 * demo_rates.get(flag, 0.5)
                print(f"   {flag:25s}: {actual_rate:5.1f}% (target: {expected_rate:.1f}%)")
    
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
    
    # Enrollment by performance level (score-based targeting)
    print(f"\n[ENROLLMENT BY PRIOR PERFORMANCE] (score-based targeting)")
    students_df['avg_prior_score'] = (students_df['ela_state_score_one_year_ago'] + 
                                       students_df['math_state_score_one_year_ago']) / 2
    score_min = config.get("score_min", 650)
    score_max = config.get("score_max", 800)
    bins = [0, 680, 710, 740, 770, 790, 1000]
    labels = ['Below Basic', 'Basic', 'Proficient', 'Advanced', 'Distinguished', 'Exceeds']
    students_df['perf_bin'] = pd.cut(students_df['avg_prior_score'], bins=bins, labels=labels)
    for level in labels:
        level_df = students_df[students_df['perf_bin'] == level]
        if len(level_df) > 0:
            level_treated = level_df[level_df['student_id'].isin(treated_ids)]
            rate = 100 * len(level_treated) / len(level_df)
            print(f"   {level:15s}: {rate:5.1f}% tutored (n={len(level_df)})")
    
    # Grade distribution
    print(f"\n[GRADE DISTRIBUTION]")
    grade_dist = config.get("grade_distribution", {})
    for (min_g, max_g), target_weight in grade_dist.items():
        actual = students_df[(students_df['current_grade_level'] >= min_g) & 
                            (students_df['current_grade_level'] <= max_g)]
        actual_pct = 100 * len(actual) / len(students_df)
        target_pct = 100 * target_weight / sum(grade_dist.values())
        grade_label = f"Grades {min_g}-{max_g}" if min_g >= 0 else f"Pre-K-{max_g}"
        print(f"   {grade_label:15s}: {actual_pct:5.1f}% (target: {target_pct:.1f}%)")
    
    # Dosage summary
    dosages = [info['dosage'] for info in treatment_info.values() if info['is_treated']]
    dosage_series = pd.Series(dosages)
    
    print(f"\n[DOSAGE] (treated students only)")
    print(f"   Median hours:  {dosage_series.median():.1f}")
    print(f"   Mean hours:    {dosage_series.mean():.1f}")
    print(f"   Std dev:       {dosage_series.std():.1f}")
    print(f"   Min:           {dosage_series.min():.1f}")
    print(f"   Max:           {dosage_series.max():.1f}")
    
    # Dosage by subgroup
    print(f"\n[DOSAGE BY SUBGROUP]")
    for flag in ['ell', 'iep', 'economic_disadvantage']:
        flag_dosages = [info['dosage'] for sid, info in treatment_info.items() 
                       if info['is_treated'] and info['flags'].get(flag) == 'TRUE']
        non_flag_dosages = [info['dosage'] for sid, info in treatment_info.items() 
                          if info['is_treated'] and info['flags'].get(flag) != 'TRUE']
        if flag_dosages and non_flag_dosages:
            flag_mean = np.mean(flag_dosages)
            non_flag_mean = np.mean(non_flag_dosages)
            mult = subgroup_effects.get(flag, {}).get('dosage_multiplier', 1.0)
            print(f"   {flag:25s}: {flag_mean:5.1f} hrs (others: {non_flag_mean:.1f}, target mult: {mult:.2f})")
    
    # Dose-response info
    dose_config = config.get("dose_response", {})
    if dose_config.get("enabled", False):
        print(f"\n[DOSE-RESPONSE]")
        print(f"   Enabled:         Yes")
        print(f"   Type:            {dose_config.get('type', 'linear')}")
        print(f"   Reference hours: {dose_config.get('reference_hours', 55)}")
        dose_mults = [info['dose_multiplier'] for info in treatment_info.values() if info['is_treated']]
        print(f"   Dose multiplier range: {min(dose_mults):.2f} - {max(dose_mults):.2f}")
    
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
    
    # ELA-Math correlation
    print(f"\n[ELA-MATH CORRELATION]")
    ela_scores = students_df['ela_state_score_one_year_ago']
    math_scores = students_df['math_state_score_one_year_ago']
    actual_corr = ela_scores.corr(math_scores)
    target_corr = config.get("ela_math_correlation", 0.75)
    print(f"   Actual:  {actual_corr:.3f}")
    print(f"   Target:  {target_corr:.3f}")
    
    # Session summary
    print(f"\n[SESSIONS]")
    print(f"   Total sessions: {len(sessions_df):,}")
    if len(treated) > 0:
        print(f"   Avg per student: {len(sessions_df)/len(treated):.1f}")
    
    # Session ratio distribution
    print(f"\n[SESSION RATIOS]")
    ratio_counts = sessions_df['session_ratio'].value_counts(normalize=True) * 100
    ratio_weights = config.get("session_ratio_weights", {})
    total_weight = sum(ratio_weights.values())
    for ratio in sorted(ratio_counts.index):
        actual = ratio_counts[ratio]
        target = 100 * ratio_weights.get(ratio, 0) / total_weight if total_weight > 0 else 0
        print(f"   {ratio:6s}: {actual:5.1f}% (target: {target:.1f}%)")
    
    # Subject distribution by grade
    print(f"\n[SUBJECT DISTRIBUTION BY GRADE]")
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
        weekdays = session_times.dt.dayofweek
        print(f"   Hour range: {hours.min()}:00 - {hours.max()}:59")
        print(f"   Most common hour: {hours.mode().iloc[0]}:00")
        print(f"   Weekend sessions: {(weekdays >= 5).sum()} (should be 0)")
    except:
        print("   (datetime parsing not available)")
    
    # Fidelity summary
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
    
    # Set random seed for reproducibility
    set_random_seed(CONFIG.get("random_seed"))
    
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
