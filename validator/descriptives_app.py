import streamlit as st
import pandas as pd

# Streamlit app title
st.title("Tutoring Dosage Analysis")

# File upload section
st.header("Upload your CSV files")
file1 = st.file_uploader("Upload the first CSV file", type=["csv"])
file2 = st.file_uploader("Upload the second CSV file", type=["csv"])

if file1 and file2:
    try:
        # Load the CSV files
        data1 = pd.read_csv(file1)
        data2 = pd.read_csv(file2)
        
        # Combine the datasets
        combined_data = pd.concat([data1, data2], ignore_index=True)

        # Ensure the required column is present
        if "tutoring_hours" not in combined_data.columns:
            st.error("The required column 'tutoring_hours' is missing from the uploaded files.")
        else:
            # Calculate the percentage of children receiving full dosage (60 hours)
            full_dosage = combined_data["tutoring_hours"] >= 60
            full_dosage_percentage = (full_dosage.sum() / len(combined_data)) * 100
            
            # Display results
            st.subheader("Results")
            st.write(f"Total children: {len(combined_data)}")
            st.write(f"Children receiving full dosage (60 hours): {full_dosage.sum()}")
            st.write(f"Percentage of children receiving full dosage: {full_dosage_percentage:.2f}%")
    
    except Exception as e:
        st.error(f"An error occurred while processing the files: {e}")
else:
    st.info("Please upload both CSV files to proceed.")
