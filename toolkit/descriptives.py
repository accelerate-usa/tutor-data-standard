import pandas as pd
import streamlit as st
import plotly.express as px

st.title("📊 Tutoring Hours and Cost Analysis")
st.write("Analyze your tutoring program's hours, cost per student, and cost per point gained dynamically.")

# File upload
st.sidebar.title("Upload Your Data")
uploaded_provider_file = st.sidebar.file_uploader("Upload Tutoring Session Data (CSV)", type="csv")
uploaded_student_file = st.sidebar.file_uploader("Upload Student Data (CSV)", type="csv")

try:
    if uploaded_provider_file is not None and uploaded_student_file is not None:
        # Load the uploaded files
        provider_df = pd.read_csv(uploaded_provider_file)
        student_df = pd.read_csv(uploaded_student_file)

        # Ensure `student_id` is consistent across datasets
        provider_df['student_id'] = provider_df['student_id'].astype(str)
        student_df['student_id'] = student_df['student_id'].astype(str)

        # Merge datasets
        merged_provider_df = provider_df.merge(student_df, on="student_id", how="inner")

        # Convert session duration to hours and round to the nearest integer
        merged_provider_df['session_duration_hours'] = (merged_provider_df['session_duration'] / 60).round()

        # Calculate total tutoring hours per student
        tutoring_hours_per_student = merged_provider_df.groupby("student_id")["session_duration_hours"].sum().reset_index()

        # Round the total hours to the nearest integer
        tutoring_hours_per_student['session_duration_hours'] = tutoring_hours_per_student['session_duration_hours'].round()

        # User input for full dosage threshold
        st.sidebar.title("Customize Analysis")
        full_dosage_threshold = st.sidebar.number_input(
            "Enter the full dosage threshold in hours:",
            min_value=0.0,
            value=40.0,  # Default threshold
            step=1.0
        )

        # Add a column indicating the dosage category
        tutoring_hours_per_student['dosage_category'] = tutoring_hours_per_student['session_duration_hours'].apply(
            lambda x: "Below Full Dosage" if x < full_dosage_threshold else "Full Dosage or Above"
        )

        # Count students per hour and category
        hourly_distribution = tutoring_hours_per_student.groupby(
            ['session_duration_hours', 'dosage_category']
        ).size().reset_index(name='student_count')

        # Create a bar chart
        fig = px.bar(
            hourly_distribution,
            x="session_duration_hours",
            y="student_count",
            color="dosage_category",
            color_discrete_map={
                "Below Full Dosage": "red",
                "Full Dosage or Above": "blue"
            },
            labels={
                "session_duration_hours": "Total Tutoring Hours (Rounded)",
                "student_count": "Number of Students",
                "dosage_category": "Dosage Category"
            },
            title="Distribution of Tutoring Hours per Student"
        )

        # Customize layout
        fig.update_layout(
            xaxis=dict(
                dtick=5,  # Show labels at intervals of 5 hours
                title="Total Tutoring Hours (Rounded)"
            ),
            bargap=0.1,
            legend=dict(title="Dosage Category"),
            yaxis_title="Number of Students"
        )

        # Display the chart
        st.plotly_chart(fig)

        # Allow user to input the total cost of the tutoring program
        st.sidebar.title("Cost Analysis")
        total_cost = st.sidebar.number_input(
            "Enter the total cost of your tutoring program (in dollars):",
            min_value=0.0,
            value=0.0,
            step=100.0,
            help="This is the total cost of the tutoring program, used to calculate the cost per student and cost per point gained."
        )

        # Calculate cost per student
        total_students = len(tutoring_hours_per_student)
        if total_students > 0:
            cost_per_student = total_cost / total_students
            st.write("### 💰 Cost Analysis")
            st.metric(
                label="Cost Per Student",
                value=f"${cost_per_student:.2f}",
                delta=f"Based on {total_students} students",
                help="The cost per student is calculated by dividing the total program cost by the number of students."
            )
        else:
            st.warning("No students found in the dataset. Please check your data.")

        # Calculate value-added points for ELA and Math
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
                help="The cost per point gained is calculated based on the value-added metric and the total program cost."
            )
        else:
            st.write("### 📈 Value-Added Analysis")
            st.warning("No value added on average. The average value-added is less than 1 point.")

        # Raw cost per point
        if average_total_raw_gain > 0:
            raw_cost_per_point = total_cost / average_total_raw_gain
            st.metric(
                label="Raw Cost Per Point",
                value=f"${raw_cost_per_point:.2f} per point",
                delta=f"Avg. Total Points Gained: {average_total_raw_gain:.2f} points",
                help="This is the cost per point gained, calculated without considering value-added metrics."
            )
        else:
            st.warning("No raw points gained on average. Check your dataset.")
    else:
        st.info("Please upload both the tutoring session data and the student data to proceed.")
        st.info(
            "If you have trouble uploading, make sure that your data is formatted correctly using our validator "
            '[here](https://accelerate.us/datas-validator).'
        )
except Exception as e:
    st.error(f"An error occurred: {str(e)}.")
    # st.markdown("---")
    st.info(
        "If you have trouble uploading, make sure that your data is formatted correctly using our validator "
        '[here](https://accelerate.us/datas-validator).'
    )
