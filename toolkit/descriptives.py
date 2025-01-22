#%%
import pandas as pd

# Load the two CSV files
student_data = pd.read_csv("fake_student_dataset.csv")
tutoring_data = pd.read_csv("fake_tutoring_dataset.csv")

# Merge the datasets on the 'student_id'
merged_data = pd.merge(tutoring_data, student_data, on="student_id", how="left") # TODO: WRONG

# Ask the user what is considered a full dose of tutoring (in hours)
full_dose_hours = float(input("Enter the number of hours considered a full dose of tutoring: "))

# Convert session duration from minutes to hours in the tutoring dataset
merged_data["session_duration_hours"] = merged_data["session_duration"] / 60

# Aggregate the total tutoring hours per student
total_tutoring_hours = merged_data.groupby("student_id")["session_duration_hours"].sum()
total_tutoring_hours = total_tutoring_hours.reset_index()
total_tutoring_hours.rename(columns={"session_duration_hours": "total_hours"}, inplace=True)

# Merge the aggregated data back to the student dataset
final_data = pd.merge(student_data, total_tutoring_hours, on="student_id", how="left")
final_data["total_hours"] = final_data["total_hours"].fillna(0)  # Fill NaN with 0 for students with no sessions

# Calculate the percentage of students who received a full dose of tutoring
students_with_full_dose = final_data[final_data["total_hours"] >= full_dose_hours].shape[0]
total_students = final_data.shape[0]
percentage_with_full_dose = (students_with_full_dose / total_students) * 100

# Output the results
print(f"{percentage_with_full_dose:.2f}% of students received a full dosage of tutoring (at least {full_dose_hours} hours).")

# Save the final merged dataset to a new CSV
final_data.to_csv("merged_tutoring_data.csv", index=False)

print("Merged data saved to 'merged_tutoring_data.csv'")

# %%
