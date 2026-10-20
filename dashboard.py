"""Reusable interactive analytics dashboard for InsightFlow AI.
Call render_dashboard(df) from your existing Streamlit application.
"""
import io
import html
import pandas as pd
import plotly.express as px
import streamlit as st
from pandas.api.types import is_numeric_dtype, is_datetime64_any_dtype


def _prepared(df):
    out = df.copy()
    for col in out.columns:
        if is_datetime64_any_dtype(out[col]):
            continue
        if out[col].dtype == 'object' or str(out[col].dtype) == 'string':
            name = str(col).lower()
            if any(term in name for term in ('date', 'timestamp', 'datetime')):
                parsed = pd.to_datetime(out[col], errors='coerce')
                if parsed.notna().sum() >= max(1, int(out[col].notna().sum() * 0.8)):
                    out[col] = parsed
    return out


def _filters(df, prefix):
    result = df.copy()
    with st.expander('Interactive filters', expanded=True):
        categorical = [c for c in df.columns if not is_numeric_dtype(df[c]) and not is_datetime64_any_dtype(df[c]) and 1 < df[c].nunique(dropna=True) <= 40]
        numeric = [c for c in df.columns if is_numeric_dtype(df[c]) and df[c].notna().any()]
        selected_cat = st.multiselect('Categorical filters', categorical, key=f'{prefix}_cat_cols')
        for col in selected_cat:
            values = sorted(df[col].dropna().astype(str).unique().tolist())
            chosen = st.multiselect(f'{col}: allowed values', values, default=values, key=f'{prefix}_cat_{col}')
            result = result[result[col].astype(str).isin(chosen)]
        selected_num = st.selectbox('Numeric range filter', ['None'] + numeric, key=f'{prefix}_num_col')
        if selected_num != 'None':
            series = pd.to_numeric(df[selected_num], errors='coerce').dropna()
            lo, hi = float(series.min()), float(series.max())
            if lo < hi:
                bounds = st.slider(f'{selected_num}: range', min_value=lo, max_value=hi, value=(lo, hi), key=f'{prefix}_num_range')
                result = result[result[selected_num].between(*bounds)]
            else:
                st.info(f'{selected_num} has only one observed numeric value: {lo:g}.')
    return result


def _chart(df, prefix):
    st.subheader('Chart builder')
    numeric = [c for c in df.columns if is_numeric_dtype(df[c])]
    columns = list(df.columns)
    kind = st.selectbox('Chart type', ['Bar', 'Histogram', 'Line', 'Scatter', 'Box', 'Pie'], key=f'{prefix}_chart_kind')
    if df.empty or not columns:
        st.warning('No records are available after filtering.')
        return
    if kind in ('Histogram', 'Box') and not numeric:
        st.warning('This chart requires a numeric column. Choose another chart or upload numeric data.')
        return
    if kind == 'Scatter' and len(numeric) < 2:
        st.warning('A scatter plot requires at least two numeric columns.')
        return
    try:
        if kind == 'Histogram':
            x = st.selectbox('Numeric column', numeric, key=f'{prefix}_hist_x')
            fig = px.histogram(df, x=x, title=f'Distribution of {x}')
        elif kind == 'Box':
            y = st.selectbox('Numeric column', numeric, key=f'{prefix}_box_y')
            cats = [c for c in columns if c != y and df[c].nunique(dropna=True) <= 30]
            x = st.selectbox('Group by (optional)', ['None'] + cats, key=f'{prefix}_box_x')
            fig = px.box(df, x=None if x == 'None' else x, y=y, title=f'{y} distribution')
        elif kind == 'Scatter':
            x = st.selectbox('X axis', numeric, key=f'{prefix}_scatter_x')
            y = st.selectbox('Y axis', [c for c in numeric if c != x], key=f'{prefix}_scatter_y')
            fig = px.scatter(df, x=x, y=y, title=f'{y} vs {x}')
        elif kind == 'Line':
            x = st.selectbox('X axis', columns, key=f'{prefix}_line_x')
            if not numeric:
                st.warning('Line charts require a numeric Y axis.')
                return
            y = st.selectbox('Numeric Y axis', numeric, key=f'{prefix}_line_y')
            method = st.selectbox('Aggregate duplicate X values', ['Mean', 'Sum', 'Count'], key=f'{prefix}_line_method')
            group = df.groupby(x, dropna=False, as_index=False)[y]
            plotted = group.mean() if method == 'Mean' else group.sum() if method == 'Sum' else group.count()
            plotted = plotted.sort_values(x)
            fig = px.line(plotted, x=x, y=y, markers=True, title=f'{method} of {y} by {x}')
        else:
            x = st.selectbox('Category column', columns, key=f'{prefix}_{kind}_x')
            method = st.selectbox('Metric', ['Record count', 'Sum', 'Mean'], key=f'{prefix}_{kind}_metric')
            if method == 'Record count':
                plotted = df.groupby(x, dropna=False).size().reset_index(name='Value')
            else:
                if not numeric:
                    st.warning('Sum and mean require numeric columns.')
                    return
                y = st.selectbox('Numeric metric column', numeric, key=f'{prefix}_{kind}_y')
                plotted = df.groupby(x, dropna=False)[y].agg('sum' if method == 'Sum' else 'mean').reset_index(name='Value')
            plotted[x] = plotted[x].astype(str)
            plotted = plotted.sort_values('Value', ascending=False).head(25)
            if kind == 'Bar':
                fig = px.bar(plotted, x=x, y='Value', title=f'{method} by {x} (top 25)')
            else:
                fig = px.pie(plotted, names=x, values='Value', title=f'{method} by {x} (top 25)')
        st.plotly_chart(fig, use_container_width=True)
    except (ValueError, TypeError, KeyError) as exc:
        st.error(f'Chart cannot be generated with these columns: {exc}')


