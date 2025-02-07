import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="DATAS Analysis Toolkit", layout="wide")

# Title
st.title("📊 DATAS Analysis Toolkit")

# Tabs
tab1, tab2, tab3 = st.tabs(["Step 1: Upload Data", "Step 2: Analysis Settings", "Step 3: Charts & Results"])

# Session state to hold data
if "provider_data" not in st.session_state:
    st.session_state["provider_data"] = None
if "student_data" not in st.session_state:
    st.session_state["student_data"] = None

# ---- STEP 1: UPLOAD DATA ----
with tab1:
    st.header("1. Upload Your Data")
    st.write("Feel free to use our example [student](https://drive.google.com/file/d/1FjTLaWGRQd6zlgaXkqHkAU_Gj8kUzgGY/view) and [session](https://drive.google.com/file/d/1ivNs9gFkIIgiABUHEOvsm8mCmvg9nKJ3/view) datasets to explore the toolkit.")
    st.write("To use your own data, upload your session and student below. Be sure that your data is formatted according to our [data dictionary](https://accelerate.us/datas-validator). Our [validator](https://accelerate.us/datas-validator) can help you troubleshoot your data formatting.") 

    uploaded_provider_file = st.file_uploader("Upload Tutoring Session Data (CSV)", type="csv", key="provider_uploader")
    uploaded_student_file = st.file_uploader("Upload Student Data (CSV)", type="csv", key="student_uploader")

    if uploaded_provider_file and uploaded_student_file:
        try:
            provider_df = pd.read_csv(uploaded_provider_file)
            student_df = pd.read_csv(uploaded_student_file)
            st.session_state["provider_data"] = provider_df
            st.session_state["student_data"] = student_df

            st.success("Files uploaded successfully.")
            with st.expander("Preview Data"):
                st.write("### Provider Data Sample")
                st.dataframe(provider_df.head())
                st.write("### Student Data Sample")
                st.dataframe(student_df.head())
        except Exception as e:
            st.error(f"Error reading files: {e}")

    else:
        st.info("Please upload both CSV files to proceed.")

# ---- STEP 2: ANALYSIS SETTINGS ----
with tab2:
    st.header("2. Adjust Parameters")
    if st.session_state["provider_data"] is not None and st.session_state["student_data"] is not None:
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
    if st.session_state["provider_data"] is not None and st.session_state["student_data"] is not None:
        provider_df = st.session_state["provider_data"]
        student_df = st.session_state["student_data"]

        try:
            # Data prep
            provider_df['student_id'] = provider_df['student_id'].astype(str)
            student_df['student_id'] = student_df['student_id'].astype(str)

            merged_provider_df = provider_df.merge(student_df, on="student_id", how="inner")
            merged_provider_df['session_duration_hours'] = (merged_provider_df['session_duration'] / 60).round()

            tutoring_hours_per_student = merged_provider_df.groupby("student_id")["session_duration_hours"].sum().reset_index()
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
            full_dosage_students = tutoring_hours_per_student[tutoring_hours_per_student['dosage_category'] == "Full Dosage or Above"].shape[0]
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
                    delta=f"Total Students: {total_students}"
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

            # Average value-added points across students
            average_ela_value_added = student_df['ela_value_added'].mean()
            average_math_value_added = student_df['math_value_added'].mean()
            average_total_value_added = (average_ela_value_added + average_math_value_added) / 2

            # Raw point gains (total points gained from two years ago to current year)
            student_df['ela_raw_points_gained'] = student_df['ela_state_score_current_year'] - student_df['ela_state_score_two_years_ago']
            student_df['math_raw_points_gained'] = student_df['math_state_score_current_year'] - student_df['math_state_score_two_years_ago']
            average_ela_raw_gain = student_df['ela_raw_points_gained'].mean()
            average_math_raw_gain = student_df['math_raw_points_gained'].mean()
            average_total_raw_gain = (average_ela_raw_gain + average_math_raw_gain) / 2

            # Calculate cost per point gained
            if average_total_value_added >= 1:
                value_added_cost_per_point = total_cost / average_total_value_added
                st.write("### 📈 Value-Added Analysis")
                st.metric(
                    label="Value-Added Cost Per Point",
                    value=f"${value_added_cost_per_point:.2f} per point",
                    delta=f"Avg. Value-Added: {average_total_value_added:.2f} points",
                    help="Value-added measures the improvement in student performance, accounting for expected growth."
                )
            else:
                st.write("### 📈 Value-Added Analysis")
                st.warning(f"No value added on average. The average value-added is less than 1 point ({average_total_value_added:.2f}).")

            # Raw cost per point
            if average_total_raw_gain > 0:
                raw_cost_per_point = (total_cost / average_total_raw_gain) / total_students
                st.metric(
                    label="Raw Cost Per Point, Per Student",
                    value=f"${raw_cost_per_point:.2f} per point, per student",
                    delta=f"Avg. Total Points Gained: {average_total_raw_gain:.2f} points",
                    help="This is the cost per point gained, calculated without considering value-added metrics."
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

