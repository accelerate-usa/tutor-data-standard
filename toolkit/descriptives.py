import streamlit as st
import pandas as pd
import plotly.express as px
import re
from datetime import datetime

st.set_page_config(page_title="DATAS Analysis Toolkit", layout="wide")

# Title
st.title("📊 DATAS Analysis Toolkit")

# util functions
def validate_data(df: pd.DataFrame, data_type: str):
    errors = []

    # 1. Empty or header-only file
    if df.shape[0] <= 0:
        errors.append("The file appears to be empty or only contains headers.")
        return errors

    # Normalize column names
    headers = [c.strip() for c in df.columns]

    if data_type == 'school':
        expected = [
            "student_id","district_id","district_name","school_id","school_name",
            "current_grade_level","gender","ethnicity","ell","iep","gifted_flag",
            "homeless_flag","ela_state_score_two_years_ago","ela_state_score_one_year_ago",
            "ela_state_score_current_year","math_state_score_two_years_ago",
            "math_state_score_one_year_ago","math_state_score_current_year",
            "performance_level_prior_year","performance_level_current_year",
            "disability","economic_disadvantage"
        ]
        missing = [h for h in expected if h not in headers]
        if missing:
            errors.append("Invalid Headers – missing or misspelled:")
            errors += [f"  • {h}" for h in missing]
            return errors

        unique_eth = set()
        unique_pp = set()
        unique_pc = set()

        for i, row in df.iterrows():
            vals = row.astype(str).str.strip().tolist()
            if all(v == '' for v in vals):
                continue

            def chk(field, val):
                if field == "student_id" and not re.fullmatch(r"\d{10}", val):
                    return f'Row {i+2}: Invalid student_id "{val}" (should be 10 digits)'
                if field == "district_id" and not re.fullmatch(r"\d{7}", val):
                    return f'Row {i+2}: Invalid district_id "{val}" (7 digits)'
                if field == "school_id" and not re.fullmatch(r"\d{6}", val):
                    return f'Row {i+2}: Invalid school_id "{val}" (6 digits)'
                if field == "current_grade_level":
                    try:
                        iv = int(val)
                        if iv < -1 or iv > 12:
                            return f'Row {i+2}: current_grade_level "{val}" must be -1–12'
                    except:
                        return f'Row {i+2}: current_grade_level "{val}" not an integer'
                if field in ["ell", "iep", "gifted_flag", "homeless_flag", "disability", "economic_disadvantage", "gender"]:
                    bool_val = str(val).lower()
                    if bool_val not in ("true", "false", "1", "0", "t", "f", "yes", "no", "y", "n", "TRUE", "FALSE", "YES", "NO", "T", "F", "male", "female"):
                        return f'Row {i+2}: {field} "{val}" must be a boolean value (TRUE/FALSE, True/False, 1/0, etc.)'
                if field in [
                    "ela_state_score_two_years_ago","ela_state_score_one_year_ago",
                    "ela_state_score_current_year","math_state_score_two_years_ago",
                    "math_state_score_one_year_ago","math_state_score_current_year"
                ]:
                    try:
                        iv = float(val)
                    except:
                        return f'Row {i+2}: {field} "{val}" must be a number'
                if field == "ethnicity":
                    unique_eth.add(val)
                if field == "performance_level_prior_year":
                    unique_pp.add(val)
                if field == "performance_level_current_year":
                    unique_pc.add(val)
                return None

            for col in expected:
                err = chk(col, str(row[col]))
                if err:
                    errors.append(err)

        if len(unique_eth) > 10:
            errors.append(f"The 'ethnicity' column has >10 unique values ({len(unique_eth)})")
        if len(unique_pp) > 6:
            errors.append(f"'performance_level_prior_year' has >6 unique values ({len(unique_pp)})")
        if len(unique_pc) > 6:
            errors.append(f"'performance_level_current_year' has >6 unique values ({len(unique_pc)})")

    elif data_type == 'session':
        expected = ["student_id","session_topic","session_date","session_duration","tutor_id"]
        missing = [h for h in expected if h not in headers]
        if missing:
            errors.append("Invalid Headers – missing or misspelled:")
            errors += [f"  • {h}" for h in missing]
            return errors

        for i, row in df.iterrows():
            vals = row.astype(str).str.strip().tolist()
            if all(v == '' for v in vals):
                continue

            sid = str(row["student_id"])
            if not re.fullmatch(r"\d+", sid):
                errors.append(f'Row {i+2}: Invalid student_id "{sid}"')

            topic = str(row["session_topic"]).lower()
            if topic not in ("math","ela"):
                errors.append(f'Row {i+2}: session_topic "{row["session_topic"]}" must be math or ela')

            date = str(row["session_date"])
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
                errors.append(f'Row {i+2}: Invalid session_date "{date}"')
            else:
                try:
                    y,m,d = map(int, date.split("-"))
                    _ = datetime(y,m,d)
                except:
                    errors.append(f'Row {i+2}: session_date "{date}" is not a real date')

            try:
                dur = float(row["session_duration"])
                if dur <= 0:
                    errors.append(f'Row {i+2}: session_duration "{row["session_duration"]}" must be >0')
            except:
                errors.append(f'Row {i+2}: session_duration "{row["session_duration"]}" not a number')

            tid = str(row["tutor_id"]).strip()
            if not tid:
                errors.append(f'Row {i+2}: tutor_id must be non-empty')

    return errors

