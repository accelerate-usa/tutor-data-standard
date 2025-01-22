#%%
import pandas as pd
import random
from faker import Faker

# Initialize Faker
fake = Faker()

# Define plausible values for the dataset
ethnicities = ["Hispanic", "Asian", "Black", "White", "Native American", "Pacific Islander", "Other"]

# Function to determine performance level based on average score
def get_performance_level(ela_score, math_score):
    avg_score = (ela_score + math_score) / 2
    if avg_score < 675:
        return "basic"
    elif avg_score < 725:
        return "proficient"
    else:
        return "advanced"

# Function to generate a fake dataset
def generate_fake_dataset(num_rows):
    data = []

    # Calculate the number of schools and districts
    num_schools = max(1, num_rows // 150)
    num_districts = max(1, num_schools // 3)

    # Generate unique district details
    district_ids = [fake.unique.random_number(digits=7, fix_len=True) for _ in range(num_districts)]
    district_names = [fake.company().replace(",", "") + " School District" for _ in range(num_districts)]

    # Generate unique school details, associating each school with a district
    school_details = []
    for _ in range(num_schools):
        district_index = random.randint(0, num_districts - 1)
        school_details.append({
            "school_id": fake.unique.random_number(digits=6, fix_len=True),
            "school_name": fake.company().replace(",", "") + " High School",
            "district_id": district_ids[district_index],
            "district_name": district_names[district_index]
        })

    for i in range(num_rows):
        student_id = fake.unique.random_number(digits=10, fix_len=True)

        # Assign student to a school
        school = random.choice(school_details)

        current_grade_level = random.randint(-1, 12)
        gender = random.choice([True, False])  # True = Male, False = Female
        ethnicity = random.choice(ethnicities)
        ell = random.choice([True, False])
        iep = random.choice([True, False])
        gifted_flag = random.choice([True, False])
        homeless_flag = random.choice([True, False])
        disability = random.choice([True, False])
        economic_disadvantage = random.choice([True, False])

        # Generate scores with growth over years
        ela_growth = random.uniform(5, 50)  # Random growth range for ELA
        math_growth = random.uniform(5, 50)  # Random growth range for Math

        ela_state_score_two_years_ago = random.randint(600, 750)
        ela_state_score_one_year_ago = ela_state_score_two_years_ago + int(ela_growth * random.uniform(0.4, 0.6))
        ela_state_score_current_year = ela_state_score_one_year_ago + int(ela_growth * random.uniform(0.4, 0.6))

        math_state_score_two_years_ago = random.randint(600, 750)
        math_state_score_one_year_ago = math_state_score_two_years_ago + int(math_growth * random.uniform(0.4, 0.6))
        math_state_score_current_year = math_state_score_one_year_ago + int(math_growth * random.uniform(0.4, 0.6))

        # Assign performance levels based on average scores
        performance_level_two_years_ago = get_performance_level(
            ela_state_score_two_years_ago, math_state_score_two_years_ago
        )
        performance_level_prior_year = get_performance_level(
            ela_state_score_one_year_ago, math_state_score_one_year_ago
        )
        performance_level_current_year = get_performance_level(
            ela_state_score_current_year, math_state_score_current_year
        )

        data.append({
            "student_id": str(student_id),
            "district_id": str(school["district_id"]),
            "district_name": school["district_name"],
            "school_id": str(school["school_id"]),
            "school_name": school["school_name"],
            "current_grade_level": current_grade_level,
            "gender": gender,
            "ethnicity": ethnicity,
            "ell": ell,
            "iep": iep,
            "gifted_flag": gifted_flag,
            "homeless_flag": homeless_flag,
            "disability": disability,
            "economic_disadvantage": economic_disadvantage,
            "ela_state_score_two_years_ago": ela_state_score_two_years_ago,
            "ela_state_score_one_year_ago": ela_state_score_one_year_ago,
            "ela_state_score_current_year": ela_state_score_current_year,
            "math_state_score_two_years_ago": math_state_score_two_years_ago,
            "math_state_score_one_year_ago": math_state_score_one_year_ago,
            "math_state_score_current_year": math_state_score_current_year,
            "performance_level_two_years_ago": performance_level_two_years_ago,
            "performance_level_prior_year": performance_level_prior_year,
            "performance_level_current_year": performance_level_current_year
        })

    return pd.DataFrame(data)

# Generate a dataset of arbitrary length (e.g., 100 rows)
dataset = generate_fake_dataset(1000)

# Save the dataset to a CSV file
dataset.to_csv("fake_student_dataset.csv", index=False)

print("Fake dataset generated and saved to 'fake_student_dataset.csv'")

# %%