def _report_html(df, filename):
    rows, cols = df.shape
    missing = int(df.isna().sum().sum())
    summary = df.describe(include='all').transpose().fillna('').astype(str).to_html(border=0, escape=True)
    quality = df.isna().sum().reset_index()
    quality.columns = ['Column', 'Missing values']
    quality_html = quality.to_html(index=False, border=0, escape=True)
    return f'''<!doctype html><html><head><meta charset="utf-8"><title>InsightFlow AI Report</title>
<style>body{{font-family:Arial,sans-serif;max-width:1100px;margin:40px auto;color:#182638}}h1{{color:#15365a}}table{{border-collapse:collapse;width:100%;font-size:12px}}td,th{{padding:8px;border-bottom:1px solid #ddd;text-align:left}}.stats{{display:flex;gap:25px}}.stats div{{padding:14px;background:#f0f3f8}}@media print{{button{{display:none}}body{{margin:10mm}}}}</style></head>
<body><button onclick="window.print()">Print / Save as PDF</button><h1>InsightFlow AI — Analytics Report</h1>
<p>Dataset: {html.escape(filename)}</p><div class="stats"><div>Rows: {rows}</div><div>Columns: {cols}</div><div>Missing cells: {missing}</div></div>
<h2>Missing values by column</h2>{quality_html}<h2>Descriptive statistics</h2>{summary}
<p>Report describes the current filtered dataset. It does not include interactive Plotly charts.</p></body></html>'''


def render_dashboard(df, filename='Uploaded CSV', prefix='phase3'):
    """Render dashboard for any pandas DataFrame; does not mutate original."""
    if not isinstance(df, pd.DataFrame):
        st.error('Dashboard requires a pandas DataFrame.')
        return
    if df.columns.duplicated().any():
        st.error('Dashboard cannot run with duplicate column names. Resolve them in Phase 2 first.')
        return
    df = _prepared(df)
    st.header('Phase 3 · Interactive Analytics Dashboard')
    st.caption(f'Dataset: {filename} | Use your original or approved cleaned data')
    filtered = _filters(df, prefix)
    tab1, tab2, tab3 = st.tabs(['Dashboard', 'Data explorer', 'Printable report'])
    with tab1:
        a, b, c, d = st.columns(4)
        a.metric('Records', f'{len(filtered):,}')
        b.metric('Columns', len(filtered.columns))
        c.metric('Missing cells', f'{int(filtered.isna().sum().sum()):,}')
        d.metric('Duplicate rows', f'{int(filtered.duplicated().sum()):,}')
        if not filtered.empty:
            st.subheader('Automatic data insights')
            numeric = filtered.select_dtypes(include='number')
            if len(numeric.columns):
                col = numeric.columns[0]
                st.write(f'**{col}:** mean {numeric[col].mean():,.2f}; median {numeric[col].median():,.2f}.')
            missing = filtered.isna().sum().sort_values(ascending=False)
            if len(missing) and missing.iloc[0] > 0:
                st.write(f'**Most missing values:** {missing.index[0]} ({int(missing.iloc[0])} cells).')
            else:
                st.write('No missing cells in the filtered dataset.')
        _chart(filtered, prefix)
    with tab2:
        st.subheader('Filtered data')
        st.dataframe(filtered, use_container_width=True)
        st.download_button('Download filtered CSV', filtered.to_csv(index=False).encode('utf-8-sig'), file_name='insightflow_filtered.csv', mime='text/csv', key=f'{prefix}_csv')
        st.subheader('Column quality')
        st.dataframe(pd.DataFrame({'Column': filtered.columns, 'Data type': [str(t) for t in filtered.dtypes], 'Missing': filtered.isna().sum().values, 'Unique': filtered.nunique(dropna=True).values}), use_container_width=True, hide_index=True)
    with tab3:
        st.subheader('Printable analytics report')
        st.write('Download the report, open it in Chrome, and press Ctrl+P to print or save as PDF.')
        report = _report_html(filtered, filename)
        st.download_button('Download printable HTML report', report.encode('utf-8'), file_name='insightflow_report.html', mime='text/html', key=f'{prefix}_report')
        st.info('The report includes KPIs, data quality and descriptive statistics. Interactive charts are not embedded in the printable report.')
