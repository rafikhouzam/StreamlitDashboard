# utils/db.py
from sqlalchemy import create_engine
import streamlit as st
import pandas as pd
from sqlalchemy.sql import text

def get_sql_engine():
    server = st.secrets["SQL_SERVER"]
    db = st.secrets["SQL_DB"]

    use_windows_auth = st.secrets.get("SQL_WINDOWS_AUTH", True)

    if use_windows_auth:
        conn_str = (
            f"mssql+pyodbc://@{server}/{db}"
            "?driver=ODBC+Driver+18+for+SQL+Server"
            "&Trusted_Connection=yes"
            "&TrustServerCertificate=yes"
        )
    else:
        user = st.secrets["SQL_USER"]
        pwd = st.secrets["SQL_PASSWORD"]
        conn_str = (
            f"mssql+pyodbc://{user}:{pwd}@{server}/{db}"
            "?driver=ODBC+Driver+18+for+SQL+Server"
            "&TrustServerCertificate=yes"
        )

    return create_engine(conn_str, pool_pre_ping=True)

@st.cache_data(ttl=600)
def read_sql(query: str, params: dict | None = None) -> pd.DataFrame:
    engine = get_sql_engine()
    with engine.connect() as conn:
        return pd.read_sql(text(query), conn, params=params or {})
