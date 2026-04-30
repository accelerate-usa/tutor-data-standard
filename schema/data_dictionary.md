# Tutor Data Standard Dictionary

Generated from `schema_registry.py`. Regenerate with `python utils/generate_schema_artifacts.py`.

Most teams can upload `sessions.csv` and `students.csv` directly in the dashboard.

> Advanced, optional: the dashboard can apply an uploaded local mapping profile JSON for recurring uploads with non-canonical column headers. Keep this feature documented, but keep it out of the primary upload path. The app does not store the file for the user.

## Student Dataset

Canonical columns: `student_id, district_id, district_name, school_id, school_name, current_grade_level, gender, ethnicity, ell, iep, gifted_flag, homeless_flag, disability, economic_disadvantage, ela_outcome_measure_1, ela_outcome_measure_2, ela_outcome_measure_3, math_outcome_measure_1, math_outcome_measure_2, math_outcome_measure_3, performance_level_previous, performance_level_most_recent, performance_level_earliest`

| section | column_name | description | data_type | required | example_values | range_of_values | aliases | used_in |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Identifiers | student_id | Unique identifier for the student. Stored and matched as text. | identifier | yes | 0016740395, S67890 | Any non-empty string. Must match the session file exactly after trimming whitespace. |  | overview, dosage, equity, outcomes, cost |
| Identifiers | district_id | District identifier stored as text to preserve leading zeros. | identifier | yes | 0803360 | Any non-empty string. |  | overview, dosage, equity, outcomes, cost |
| Identifiers | district_name | District name. | string | yes | Denver Public Schools | Free text. |  | overview |
| Identifiers | school_id | School identifier stored as text to preserve leading zeros. | identifier | yes | 631930 | Any non-empty string. |  | overview, dosage, equity, outcomes, cost |
| Identifiers | school_name | School name. | string | yes | Denver High School | Free text. |  | overview, dosage, equity, outcomes, cost |
| Student Characteristics | current_grade_level | Current grade level served. Upload accepts numeric grades plus common labels such as K and Pre-K. | integer | yes | 8, K, Pre-K | -1 through 12 after normalization. |  | overview, dosage, equity, outcomes, cost |
| Student Characteristics | gender | Student gender category as reported locally. | categorical | recommended | Female, Male, Nonbinary, Unknown | No more than 5 unique strings is recommended. | sex | dosage |
| Student Characteristics | ethnicity | Student ethnicity or race category as reported locally. | categorical | recommended | White, Hispanic or Latino, Black or African American | No more than 10 unique strings is recommended. |  | dosage, equity |
| Student Characteristics | ell | English learner flag. Blank values are treated as unknown rather than false. | tri_state_flag | recommended | TRUE, FALSE, Unknown | Boolean-like values or blank. | english_learner, english_language_learner | equity |
| Student Characteristics | iep | IEP flag. Blank values are treated as unknown rather than false. | tri_state_flag | recommended | TRUE, FALSE, Unknown | Boolean-like values or blank. |  | equity |
| Student Characteristics | gifted_flag | Gifted flag. | tri_state_flag | recommended | TRUE, FALSE, Unknown | Boolean-like values or blank. |  |  |
| Student Characteristics | homeless_flag | Homelessness flag. | tri_state_flag | recommended | TRUE, FALSE, Unknown | Boolean-like values or blank. |  |  |
| Student Characteristics | disability | Disability flag. | tri_state_flag | recommended | TRUE, FALSE, Unknown | Boolean-like values or blank. |  |  |
| Student Characteristics | economic_disadvantage | Economic disadvantage flag. | tri_state_flag | recommended | TRUE, FALSE, Unknown | Boolean-like values or blank. | free_reduced_lunch | equity |
| Ordered Outcome Measures | ela_outcome_measure_1 | Earliest available numeric ELA outcome measure. | numeric_outcome | recommended | 712 | Any comparable numeric outcome scale. Measure 1 is the earliest observation in order. | ela_state_score_two_years_ago, ela_outcome_score_two_years_ago | outcomes |
| Ordered Outcome Measures | ela_outcome_measure_2 | Middle or later numeric ELA outcome measure. | numeric_outcome | recommended | 726 | Any comparable numeric outcome scale. Measure 2 must be later than measure 1. | ela_state_score_one_year_ago, ela_outcome_score_one_year_ago | outcomes |
| Ordered Outcome Measures | ela_outcome_measure_3 | Most recent numeric ELA outcome measure. | numeric_outcome | recommended | 775 | Any comparable numeric outcome scale. Measure 3 is the most recent observation. | ela_state_score_current_year, ela_outcome_score_current_year | outcomes, equity |
| Ordered Outcome Measures | math_outcome_measure_1 | Earliest available numeric math outcome measure. | numeric_outcome | recommended | 705 | Any comparable numeric outcome scale. Measure 1 is the earliest observation in order. | math_state_score_two_years_ago, math_outcome_score_two_years_ago | outcomes |
| Ordered Outcome Measures | math_outcome_measure_2 | Middle or later numeric math outcome measure. | numeric_outcome | recommended | 719 | Any comparable numeric outcome scale. Measure 2 must be later than measure 1. | math_state_score_one_year_ago, math_outcome_score_one_year_ago | outcomes |
| Ordered Outcome Measures | math_outcome_measure_3 | Most recent numeric math outcome measure. | numeric_outcome | recommended | 741 | Any comparable numeric outcome scale. Measure 3 is the most recent observation. | math_state_score_current_year, math_outcome_score_current_year | outcomes, equity |
| Performance Levels | performance_level_previous | The previous available categorical performance level, if reported. | categorical | recommended | Basic, Proficient | No more than 6 unique strings is recommended. | performance_level_prior_year | equity |
| Performance Levels | performance_level_most_recent | The most recent categorical performance level, if reported. | categorical | recommended | Basic, Advanced | No more than 6 unique strings is recommended. | performance_level_current_year | equity |
| Performance Levels | performance_level_earliest | The earliest available categorical performance level, if reported. | categorical | recommended | Basic | No more than 6 unique strings is recommended. | performance_level_two_years_ago |  |

## Session Dataset

Canonical columns: `student_id, session_topic, session_date, session_duration, session_ratio, tutor_id`

| section | column_name | description | data_type | required | example_values | range_of_values | aliases | used_in |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Core Session Data | student_id | Unique identifier for the student. Must match the student file exactly after trimming whitespace. | identifier | yes | 0016740395, S67890 | Any non-empty string. |  | overview, dosage, equity, outcomes, cost |
| Core Session Data | session_topic | Tutoring subject. Intake normalizes common aliases such as 'reading' to 'ela' and 'mathematics' to 'math'. | categorical | yes | math, ela, reading | Currently supported analysis expects math or ela after normalization. |  | overview, dosage |
| Core Session Data | session_date | Date or datetime for the tutoring session. | datetime | yes | 2024-06-15, 2024-06-15 10:30:00 | Any parseable date or datetime. | session_datetime | overview, dosage |
| Core Session Data | session_duration | Duration of the session in minutes. | numeric | yes | 45, 60 | Non-negative numeric values. |  | overview, dosage, equity, outcomes, cost |
| Core Session Data | session_ratio | Student-to-tutor ratio. | string | recommended | 1:1, 1:3 | Free text or ratio notation. |  |  |
| Core Session Data | tutor_id | Unique identifier for the tutor. | identifier | yes | T54321, 98765 | Any non-empty string. |  | overview |
