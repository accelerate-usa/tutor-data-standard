# DATAS

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)

DATAS, the Data Alignment and Tutoring Assessment Standards project, defines a practical data standard for tutoring implementation and outcomes data. The repo includes the schema, generated data dictionary, validation logic, example datasets, and local dashboards that help districts, providers, researchers, and funders inspect tutoring program data without sending student-level records to an external service.

## What Is Included

1. A canonical student dataset and session dataset schema in [schema/data_dictionary.md](schema/data_dictionary.md).
2. Header-only templates for [students](schema/student_template_header.csv) and [sessions](schema/session_template_header.csv).
3. A Streamlit dashboard at [toolkit/descriptives.py](toolkit/descriptives.py), which is the primary user-facing analysis tool.
4. A standalone browser dashboard at [toolkit/descriptives.html](toolkit/descriptives.html), which provides a local HTML alternative when users do not want to install or run Streamlit.
5. Tests that cover schema normalization, validation, descriptive analytics, generated schema artifacts, and large-file ingest behavior.

## Quick Start

Create a Python environment and install the pinned runtime dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r toolkit\requirements.txt
```

Run the primary Streamlit dashboard:

```powershell
streamlit run toolkit\descriptives.py
```

The dashboard accepts `.csv`, `.xlsx`, `.xls`, and `.json` files. Upload a session file and a student file in the `Upload & Schema` tab, then review validation results before moving through dosage, equity, outcomes, and cost analytics.

## Standalone HTML Dashboard

The standalone dashboard at [toolkit/descriptives.html](toolkit/descriptives.html) is an alternative local path for users who do not want to run a Python app. Open the file in a modern browser, upload the same student and session files, or use the bundled example data to inspect the dashboard immediately.

The HTML version is intended to match the Streamlit app's core validation and descriptive calculations. It is useful for demos, lightweight local review, and teams that need a simple file-based workflow. The Streamlit app remains the canonical implementation when users want the most complete Python workflow.

## Schema

The generated schema artifacts live in [schema](schema):

1. [schema/data_dictionary.md](schema/data_dictionary.md) explains every canonical column.
2. [schema/student_dictionary.csv](schema/student_dictionary.csv) and [schema/session_dictionary.csv](schema/session_dictionary.csv) provide machine-readable dictionaries.
3. [schema/student_template_header.csv](schema/student_template_header.csv) and [schema/session_template_header.csv](schema/session_template_header.csv) provide empty header templates.

Regenerate schema artifacts after changing [schema_registry.py](schema_registry.py):

```powershell
python utils\generate_schema_artifacts.py
```

CI and the local test suite verify that generated schema files are current.

## Example Data

The bundled example files in [utils/example_student_dataset.csv](utils/example_student_dataset.csv) and [utils/example_session_dataset.csv](utils/example_session_dataset.csv) are generated from [utils/generate_datasets.py](utils/generate_datasets.py). They are large enough to exercise the dashboard with realistic distributions while remaining small enough to keep in the repo.

Regenerate them when the schema or example-data assumptions change:

```powershell
python utils\generate_datasets.py
```

## Development

Install the development dependencies:

```powershell
python -m pip install -r requirements-dev.txt
```

Run the standard test suite:

```powershell
pytest -q
```

Run the opt-in million-row scale test before a 1.0 release or other major launch checkpoint:

```powershell
$env:DATAS_RUN_FULL_STRESS_TEST = "1"
pytest -q tests\test_large_ingest.py
```

The scale test writes temporary generated files under pytest's temp directory and does not require checked-in stress fixtures.

## Optional Mapping Profiles

Most users should ignore mapping profiles. They are only for recurring uploads with non-canonical column headers. Advanced users can upload a local JSON mapping profile to reuse known column mappings. The app does not store this profile.

## Security And Privacy

DATAS dashboards are designed for local review. Users should not commit student-level operational data, generated stress data, `.env` files, or local mapping profiles.

## Governance And Contributions

DATAS is stewarded by Accelerate with input from tutoring providers, platforms, school systems, researchers, and philanthropy partners. Contributions are welcome. For substantial schema or dashboard changes, open an issue or pull request that explains the user need, expected behavior, and validation approach.

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
