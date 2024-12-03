#%%
import csv
import random
import string

def generate_csv(n, filename):
    # Define headers as per the data dictionary
    headers = [
        "student_id",
        "district_id",
        "district_name",
        "school_id",
        "school_name",
        "current_grade_level",
        "gender",
        "ethnicity",
        "ell",
        "iep",
        "gifted_flag",
        "homeless_flag",
        "ela_state_score_two_years_ago",
        "ela_state_score_one_year_ago",
        "ela_state_score_current_year",
        "math_state_score_two_years_ago",
        "math_state_score_one_year_ago",
        "math_state_score_current_year",
        "performance_level_prior_year",
        "performance_level_current_year",
        "disability",
        "economic disadvantage"
    ]

    # Define possible values for certain fields
    genders = ['Male', 'Female']
    boolean_values = ['TRUE', 'FALSE']
    ethnicities = ['Ethnicity ' + str(i) for i in range(1, 11)]  # Up to 10 unique ethnicities
    performance_levels = ['Level ' + str(i) for i in range(1, 7)]  # Up to 6 unique levels
    district_names = ['District ' + str(i) for i in range(1, 6)]  # Sample district names
    school_names = ['School ' + str(i) for i in range(1, 11)]     # Sample school names

    # Keep track of used IDs to ensure uniqueness
    used_student_ids = set()

    with open(filename, mode='w', newline='') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=headers)
        writer.writeheader()

        for _ in range(n):
            # Generate unique student_id (10-digit integer as a string)
            while True:
                student_id = ''.join(random.choices(string.digits, k=10))
                if student_id not in used_student_ids:
                    used_student_ids.add(student_id)
                    break

            # Generate district_id (7-digit integer as a string)
            leaids = [ '0100001', '0200001', '0400001', '0500001', '0600001', '0800001', '0900001', '1000001', '1100001', '1200001',]
            district_id = random.choice(leaids)
            district_name = random.choice(district_names)

            # Generate school_id (6-digit integer as a string)
            school_id = ''.join(random.choices(string.digits, k=6))
            school_name = random.choice(school_names)

            # Generate other fields according to their constraints
            current_grade_level = random.randint(0, 12)
            gender = random.choice(genders)
            ethnicity = random.choice(ethnicities)
            ell = random.choice(boolean_values)
            iep = random.choice(boolean_values)
            gifted_flag = random.choice(boolean_values)
            homeless_flag = random.choice(boolean_values)
            ela_score_two_years_ago = random.randint(650, 800)
            ela_score_one_year_ago = random.randint(650, 800)
            ela_score_current_year = random.randint(650, 800)
            math_score_two_years_ago = random.randint(650, 800)
            math_score_one_year_ago = random.randint(650, 800)
            math_score_current_year = random.randint(650, 800)
            performance_level_prior_year = random.choice(performance_levels)
            performance_level_current_year = random.choice(performance_levels)
            disability = random.choice(boolean_values)
            economic_disadvantage = random.choice(boolean_values)

            # Create a dictionary for the row
            row = {
                "student_id": student_id,
                "district_id": district_id,
                "district_name": district_name,
                "school_id": school_id,
                "school_name": school_name,
                "current_grade_level": current_grade_level,
                "gender": gender,
                "ethnicity": ethnicity,
                "ell": ell,
                "iep": iep,
                "gifted_flag": gifted_flag,
                "homeless_flag": homeless_flag,
                "ela_state_score_two_years_ago": ela_score_two_years_ago,
                "ela_state_score_one_year_ago": ela_score_one_year_ago,
                "ela_state_score_current_year": ela_score_current_year,
                "math_state_score_two_years_ago": math_score_two_years_ago,
                "math_state_score_one_year_ago": math_score_one_year_ago,
                "math_state_score_current_year": math_score_current_year,
                "performance_level_prior_year": performance_level_prior_year,
                "performance_level_current_year": performance_level_current_year,
                "disability": disability,
                "economic disadvantage": economic_disadvantage
            }

            # Write the row to the CSV file
            writer.writerow(row)

    print(f"CSV file '{filename}' with {n} rows has been generated successfully.")

generate_csv(10000, 'school_data.csv')

# %%
