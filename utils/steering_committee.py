#%%
import gspread
import pandas as pd

with open('key.txt') as f:
    sheet_key = f.read().strip()

# Access the Google Sheet using gspread
gc = gspread.service_account()
worksheet = gc.open_by_key(sheet_key).worksheet('Form Responses 1')

# Fetch all data and convert it to a DataFrame
df = pd.DataFrame(worksheet.get_all_records()).apply(lambda x: x.str.strip())

# Define leads
leads = ["Jason Godfrey", "Britta Tremblay", "Jennifer Bronson"]

# Separate first three members and sort remaining alphabetically
first_three = df[df['Name'].isin(leads)]
remaining_members = df[~df['Name'].isin(leads)].sort_values('Name')

# Combine first three with the sorted remaining members
ordered_members = pd.concat([first_three, remaining_members])

# Function to generate the HTML table with proper formatting
def generate_html_table(df):
    rows = []
    
    for i in range(0, len(df), 3):
        row = ""
        for _, member in df.iloc[i:i+3].iterrows():
            img_name = member['Name'].replace(" ", "").lower()
            img_path = f"img/{img_name}.jpg"
            row += (
                f'            <td align="center">\n'
                f'                <img src="{img_path}" alt="{member["Name"]}" width="100"/><br>\n'
                f'                <strong>{member["Name"]}</strong><br>\n'
                f'                <em>{member["Title"]}</em><br>\n'
                f'                <span>{member["Organization"]}</span>\n'
                f'            </td>\n'
            )
        row += '            <td></td>\n' * (3 - len(df.iloc[i:i+3]))
        rows.append(f"        <tr>\n{row}        </tr>\n")

    return (
        "<table>\n"
        "    <thead>\n"
        "        <tr>\n"
        "            <th>Steering Committee Members</th>\n"
        "            <th></th>\n"
        "            <th></th>\n"
        "        </tr>\n"
        "    </thead>\n"
        "    <tbody>\n"
        f"{''.join(rows)}"
        "    </tbody>\n"
        "</table>"
    )

html_table = generate_html_table(ordered_members)
print(html_table)
# %%
