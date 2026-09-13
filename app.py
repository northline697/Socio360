"""
Socio360 - AI-Assisted Society Management
Single codebase:
- Google Colab development: `python app.py` -> Gradio UI
- Streamlit deployment: `streamlit run app.py` -> Streamlit UI

This MVP uses SQLite for local data storage and a built-in AI-style assistant
(no API key is required). An external LLM can be added later.
"""

import os
import sys
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
import gradio as gr

APP_NAME = "Socio360"
DB_PATH = Path("socio360.db")


# -----------------------------
# Database
# -----------------------------
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS residents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            house TEXT,
            status TEXT DEFAULT 'Active',
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resident TEXT,
            category TEXT,
            description TEXT,
            priority TEXT,
            status TEXT DEFAULT 'Open',
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            message TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            event_date TEXT,
            location TEXT,
            description TEXT,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()


def query_df(sql, params=()):
    conn = db()
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def execute(sql, params=()):
    conn = db()
    cur = conn.cursor()
    cur.execute(sql, params)
    conn.commit()
    last_id = cur.lastrowid
    conn.close()
    return last_id


def seed_demo_data():
    if not query_df("SELECT id FROM residents LIMIT 1").empty:
        return

    now = datetime.now().isoformat(timespec="seconds")

    execute(
        "INSERT INTO residents (name, phone, email, house, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("Ali Khan", "0300-1111111", "ali@example.com", "A-101", "Active", now),
    )
    execute(
        "INSERT INTO residents (name, phone, email, house, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("Sara Ahmed", "0300-2222222", "sara@example.com", "B-202", "Active", now),
    )
    execute(
        "INSERT INTO complaints (resident, category, description, priority, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("Ali Khan", "Maintenance", "Street light is not working near Block A.", "High", "Open", now),
    )
    execute(
        "INSERT INTO announcements (title, message, created_at) VALUES (?, ?, ?)",
        ("Welcome to Socio360", "Society management portal is now available.", now),
    )
    execute(
        "INSERT INTO events (title, event_date, location, description, created_at) VALUES (?, ?, ?, ?, ?)",
        ("Community Meeting", "2026-10-01", "Community Hall", "Monthly society meeting.", now),
    )


# -----------------------------
# AI assistant
# -----------------------------
def ai_assistant(question: str) -> str:
    q = (question or "").strip().lower()
    residents = int(query_df("SELECT COUNT(*) AS n FROM residents").iloc[0]["n"])
    open_complaints = int(query_df(
        "SELECT COUNT(*) AS n FROM complaints WHERE status != 'Closed'"
    ).iloc[0]["n"])
    events = int(query_df("SELECT COUNT(*) AS n FROM events").iloc[0]["n"])

    if not q:
        return "Ask me about residents, complaints, events, announcements, or society operations."

    if any(word in q for word in ["complaint", "complaints", "issue", "issues"]):
        data = query_df("""
            SELECT category, priority, status, description
            FROM complaints
            WHERE status != 'Closed'
            ORDER BY CASE priority WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END
        """)
        if data.empty:
            return "There are currently no open complaints."
        lines = [f"Open complaints: {len(data)}"]
        for _, row in data.head(5).iterrows():
            lines.append(
                f"- {row['priority']} priority / {row['category']} / {row['status']}: {row['description']}"
            )
        return "\n".join(lines)

    if any(word in q for word in ["resident", "residents", "member", "members"]):
        return (
            f"Socio360 currently has {residents} registered residents. "
            "Use the Residents section to add or manage resident records."
        )

    if any(word in q for word in ["event", "events", "meeting"]):
        return f"There are {events} events recorded. Check the Events section for dates and locations."

    if any(word in q for word in ["announcement", "news", "notice"]):
        latest = query_df(
            "SELECT title, message FROM announcements ORDER BY id DESC LIMIT 3"
        )
        if latest.empty:
            return "There are no announcements yet."
        return "\n".join(
            [f"- {r['title']}: {r['message']}" for _, r in latest.iterrows()]
        )

    if any(word in q for word in ["summary", "dashboard", "status", "report"]):
        return (
            f"Society summary: {residents} residents, {open_complaints} open complaints, "
            f"and {events} events. Prioritize high-priority complaints and keep residents "
            "updated through announcements."
        )

    return (
        "I can help with residents, complaints, events, announcements, and basic society "
        "management recommendations. Try: 'Give me a society summary' or 'Show open complaints'."
    )


# -----------------------------
# Shared data actions
# -----------------------------
def add_resident(name, phone, email, house):
    if not name.strip():
        return "Please enter the resident name."
    execute(
        "INSERT INTO residents (name, phone, email, house, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (name.strip(), phone.strip(), email.strip(), house.strip(), "Active",
         datetime.now().isoformat(timespec="seconds")),
    )
    return f"Resident '{name.strip()}' added successfully."


