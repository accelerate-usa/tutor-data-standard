#%%
import pandas as pd
import random
from faker import Faker
from datetime import datetime, timedelta
import numpy as np

fake = Faker()

def random_school_datetime():
    start_date = datetime(2024, 9, 1)
    end_date = datetime(2025, 6, 30)
    random_date = fake.date_between_dates(date_start=start_date, date_end=end_date)

    start_time = timedelta(hours=8)
    end_time = timedelta(hours=15)
    random_time = start_time + timedelta(seconds=random.randint(0, int((end_time - start_time).total_seconds())))

    return datetime.combine(random_date, datetime.min.time()) + random_time

def generate_tutoring_sessions(student_ids, num_sessions_range=(0, 100)):
    sessions = []
    tutors = [fake.random_number(digits=5, fix_len=True) for _ in range(50)]  # n unique tutors
    
    for student_id in student_ids:
        session_topic = random.choice(["math", "ela"])

        num_sessions = random.randint(*num_sessions_range)

        for _ in range(num_sessions):
            session_date = random_school_datetime()
            session_duration = random.choice([30, 45, 60, 90])
            session_ratio = random.choice(["1:1", "1:2", "1:3", "1:4", "1:5"])
            tutor_id = random.choice(tutors)

            sessions.append({
                "student_id": student_id,
                "session_topic": session_topic,
                "session_date": session_date.strftime("%Y-%m-%d"),
                "session_duration": session_duration,
                "session_ratio": session_ratio,
                "tutor_id": str(tutor_id)
            })

    return pd.DataFrame(sessions)

student_dataset = pd.read_csv("fake_student_dataset.csv")
student_ids = student_dataset["student_id"].tolist()

tutoring_dataset = generate_tutoring_sessions(student_ids)

tutoring_dataset.to_csv("fake_provider_dataset.csv", index=False)

print("Fake provider dataset generated and saved to 'fake_provider_dataset.csv'")
# %%
