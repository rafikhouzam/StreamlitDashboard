# streamlit_auth.py

import streamlit as st
from jose import jwt, JWTError
import requests

API_BASE = "https://api.anerijewels.com"
SECRET_KEY = st.secrets["JWT_SECRET"]
ALGORITHM = "HS256"

def login_form():
    with st.form("login_form"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            res = requests.post(f"{API_BASE}/token",
                                data={"username": u, "password": p})
            if res.ok:
                token = res.json()["access_token"]
                st.session_state["token"] = token
                payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                st.session_state["user"] = payload["sub"]
                st.session_state["role"] = payload["role"]
                st.rerun()
            else:
                st.error("Invalid credentials")

def require_login():
    if "token" not in st.session_state:
        st.warning("Please log in to access this page.")
        login_form()
        st.stop()
    # Optional: auto-logout on expired token
    try:
        jwt.decode(st.session_state["token"], SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        st.session_state.clear()
        st.error("Session expired. Please log in again.")
        st.stop()

def logout():
    for key in ("token", "user", "role"):
        st.session_state.pop(key, None)
