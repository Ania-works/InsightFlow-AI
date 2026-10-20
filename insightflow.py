import csv
import io
import re
from datetime import datetime

import pandas as pd
import streamlit as st
from dashboard import render_dashboard

st.set_page_config(page_title="InsightFlow AI | Phase 3", layout="wide")
st.title("InsightFlow AI")
st.caption("CSV validation, approved cleaning and interactive analytics")

MISSING = {"", "na", "n/a", "null", "none", "nan"}
TYPES = ["Auto / text", "Text", "Integer", "Decimal", "Date (YYYY-MM-DD)", "Boolean (true/false)"]


def load_csv(raw):
    if not raw:
        raise ValueError("The uploaded file is empty.")
    if b"\x00" in raw:
        raise ValueError("The file contains NUL bytes and may not be a text CSV.")
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(f"UTF-8 decoding failed near byte {exc.start}. Export the file as UTF-8 CSV.") from exc
    try:
        rows = list(csv.reader(io.StringIO(content, newline=""), strict=True))
    except csv.Error as exc:
        raise ValueError(f"Malformed CSV quoting: {exc}") from exc
    if not rows or not rows[0]:
        raise ValueError("No CSV header row was found.")
    headers = rows[0]
    if len(headers) == 1 and any(x in headers[0] for x in (";", "\t")):
        raise ValueError("The file appears to use semicolons or tabs rather than commas. Export a comma-separated CSV.")
    if any(not h.strip() for h in headers):
        raise ValueError("The header row contains an empty column name.")
    if len(headers) != len(set(headers)):
        dup = sorted({h for h in headers if headers.count(h) > 1})
        raise ValueError(f"Duplicate CSV column names: {', '.join(dup)}")
    for i, row in enumerate(rows[1:], start=2):
        if len(row) != len(headers):
            raise ValueError(f"CSV record {i}: expected {len(headers)} fields based on the header, found {len(row)}. Check commas and quotation marks. (Record number may differ from physical line number for multiline fields.)")
    if len(rows) == 1:
        raise ValueError("The CSV has headers but no data records.")
    # Read as strings to avoid silently changing IDs, postal codes, and malformed numbers.
    frame = pd.DataFrame(rows[1:], columns=headers, dtype="string")
    frame = frame.replace(r"^\s*$", pd.NA, regex=True)
    return frame


def missing_mask(series):
    return series.isna() | series.astype("string").str.strip().str.lower().isin(MISSING).fillna(False)


def valid_value(value, kind):
    if kind in ("Auto / text", "Text"):
        return True
    s = str(value).strip()
    if kind == "Integer":
        return bool(re.fullmatch(r"[+-]?\d+", s))
    if kind == "Decimal":
        try:
            number = float(s)
            return pd.notna(number) and number not in (float("inf"), float("-inf"))
        except ValueError:
            return False
    if kind == "Date (YYYY-MM-DD)":
        try:
            datetime.strptime(s, "%Y-%m-%d")
            return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", s))
        except ValueError:
            return False
    if kind == "Boolean (true/false)":
        return s.lower() in {"true", "false"}
    return True


def validate(frame, schema):
    errors = []
    for col, kind in schema.items():
        if kind in ("Auto / text", "Text"):
            continue
        for i, value in enumerate(frame[col].tolist(), start=2):
            if pd.isna(value) or str(value).strip().lower() in MISSING:
                continue
            if not valid_value(value, kind):
                errors.append({"CSV record": i, "Column": col, "Expected": kind,
                               "Actual": str(value)[:100], "Issue": "Type mismatch"})
    return pd.DataFrame(errors, columns=["CSV record", "Column", "Expected", "Actual", "Issue"])


def clean_frame(frame, trim, normalize_missing, drop_duplicates, numeric_fill, text_fill, schema, invalid_to_missing):
    out = frame.copy()
    if trim:
        for col in out.columns:
            out[col] = out[col].str.strip()
    if normalize_missing:
        for col in out.columns:
            out.loc[missing_mask(out[col]), col] = pd.NA
    if invalid_to_missing:
        for col, kind in schema.items():
            if kind in ("Auto / text", "Text"):
                continue
            invalid = out[col].apply(lambda x: False if pd.isna(x) or str(x).strip().lower() in MISSING else not valid_value(x, kind))
            out.loc[invalid, col] = pd.NA
    if drop_duplicates:
        out = out.drop_duplicates().reset_index(drop=True)
    for col, kind in schema.items():
        if kind in ("Integer", "Decimal"):
            numeric = pd.to_numeric(out[col], errors="coerce")
            if numeric_fill == "Median" and numeric.notna().any():
                numeric = numeric.fillna(numeric.median())
            elif numeric_fill == "Mean" and numeric.notna().any():
                numeric = numeric.fillna(numeric.mean())
            # Median/mean may create decimals even for an integer-designated column.
            out[col] = numeric
        elif kind == "Date (YYYY-MM-DD)":
            out[col] = pd.to_datetime(out[col], format="%Y-%m-%d", errors="coerce").dt.strftime("%Y-%m-%d")
        elif kind == "Boolean (true/false)":
            out[col] = out[col].str.lower().map({"true": True, "false": False}).astype("boolean")
        elif text_fill == "Unknown":
            out[col] = out[col].fillna("Unknown")
    return out

