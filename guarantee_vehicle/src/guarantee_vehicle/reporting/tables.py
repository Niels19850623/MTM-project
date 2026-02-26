from __future__ import annotations

import pandas as pd


def to_markdown_table(records: list[dict]) -> str:
    return pd.DataFrame(records).to_markdown(index=False)