# Tabs
tab1, tab2, tab3 = st.tabs(["Step 1: Validate Data", "Step 2: Program Characteristics", "Step 3: Charts & Results"])

# Session state to hold data
if "session_data" not in st.session_state:
    st.session_state["session_data"] = None
if "student_data" not in st.session_state:
    st.session_state["student_data"] = None

# ---- STEP 1: VALIDATE DATA ----
with tab1:
    st.header("1. Validate Your Data")
    st.write("Feel free to use our example [student](https://drive.google.com/file/d/1FjTLaWGRQd6zlgaXkqHkAU_Gj8kUzgGY/view) and [session](https://drive.google.com/file/d/1ivNs9gFkIIgiABUHEOvsm8mCmvg9nKJ3/view) datasets to explore the toolkit.")
    st.write("To use your own data, upload your session and student below. Be sure that your data is formatted according to our [data dictionary](https://docs.google.com/spreadsheets/d/1x8Y2kNCWsixtWp_MAZn_m7_XjBQ8y6iHTc11OS4fixE/edit?gid=2003973770#gid=2003973770). Our [validator](https://jasongodfrey.info/data_validator.html) can help you troubleshoot your data formatting.") 

    uploaded_session_file = st.file_uploader("Upload Tutoring Session Data (CSV)", type="csv", key="session_uploader")
    uploaded_student_file  = st.file_uploader("Upload Student Data (CSV)",  type="csv", key="student_uploader")

    if uploaded_session_file and uploaded_student_file:
        try:
            session_df = pd.read_csv(uploaded_session_file)
            student_df  = pd.read_csv(uploaded_student_file)

            prov_errs = validate_data(session_df, 'session')
            stud_errs = validate_data(student_df,  'school')

            if prov_errs or stud_errs:
                st.error("Errors Found:")
                for e in prov_errs + stud_errs:
                    st.write(f"- {e}")
            else:
                st.success("🎉 Congratulations! Your data are valid.")
                st.session_state["session_data"] = session_df
                st.session_state["student_data"]  = student_df
                with st.expander("Preview Data"):
                    st.write("### session Data Sample")
                    st.dataframe(session_df.head())
                    st.write("### Student Data Sample")
                    st.dataframe(student_df.head())

        except Exception as e:
            st.error(f"Error reading files: {e}")
    else:
        st.info("Please upload both CSV files to proceed.")

# ---- STEP 2: ANALYSIS SETTINGS ----
with tab2:
    st.header("2. Adjust Parameters")
    if st.session_state["session_data"] is not None and st.session_state["student_data"] is not None:
        # User inputs
        full_dosage_threshold = st.number_input(
            "Full dosage threshold (hours)",
            min_value=0.0,
            value=st.session_state.get("full_dosage_threshold", 60.0),
            step=1.0
        )
        total_cost = st.number_input(
            "Total program cost (in dollars)",
            min_value=0.0,
            value=st.session_state.get("total_cost", 0.0),
            step=100.0,
            help="Used to calculate cost per student and cost per point."
        )

        # Store values in session state
        st.session_state["full_dosage_threshold"] = full_dosage_threshold
        st.session_state["total_cost"] = total_cost

        st.success("Parameters updated.")
    else:
        st.warning("No data available. Go to Step 1 to upload data first.")


