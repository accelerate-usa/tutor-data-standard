#%%
import pandas as pd
import plotly.express as px
import numpy as np

# URL for exporting the Google Sheet as CSV
sheet_url = "https://docs.google.com/spreadsheets/d/19DyIaUfZtlpQKu-l_4UnfeyEoeRySUjKGL3jR5eyuoA/export?format=csv&gid=987900147"

# Read the Google Sheet data into a DataFrame
df = pd.read_csv(sheet_url)

# Ensure the latitude and longitude columns are floats
df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')

# Ensure the number of students served is an integer
df['# of students served through Accelerate'] = pd.to_numeric(
    df['# of students served through Accelerate'], errors='coerce'
).fillna(0).astype(int)

# Ensure the number of schools served is an integer
df['# of schools served through Accelerate'] = pd.to_numeric(
    df['# of schools served through Accelerate'], errors='coerce'
).fillna(0).astype(int)

# Drop rows with missing coordinates
df = df.dropna(subset=['Latitude', 'Longitude'])

# Non-linear scaling for the dot size using square root
df['scaled_size'] = np.sqrt(df['# of students served through Accelerate'])

# Create hover text with Grantee Name, District (first 3 words), and Students Served (formatted with commas)
df['hover_text'] = (
    '<b>Grantee:</b> ' + df['Grantee Name'] +
    '<br><b>District:</b> ' + df['District'].fillna('N/A').str.split().str[:3].str.join(' ') +
    '<br><b>Students Served:</b> ' + df['# of students served through Accelerate'].map('{:,}'.format)
)

# Calculate summary statistics with comma formatting
total_schools = '{:,}'.format(df['# of schools served through Accelerate'].sum())
total_students = '{:,}'.format(df['# of students served through Accelerate'].sum())
total_agencies = '{:,}'.format(df['Grantee Name'].nunique())

# Define color palette
colors = {
    "main_1": "#304A6F",
    "main_2": "#658DC0",
    "accent": "#10A59C",
    "neutral": "#E0E2E7",
    "dark_neutral": "#0F1D2F"
}

# Create the Plotly map with non-linear dot size scaling
fig = px.scatter_mapbox(
    df,
    lat='Latitude',
    lon='Longitude',
    size='scaled_size',
    size_max=30,  # Limit maximum size for better balance
    hover_name='Grantee Name',
    custom_data=['hover_text'],
    title='<b>Agencies pledged to the open DATAS standard</b>',
    zoom=3
)

# Update hover template
fig.update_traces(
    marker=dict(color=colors['main_1']),
    hovertemplate='%{customdata[0]}'
)

# Set map layout to focus on the United States with custom colors
fig.update_layout(
    mapbox=dict(
        style='carto-positron',
        center=dict(lat=37.0902, lon=-95.7129),
        zoom=3
    ),
    margin={"r": 0, "t": 60, "l": 0, "b": 0},
    height=700,
    title_font=dict(family="Poppins, sans-serif", size=22, color=colors['main_1']),
    title_x=0.5,  # Center-align the title
    paper_bgcolor=colors['neutral'],
    font=dict(family="Castoro, serif", color=colors['dark_neutral'])
)

annotations = [
    dict(
        text=f"<b>Total Schools:</b> {total_schools}",
        x=0.01, y=0.95, xref="paper", yref="paper",
        showarrow=False, font=dict(size=16, family="Poppins, sans-serif", color=colors['dark_neutral']),
        bgcolor=f"rgba(224, 226, 231, 0.8)", bordercolor=colors['main_1']
    ),
    dict(
        text=f"<b>Total Students:</b> {total_students}",
        x=0.01, y=0.90, xref="paper", yref="paper",
        showarrow=False, font=dict(size=16, family="Poppins, sans-serif", color=colors['dark_neutral']),
        bgcolor=f"rgba(224, 226, 231, 0.8)", bordercolor=colors['main_1']
    ),
    dict(
        text=f"<b>Total Agencies:</b> {total_agencies}",
        x=0.01, y=0.85, xref="paper", yref="paper",
        showarrow=False, font=dict(size=16, family="Poppins, sans-serif", color=colors['dark_neutral']),
        bgcolor=f"rgba(224, 226, 231, 0.8)", bordercolor=colors['main_1']
    )
]

fig.update_layout(annotations=annotations)

# Show the map
fig.write_html('pledge_map.html')
fig.show()

# %%
