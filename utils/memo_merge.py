# utils/memo_merge.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple, Dict, Optional

import pandas as pd


DEFAULT_FILL_COLS = (
    "AE",
    "Buyer",
    "Department",
    "RA_Issued",
    "image_url",
    "Disposition",
    "Comments",
    "Date_RA_Issued",
)


@dataclass(frozen=True)
class MergeDiagnostics:
    mapping_rows: int
    fact_rows: int
    fact_distinct_styles: int
    mapping_distinct_styles: int
    missing_style_rows: int
    missing_styles_top: pd.DataFrame
    unused_mapping_styles_top: pd.DataFrame


def _normalize_key(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.upper()


def _blank_to_na(s: pd.Series) -> pd.Series:
    # Treat empty/whitespace-only strings as NA
    return s.astype(str).str.strip().replace("", pd.NA)


def apply_memo_style_merge(
    df: pd.DataFrame,
    merge_csv_path: str,
    *,
    df_key: str = "Style",
    map_key: str = "Style",
    fill_cols: Iterable[str] = DEFAULT_FILL_COLS,
    strict_unique: bool = True,
) -> Tuple[pd.DataFrame, MergeDiagnostics]:
    """
    Merge a style-level mapping CSV into memo facts on Style.
    - Normalizes Style keys (strip + upper)
    - Enforces unique Style in mapping (optional)
    - Fills df values only when blank/NA (never overwrites populated values)
    Returns (merged_df, diagnostics)
    """
    if df_key not in df.columns:
        raise KeyError(f"apply_memo_style_merge: df is missing key column '{df_key}'")

    map_df = pd.read_csv(merge_csv_path)

    if map_key not in map_df.columns:
        raise KeyError(f"apply_memo_style_merge: mapping is missing key column '{map_key}'")

    # Normalize keys
    df = df.copy()
    df[df_key] = _normalize_key(df[df_key])
    map_df = map_df.copy()
    map_df[map_key] = _normalize_key(map_df[map_key])

    # Enforce 1 row per Style in mapping
    if strict_unique:
        dupes = map_df[map_df.duplicated(map_key, keep=False)].sort_values(map_key)
        if not dupes.empty:
            preview = dupes.head(50).to_string(index=False)
            raise ValueError(
                f"merge file has duplicate '{map_key}' values. Must be 1 row per Style.\n\n{preview}"
            )

    # Prepare mapping cols
    fill_cols = tuple(fill_cols)
    keep_cols = [map_key] + [c for c in fill_cols if c in map_df.columns]
    map_df = map_df[keep_cols].copy()

    # Rename mapping key to match df key for merge
    if map_key != df_key:
        map_df = map_df.rename(columns={map_key: df_key})

    merged = df.merge(map_df, on=df_key, how="left", suffixes=("", "_map"))

    # Fill only blanks in df from mapping
    for col in fill_cols:
        map_col = f"{col}_map"
        if map_col not in merged.columns:
            continue

        # If df doesn't have the column, create it as NA so mapping can populate it
        if col not in merged.columns:
            merged[col] = pd.NA

        merged[col] = _blank_to_na(merged[col]).fillna(merged[map_col])
        merged = merged.drop(columns=[map_col])

    # Diagnostics
    fact_styles = merged[df_key].dropna()
    mapping_styles = map_df[df_key].dropna() if df_key in map_df.columns else pd.Series([], dtype=str)

    missing_mask = merged[df_key].notna() & (
        merged["AE"].isna() if "AE" in merged.columns else False
    )
    # If AE isn't present (unlikely), just count missing key matches by checking one mapping field
    if "AE" not in merged.columns:
        probe = "Buyer" if "Buyer" in merged.columns else None
        if probe:
            missing_mask = merged[df_key].notna() & merged[probe].isna()
        else:
            missing_mask = merged[df_key].notna() & False

    missing_styles_top = (
        merged.loc[missing_mask, df_key]
        .value_counts()
        .rename_axis(df_key)
        .reset_index(name="rows_missing")
        .head(50)
    )

    unused_mapping_styles_top = (
        map_df.loc[~map_df[df_key].isin(fact_styles.unique()), df_key]
        .value_counts()
        .rename_axis(df_key)
        .reset_index(name="mapping_rows_unused")
        .head(50)
    )

    diag = MergeDiagnostics(
        mapping_rows=len(map_df),
        fact_rows=len(df),
        fact_distinct_styles=int(fact_styles.nunique()),
        mapping_distinct_styles=int(map_df[df_key].nunique()),
        missing_style_rows=int(missing_mask.sum()),
        missing_styles_top=missing_styles_top,
        unused_mapping_styles_top=unused_mapping_styles_top,
    )

    return merged, diag
