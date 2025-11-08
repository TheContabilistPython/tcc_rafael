from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np
from datetime import datetime

app = FastAPI(title="Dashboard Biblioteca UFFS - API")

# Allow requests from frontend (served on a different port)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CSV_PATH = "basededados_biblio_2025.csv"


def load_data():
    # Read semicolon separated CSV and parse dates
    df = pd.read_csv(CSV_PATH, sep=';', dtype=str)

    # normalize column names
    df.columns = [c.strip() for c in df.columns]

    # Parse relevant date columns
    for col in ['Data de empréstimo', 'Data devolução prevista', 'Data devolução efetiva']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')

    # Convert numeric columns
    if 'Idade' in df.columns:
        df['Idade'] = pd.to_numeric(df['Idade'], errors='coerce')

    return df


df = load_data()


@app.get('/api/time_series')
def time_series():
    # Monthly series counts for Livros and Notebook
    col = 'Nome tipo obra'
    date_col = 'Data de empréstimo'
    if col not in df.columns or date_col not in df.columns:
        return {"error": "colunas faltando"}

    tmp = df[[date_col, col]].dropna()
    tmp = tmp[tmp[col].isin(['Livros', 'Notebook'])]
    tmp['month'] = tmp[date_col].dt.to_period('M').dt.to_timestamp()
    grouped = tmp.groupby(['month', col]).size().unstack(fill_value=0)

    months = [d.strftime('%Y-%m') for d in grouped.index]
    livros = grouped.get('Livros', pd.Series(dtype=int)).tolist()
    notebook = grouped.get('Notebook', pd.Series(dtype=int)).tolist()

    return {"months": months, "livros": livros, "notebook": notebook}


@app.get('/api/heatmap')
def heatmap():
    # Heatmap of loans: weekday vs hour
    date_col = 'Data de empréstimo'
    if date_col not in df.columns:
        return {"error": "coluna de data faltando"}

    tmp = df[[date_col]].dropna()
    # map English day names to Portuguese full names
    day_map = {
        'Monday': 'Segunda',
        'Tuesday': 'Terça',
        'Wednesday': 'Quarta',
        'Thursday': 'Quinta',
        'Friday': 'Sexta',
        'Saturday': 'Sábado',
        'Sunday': 'Domingo'
    }
    tmp['weekday_en'] = tmp[date_col].dt.day_name()
    tmp['weekday'] = tmp['weekday_en'].map(day_map).fillna(tmp['weekday_en'])
    tmp['hour'] = tmp[date_col].dt.hour

    # hours range: remove 6 and 23 per request -> keep 7..22
    hours = list(range(7, 23))
    # only weekdays (Segunda..Sexta), remove sábado e domingo
    weekdays = ['Segunda','Terça','Quarta','Quinta','Sexta']

    pivot = tmp.groupby(['weekday', 'hour']).size().unstack(fill_value=0)

    # reindex rows and columns to ensure full grid
    pivot = pivot.reindex(index=weekdays, fill_value=0)
    pivot = pivot.reindex(columns=hours, fill_value=0)

    # convert to plain python lists for JSON
    values = pivot.values.tolist()
    return {"weekdays": weekdays, "hours": hours, "values": values}


@app.get('/api/metrics')
def metrics():
    # Average loan time (days)
    loan_col = 'Data de empréstimo'
    dev_eff = 'Data devolução efetiva'
    dev_prev = 'Data devolução prevista'

    res = {}
    # Basic summaries
    res['total_records'] = int(len(df))
    if 'Nome da pessoa' in df.columns:
        res['unique_borrowers'] = int(df['Nome da pessoa'].nunique())
    else:
        res['unique_borrowers'] = 0

    # Currently borrowed: entries without actual return date
    if dev_eff in df.columns:
        currently = df[df[dev_eff].isna()]
        res['currently_loaned'] = int(len(currently))
    else:
        res['currently_loaned'] = 0
    if loan_col in df.columns and dev_eff in df.columns:
        tmp = df[[loan_col, dev_eff]].dropna()
        tmp['loan_days'] = (tmp[dev_eff] - tmp[loan_col]).dt.total_seconds() / 86400.0
        res['average_loan_days'] = float(round(tmp['loan_days'].mean(), 2)) if not tmp.empty else None
    else:
        res['average_loan_days'] = None

    # Most borrowed books
    if 'Título' in df.columns:
        # remove unwanted titles from the top list (case-insensitive)
        banned = [
            'computador notebook positivo master',
            'notebook positivo master',
            'calculadora cientifica',
            'calculadora'
        ]
        t = df['Título'].fillna('').astype(str)
        mask = t.str.lower().apply(lambda s: not any(b in s for b in banned))
        top_books = t[mask].value_counts().head(10).reset_index()
        top_books.columns = ['title', 'count']
        res['top_books'] = top_books.to_dict(orient='records')
    else:
        res['top_books'] = []

    # Top borrowers
    if 'Nome da pessoa' in df.columns:
        top_people = df['Nome da pessoa'].value_counts().head(10).reset_index()
        top_people.columns = ['person', 'count']
        res['top_people'] = top_people.to_dict(orient='records')
        # also expose the top person as a single item
        top_all = df['Nome da pessoa'].value_counts().head(1)
        if not top_all.empty:
            name = top_all.index[0]
            cnt = int(top_all.iloc[0])
            res['top_person'] = { 'person': name, 'count': cnt }
        else:
            res['top_person'] = { 'person': None, 'count': 0 }
    else:
        res['top_people'] = []
        res['top_person'] = { 'person': None, 'count': 0 }

    # Delay metrics by Gênero and age groups
    if dev_prev in df.columns and dev_eff in df.columns:
        delays = df[[dev_prev, dev_eff, 'Gênero', 'Idade']].dropna(subset=[dev_prev, dev_eff])
        delays['delay_days'] = (delays[dev_eff] - delays[dev_prev]).dt.total_seconds() / 86400.0
        delays['is_delayed'] = delays['delay_days'] > 0

        # By genre
        by_genre = delays.groupby('Gênero').agg(
            total=('is_delayed','size'),
            delayed=('is_delayed','sum'),
            avg_delay=('delay_days','mean')
        ).reset_index()
        by_genre['pct_delayed'] = (by_genre['delayed'] / by_genre['total']).fillna(0).round(3)
        res['delay_by_genre'] = by_genre[['Gênero','total','delayed','pct_delayed','avg_delay']].to_dict(orient='records')

        # Age groups
        def age_bucket(a):
            try:
                a = float(a)
            except Exception:
                return 'Unknown'
            if np.isnan(a):
                return 'Unknown'
            if a < 20:
                return '<20'
            if a < 30:
                return '20-29'
            if a < 40:
                return '30-39'
            if a < 50:
                return '40-49'
            return '50+'

        delays['age_group'] = delays['Idade'].apply(age_bucket)
        by_age = delays.groupby('age_group').agg(
            total=('is_delayed','size'),
            delayed=('is_delayed','sum'),
            avg_delay=('delay_days','mean')
        ).reset_index()
        by_age['pct_delayed'] = (by_age['delayed'] / by_age['total']).fillna(0).round(3)
        res['delay_by_age'] = by_age[['age_group','total','delayed','pct_delayed','avg_delay']].to_dict(orient='records')
    else:
        res['delay_by_genre'] = []
        res['delay_by_age'] = []

    return res