uploaded = st.file_uploader("Upload a real CSV file (UTF-8, comma-separated)", type=["csv"])
if uploaded is None:
    st.info("Upload a CSV file to begin. Your original file is not modified.")
    st.stop()

try:
    df = load_csv(uploaded.getvalue())
except ValueError as exc:
    st.error(f"CSV validation failed: {exc}")
    st.stop()

st.success(f"Loaded {len(df):,} records and {len(df.columns)} columns from {uploaded.name}.")
st.subheader("1. Original data")
st.dataframe(df.head(50), use_container_width=True)

c1, c2, c3 = st.columns(3)
c1.metric("Records", len(df))
c2.metric("Missing / placeholder cells", int(sum(missing_mask(df[c]).sum() for c in df.columns)))
c3.metric("Exact duplicate records", int(df.duplicated().sum()))

profile = pd.DataFrame([{"Column": c, "Non-missing": int((~missing_mask(df[c])).sum()),
                         "Missing": int(missing_mask(df[c]).sum()),
                         "Distinct non-missing": int(df.loc[~missing_mask(df[c]), c].nunique())}
                        for c in df.columns])
st.subheader("2. Data quality profile")
st.dataframe(profile, use_container_width=True, hide_index=True)

st.subheader("3. Confirm expected column types")
st.caption("Choose expected types based on the data dictionary. Auto / text does not enforce a type. Dates must be YYYY-MM-DD.")
schema = {}
for col in df.columns:
    schema[col] = st.selectbox(f"{col}", TYPES, key=f"type_{col}")

st.subheader("4. Type validation errors")
errors = validate(df, schema)
if errors.empty:
    st.success("No type mismatches found for the types you selected.")
else:
    st.error(f"Found {len(errors)} type mismatch(es). Review before cleaning.")
    st.dataframe(errors, use_container_width=True, hide_index=True)
    st.download_button("Download error report", errors.to_csv(index=False).encode("utf-8-sig"), "validation_errors.csv", "text/csv")

st.subheader("5. Approve cleaning operations")
trim = st.checkbox("Trim leading and trailing whitespace", value=True)
normalize_missing = st.checkbox("Convert blank / NA / N/A / NULL / None / NaN to missing", value=True)
drop_duplicates = st.checkbox("Remove exact duplicate records", value=False)
invalid_to_missing = st.checkbox("Convert values violating confirmed types to missing (potential data loss)", value=False)
numeric_fill = st.selectbox("Fill missing values in confirmed numeric columns", ["Leave missing", "Median", "Mean"])
text_fill = st.selectbox("Fill missing values in text columns", ["Leave missing", "Unknown"])

if st.button("Apply approved cleaning", type="primary"):
    if not invalid_to_missing and not errors.empty:
        st.error("Resolve type mismatches or explicitly approve converting invalid values to missing before applying typed conversions.")
    else:
        cleaned = clean_frame(df, trim, normalize_missing, drop_duplicates, numeric_fill, text_fill, schema, invalid_to_missing)
        st.session_state["cleaned_csv"] = cleaned.to_csv(index=False).encode("utf-8-sig")
        st.session_state["cleaned_preview"] = cleaned
        st.session_state["cleaned_source"] = uploaded.getvalue()
        st.session_state["cleaned_settings"] = (tuple(schema.items()), trim, normalize_missing, drop_duplicates, invalid_to_missing, numeric_fill, text_fill)
        st.success("Cleaning complete. Review the result and download below.")

settings = (tuple(schema.items()), trim, normalize_missing, drop_duplicates, invalid_to_missing, numeric_fill, text_fill)
if st.session_state.get("cleaned_source") == uploaded.getvalue() and st.session_state.get("cleaned_settings") == settings:
    cleaned = st.session_state["cleaned_preview"]
    st.subheader("6. Before and after")
    a, b = st.columns(2)
    a.metric("Original records", len(df))
    b.metric("Cleaned records", len(cleaned))
    st.dataframe(cleaned.head(50), use_container_width=True)
    st.download_button("Download cleaned CSV", st.session_state["cleaned_csv"], "cleaned_data.csv", "text/csv")
    st.divider()
    render_dashboard(cleaned, filename=uploaded.name)
else:
    st.info("Apply cleaning to generate a downloadable result. If settings change, apply again.")
