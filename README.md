# InsightFlow AI — CSV Data Cleaning & Analytics

A Python and Streamlit application for uploading, validating, cleaning, and exploring CSV datasets through interactive visualizations.

## Features
- Upload UTF-8, comma-separated CSV files with different column structures.
- Detect malformed CSV records, duplicate headers, missing values, and duplicate rows.
- Confirm expected column types and inspect specific type-validation errors.
- Apply user-selected cleaning: trim whitespace, standardize missing values, remove duplicates, optionally convert invalid values to missing, and fill numeric values with mean or median.
- Compare original and cleaned data, then download the cleaned CSV.
- Explore the cleaned dataset with an interactive Plotly dashboard and generate a printable HTML report.

## Requirements
- Python 3.10 or newer recommended
- Dependencies listed in `requirements.txt`

## Run on Windows
1. Download or clone this repository.
2. Open the project folder in File Explorer, click the address bar, type `cmd`, and press Enter.
3. Install dependencies:
   ```bash
   py -m pip install -r requirements.txt
   ```
4. Start the app:
   ```bash
   py -m streamlit run insightflow.py
   ```
5. Open the local address shown in the terminal (usually http://localhost:8501).

## How to use
1. Upload a **UTF-8, comma-separated `.csv`** file.
2. Review the data preview and data-quality profile.
3. Select the expected type for each column. **Auto / text** does not enforce numeric or date types.
4. Review any validation errors and download the error report if needed.
5. Choose cleaning operations. To fill missing numeric values, first set those columns to **Integer** or **Decimal**.
6. Click **Apply approved cleaning**.
7. Review the cleaned data and use **Download cleaned CSV**.
8. Explore the interactive dashboard and its printable report.

## Project files
- `insightflow.py` — Streamlit app, CSV validation and cleaning workflow.
- `dashboard.py` — Interactive dashboard and reporting functionality.
- `requirements.txt` — Python dependencies.
- `.gitignore` — Excludes local caches, environments, and secrets.

## Notes
The original uploaded CSV is not overwritten. Review cleaning decisions before using results for analysis. The printable HTML report does not embed interactive Plotly charts.

## Author
Ania Ahmed — [GitHub](https://github.com/Ania-works)