def add_complaint(resident, category, description, priority):
    if not description.strip():
        return "Please enter a complaint description."
    execute(
        "INSERT INTO complaints (resident, category, description, priority, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (resident.strip(), category, description.strip(), priority, "Open",
         datetime.now().isoformat(timespec="seconds")),
    )
    return "Complaint submitted successfully."


def add_announcement(title, message):
    if not title.strip() or not message.strip():
        return "Please enter both a title and message."
    execute(
        "INSERT INTO announcements (title, message, created_at) VALUES (?, ?, ?)",
        (title.strip(), message.strip(), datetime.now().isoformat(timespec="seconds")),
    )
    return "Announcement published successfully."


def add_event(title, event_date, location, description):
    if not title.strip() or not event_date.strip():
        return "Please enter an event title and date."
    execute(
        "INSERT INTO events (title, event_date, location, description, created_at) VALUES (?, ?, ?, ?, ?)",
        (title.strip(), event_date.strip(), location.strip(), description.strip(),
         datetime.now().isoformat(timespec="seconds")),
    )
    return "Event added successfully."


# -----------------------------
# Gradio UI for Colab development
# -----------------------------
def build_gradio():
    with gr.Blocks(title=APP_NAME, theme=gr.themes.Soft()) as demo:
        gr.Markdown(
            "# 🏘️ Socio360\n"
            "### AI-Assisted Society Management\n"
            "Manage residents, complaints, announcements and community events."
        )

        with gr.Tab("Dashboard"):
            refresh = gr.Button("Refresh Dashboard")
            dashboard = gr.Dataframe(
                headers=["Metric", "Value"],
                datatype=["str", "number"],
                value=[
                    ["Residents", len(query_df("SELECT id FROM residents"))],
                    ["Open Complaints", len(query_df("SELECT id FROM complaints WHERE status != 'Closed'"))],
                    ["Events", len(query_df("SELECT id FROM events"))],
                ],
                interactive=False,
            )
            refresh.click(
                lambda: [
                    ["Residents", len(query_df("SELECT id FROM residents"))],
                    ["Open Complaints", len(query_df("SELECT id FROM complaints WHERE status != 'Closed'"))],
                    ["Events", len(query_df("SELECT id FROM events"))],
                ],
                outputs=dashboard,
            )

        with gr.Tab("Residents"):
            with gr.Row():
                with gr.Column():
                    n = gr.Textbox(label="Name")
                    p = gr.Textbox(label="Phone")
                    e = gr.Textbox(label="Email")
                    h = gr.Textbox(label="House / Unit")
                    add = gr.Button("Add Resident")
                    msg = gr.Textbox(label="Status")
                    add.click(add_resident, [n, p, e, h], msg)
                table = gr.Dataframe(
                    value=query_df("SELECT id, name, phone, email, house, status FROM residents"),
                    interactive=False,
                )
            gr.Button("Refresh").click(
                lambda: query_df("SELECT id, name, phone, email, house, status FROM residents"),
                outputs=table,
            )

        with gr.Tab("Complaints"):
            with gr.Row():
                with gr.Column():
                    cr = gr.Textbox(label="Resident")
                    cc = gr.Dropdown(["Maintenance", "Security", "Cleanliness", "Utilities", "Other"],
                                     value="Maintenance", label="Category")
                    cd = gr.Textbox(label="Description", lines=4)
                    cp = gr.Dropdown(["Low", "Medium", "High"], value="Medium", label="Priority")
                    cb = gr.Button("Submit Complaint")
                    cm = gr.Textbox(label="Status")
                    cb.click(add_complaint, [cr, cc, cd, cp], cm)
                ct = gr.Dataframe(
                    value=query_df(
                        "SELECT id, resident, category, priority, status, description FROM complaints"
                    ),
                    interactive=False,
                )
            gr.Button("Refresh").click(
                lambda: query_df(
                    "SELECT id, resident, category, priority, status, description FROM complaints"
                ),
                outputs=ct,
            )

        with gr.Tab("Announcements"):
            at = gr.Textbox(label="Title")
            am = gr.Textbox(label="Message", lines=4)
            ab = gr.Button("Publish Announcement")
            ast = gr.Textbox(label="Status")
            ab.click(add_announcement, [at, am], ast)

        with gr.Tab("Events"):
            et = gr.Textbox(label="Event Title")
            ed = gr.Textbox(label="Date (YYYY-MM-DD)")
            el = gr.Textbox(label="Location")
            ex = gr.Textbox(label="Description", lines=3)
            eb = gr.Button("Add Event")
            esm = gr.Textbox(label="Status")
            eb.click(add_event, [et, ed, el, ex], esm)

        with gr.Tab("AI Assistant"):
            gr.Markdown("Ask the built-in assistant about society operations.")
            aq = gr.Textbox(label="Your question", placeholder="Give me a society summary")
            ar = gr.Textbox(label="AI Assistant", lines=8)
            gr.Button("Ask Socio360 AI").click(ai_assistant, aq, ar)

    return demo