# ---- STEP 3: CHARTS & RESULTS ----
with tab3:
    st.header("3. View Charts & Metrics")
    st.write("---")
    st.subheader("Dosage Insights")
    if st.session_state["session_data"] is not None and st.session_state["student_data"] is not None:
        session_df = st.session_state["session_data"]
        student_df = st.session_state["student_data"]

        try:
            # Data prep
            session_df['student_id'] = session_df['student_id'].astype(str).str.strip()
            student_df['student_id'] = student_df['student_id'].astype(str).str.strip()

            merged_session_df = session_df.merge(student_df, on="student_id", how="inner")
            merged_session_df['session_duration_hours'] = (merged_session_df['session_duration'] / 60).round()

            tutoring_hours_per_student = merged_session_df.groupby("student_id")["session_duration_hours"].sum().reset_index()
            tutoring_hours_per_student['session_duration_hours'] = tutoring_hours_per_student['session_duration_hours'].round()

            # Retrieve threshold and total cost
            full_dosage_threshold = st.session_state.get("full_dosage_threshold", 60.0)
            total_cost = st.session_state.get("total_cost", 0.0)

            # Categorize dosage
            tutoring_hours_per_student['dosage_category'] = tutoring_hours_per_student['session_duration_hours'].apply(
                lambda x: "Below Full Dosage" if x < full_dosage_threshold else "Full Dosage or Above"
            )

            # Distribution
            hourly_distribution = tutoring_hours_per_student.groupby(
                ['session_duration_hours', 'dosage_category']
            ).size().reset_index(name='student_count')

            # Plotly bar chart
            fig = px.bar(
                hourly_distribution,
                x="session_duration_hours",
                y="student_count",
                color="dosage_category",
                color_discrete_map={
                    "Below Full Dosage": "#FF6384",  # Example palette
                    "Full Dosage or Above": "#36A2EB"
                },
                labels={
                    "session_duration_hours": "Total Tutoring Hours (Rounded)",
                    "student_count": "Number of Students",
                    "dosage_category": "Dosage Category"
                },
                title="Distribution of Tutoring Hours per Student"
            )
            fig.update_layout(
                xaxis=dict(dtick=5),
                bargap=0.1,
                legend_title="Dosage Category",
                yaxis_title="Number of Students"
            )
            # Vertical line for threshold
            fig.add_vline(
                x=full_dosage_threshold,
                line_width=2,
                line_dash="dash",
                line_color="orange",
                annotation_text="Dosage Threshold",
                annotation_position="top right"
            )
            st.plotly_chart(fig, use_container_width=True)

            # Calculate percentage of students receiving full dosage
            full_dosage_students = tutoring_hours_per_student[
                tutoring_hours_per_student['dosage_category'] == "Full Dosage or Above"
            ].shape[0]
            total_students = tutoring_hours_per_student.shape[0]
            if total_students > 0:
                percentage_full_dosage = (full_dosage_students / total_students) * 100
            else:
                percentage_full_dosage = 0

            # Display percentage
            st.write(f"**{percentage_full_dosage:.2f}% of students** are receiving the full dosage or above.")

            # Cost metrics
            st.write("---")
            st.subheader("Cost Analysis")

            col1, col2, col3 = st.columns(3)
            total_students = len(tutoring_hours_per_student)
            if total_students > 0:
                cost_per_student = total_cost / total_students
                col1.metric(
                    label="Cost Per Student",
                    value=f"${cost_per_student:,.2f}",
                    delta=f"Total Students: {total_students}",
                    help="Cost Per Student: `Total Cost / Total Students`\n\nThis metric represents the average cost allocated for each student."
                )
            else:
                st.warning("No students found.")

            # Value-added calculations
            student_df['ela_value_added'] = (
                (student_df['ela_state_score_current_year'] - student_df['ela_state_score_one_year_ago']) -
                (student_df['ela_state_score_one_year_ago'] - student_df['ela_state_score_two_years_ago'])
            )
            student_df['math_value_added'] = (
                (student_df['math_state_score_current_year'] - student_df['math_state_score_one_year_ago']) -
                (student_df['math_state_score_one_year_ago'] - student_df['math_state_score_two_years_ago'])
            )
            average_ela_value_added = student_df['ela_value_added'].mean()
            average_math_value_added = student_df['math_value_added'].mean()
            average_total_value_added = (average_ela_value_added + average_math_value_added) / 2

            # Raw point gains (from two years ago to current year)
            student_df['ela_raw_points_gained'] = student_df['ela_state_score_current_year'] - student_df['ela_state_score_two_years_ago']
            student_df['math_raw_points_gained'] = student_df['math_state_score_current_year'] - student_df['math_state_score_two_years_ago']
            average_ela_raw_gain = student_df['ela_raw_points_gained'].mean()
            average_math_raw_gain = student_df['math_raw_points_gained'].mean()
            average_total_raw_gain = (average_ela_raw_gain + average_math_raw_gain) / 2

            # Value-Added Analysis Tooltip (always present)
            value_added_help = (
                "Value-Added Cost Per Point:\n\n"
                "• $VA = (S_{current} - S_{1yr}) - (S_{1yr} - S_{2yr})$\n\n"
                "• $\\text{Average VA} = \\frac{\\text{ELA VA} + \\text{Math VA}}{2}$\n\n"
                "This metric shows the cost for each additional point of improvement beyond the typical yearly change."
            )

            if average_total_value_added < 1:
                value_added_help += "\n\nNote: The average value-added is less than 1 point, indicating non-substantial improvement."

            st.write("### 📈 Value-Added Analysis")
            if average_total_value_added >= 1:
                value_added_cost_per_point = total_cost / average_total_value_added
                st.metric(
                    label="Value-Added Cost Per Point",
                    value=f"${value_added_cost_per_point:.2f} per point",
                    delta=f"Avg. Value-Added: {average_total_value_added:.2f} points",
                    help=value_added_help
                )
            else:
                st.metric(
                    label="Value-Added Cost Per Point",
                    value="N/A",
                    delta=f"Avg. Value-Added: {average_total_value_added:.2f} points",
                    help=value_added_help
                )

            # Raw Cost Per Point, Per Student
            if average_total_raw_gain > 0:
                raw_cost_per_point = total_cost / (average_total_raw_gain * total_students)
                st.metric(
                    label="Raw Cost Per Point, Per Student",
                    value=f"${raw_cost_per_point:.2f} per point, per student",
                    delta=f"Avg. Total Points Gained: {average_total_raw_gain:.2f} points",
                    help="Raw Cost Per Point, Per Student:\n\n"
                        "• $\\text{Cost Per Point} = \\frac{\\text{Total Cost}}{\\text{Avg Total Raw Gain} × \\text{Total Students}}$\n\n"
                        "This metric shows the average cost incurred for each point of raw score improvement per student."
                )
            else:
                st.warning("No raw points gained on average. Check your dataset.")

            #
            st.write("---")
            st.subheader("More in-depth tools below:")
            buttons_html = """
            <div style="display: flex; justify-content: space-evenly; align-items: center; flex-wrap: wrap;">
                <a href="https://studentsupportaccelerator.org/tutoring" target="_blank">
                    <button style="background-color: transparent; color: rgb(255,255,255); padding: 0.5em 1em; 
                                    border: 2px solid rgb(255,255,255); border-radius: 4px; cursor: pointer;">
                        Toolkit for Tutoring Programs
                    </button>
                </a>
                <a href="https://accelerate.us/cost-analysis-tool/" target="_blank">
                    <button style="background-color: transparent; color: rgb(255,255,255); padding: 0.5em 1em; 
                                    border: 2px solid rgb(255,255,255); border-radius: 4px; cursor: pointer;">
                        Cost-Analysis Tool
                    </button>
                </a>
                <a href="https://accelerate.us/state-field-guide/ target="_blank">
                    <button style="background-color: transparent; color: rgb(255,255,255); padding: 0.5em 1em; 
                                    border: 2px solid rgb(255,255,255); border-radius: 4px; cursor: pointer;">
                        State Field Guide
                    </button>
                </a>
                <a href="https://docs.google.com/spreadsheets/d/1x8Y2kNCWsixtWp_MAZn_m7_XjBQ8y6iHTc11OS4fixE/edit?gid=2003973770#gid=2003973770" target="_blank">
                    <button style="background-color: transparent; color: rgb(255,255,255); padding: 0.5em 1em; 
                                    border: 2px solid rgb(255,255,255); border-radius: 4px; cursor: pointer;">
                        Data Dictionary
                    </button>
                </a>
            </div>
            """

            st.markdown(buttons_html, unsafe_allow_html=True)
            #
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
    else:
        st.info("Please complete Steps 1 and 2 before viewing results.")

st.write("---")
st.caption("Ensure your files are formatted correctly before uploading. You can validate your data at our [validator](https://jasongodfrey.info/data_validator.html).")
st.caption("Once you refresh, all data are erased. You may run this tool [locally](https://github.com/accelerate-usa/tutor-data-standard/tree/main/toolkit).")