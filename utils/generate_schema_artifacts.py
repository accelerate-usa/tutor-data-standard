from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from schema_registry import dictionary_dataframe, get_canonical_columns


OUTPUT_DIR = REPO_ROOT / "schema"


def write_markdown_table(df: pd.DataFrame) -> str:
    columns = list(df.columns)
    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join(["---"] * len(columns)) + " |"
    rows = [
        "| " + " | ".join(str(row[column]).replace("\n", " ").strip() for column in columns) + " |"
        for _, row in df.fillna("").iterrows()
    ]
    return "\n".join([header, divider, *rows])


def build_markdown_document() -> str:
    sections = [
        "# Tutor Data Standard Dictionary",
        "",
        "Generated from `schema_registry.py`. Regenerate with `python utils/generate_schema_artifacts.py`.",
        "",
        "Most teams can upload `sessions.csv` and `students.csv` directly in the dashboard.",
        "",
        "> Advanced, optional: the dashboard can apply an uploaded local mapping profile JSON for recurring uploads with non-canonical column headers. Keep this feature documented, but keep it out of the primary upload path. The app does not store the file for the user.",
        "",
    ]

    for dataset in ("student", "session"):
        df = dictionary_dataframe(dataset)
        title = f"{dataset.title()} Dataset"
        sections.extend(
            [
                f"## {title}",
                "",
                f"Canonical columns: `{', '.join(get_canonical_columns(dataset))}`",
                "",
                write_markdown_table(df),
                "",
            ]
        )

    return "\n".join(sections)


def write_outputs() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)

    for dataset in ("student", "session"):
        dictionary_df = dictionary_dataframe(dataset)
        dictionary_df.to_csv(OUTPUT_DIR / f"{dataset}_dictionary.csv", index=False)

        template_df = pd.DataFrame(columns=get_canonical_columns(dataset))
        template_df.to_csv(OUTPUT_DIR / f"{dataset}_template_header.csv", index=False)

    (OUTPUT_DIR / "data_dictionary.md").write_text(build_markdown_document(), encoding="utf-8")


if __name__ == "__main__":
    write_outputs()
    print(f"Wrote schema artifacts to {OUTPUT_DIR}")