# -----------------------------
# Streamlit UI for deployment
# -----------------------------
def streamlit_app():
    st.set_page_config(page_title=APP_NAME, page_icon="🏘️", layout="wide")
    st.title("🏘️ Socio360")
    st.caption("AI-Assisted Society Management")

    with st.sidebar:
        st.header("Navigation")
        page = st.radio(
            "Go to",
            ["Dashboard", "Residents", "Complaints", "Announcements", "Events", "AI Assistant"],
        )
        st.divider()
        st.caption("Socio360 MVP • SQLite storage")

    if page == "Dashboard":
        st.subheader("Society Dashboard")
        c1, c2, c3 = st.columns(3)
        c1.metric("Residents", len(query_df("SELECT id FROM residents")))
        c2.metric("Open Complaints", len(query_df("SELECT id FROM complaints WHERE status != 'Closed'")))
        c3.metric("Events", len(query_df("SELECT id FROM events")))

        st.subheader("Recent complaints")
        st.dataframe(
            query_df(
                "SELECT resident, category, priority, status, description "
                "FROM complaints ORDER BY id DESC LIMIT 10"
            ),
            use_container_width=True,
            hide_index=True,
        )

    elif page == "Residents":
        st.subheader("Resident Management")
        with st.form("resident_form"):
            name = st.text_input("Name")
            phone = st.text_input("Phone")
            email = st.text_input("Email")
            house = st.text_input("House / Unit")
            submitted = st.form_submit_button("Add Resident")
            if submitted:
                st.success(add_resident(name, phone, email, house))
                st.rerun()
        st.dataframe(
            query_df("SELECT id, name, phone, email, house, status FROM residents ORDER BY id DESC"),
            use_container_width=True,
            hide_index=True,
        )

    elif page == "Complaints":
        st.subheader("Complaint Management")
        with st.form("complaint_form"):
            resident = st.text_input("Resident")
            category = st.selectbox(
                "Category", ["Maintenance", "Security", "Cleanliness", "Utilities", "Other"]
            )
            description = st.text_area("Description")
            priority = st.selectbox("Priority", ["Low", "Medium", "High"], index=1)
            submitted = st.form_submit_button("Submit Complaint")
            if submitted:
                st.success(add_complaint(resident, category, description, priority))
                st.rerun()
        st.dataframe(
            query_df(
                "SELECT id, resident, category, priority, status, description, created_at "
                "FROM complaints ORDER BY id DESC"
            ),
            use_container_width=True,
            hide_index=True,
        )

    elif page == "Announcements":
        st.subheader("Announcements & Society News")
        with st.form("announcement_form"):
            title = st.text_input("Title")
            message = st.text_area("Message")
            submitted = st.form_submit_button("Publish")
            if submitted:
                st.success(add_announcement(title, message))
                st.rerun()
        st.dataframe(
            query_df("SELECT id, title, message, created_at FROM announcements ORDER BY id DESC"),
            use_container_width=True,
            hide_index=True,
        )

    elif page == "Events":
        st.subheader("Community Events")
        with st.form("event_form"):
            title = st.text_input("Event Title")
            event_date = st.date_input("Event Date")
            location = st.text_input("Location")
            description = st.text_area("Description")
            submitted = st.form_submit_button("Add Event")
            if submitted:
                st.success(add_event(title, str(event_date), location, description))
                st.rerun()
        st.dataframe(
            query_df(
                "SELECT id, title, event_date, location, description, created_at "
                "FROM events ORDER BY event_date"
            ),
            use_container_width=True,
            hide_index=True,
        )

    elif page == "AI Assistant":
        st.subheader("🤖 Socio360 AI Assistant")
        st.info(
            "This MVP uses a built-in assistant, so it works without an API key. "
            "It can be upgraded later with a hosted LLM."
        )
        question = st.text_area(
            "Ask a question",
            placeholder="Give me a society summary",
        )
        if st.button("Ask Socio360 AI", type="primary"):
            st.write(ai_assistant(question))


# -----------------------------
# Entry point
# -----------------------------
init_db()
seed_demo_data()

# Streamlit executes the file through its own runtime.
# Normal `python app.py` launches Gradio for Colab development.
if "streamlit" in " ".join(sys.argv).lower() or os.getenv("STREAMLIT_RUNTIME"):
    streamlit_app()
else:
    build_gradio().launch(share=True)
