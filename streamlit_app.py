"""
Streamlit demo app: attrition impact on payroll cost for FP&A professionals.
The goal is to be simple, readable, and ready for a LinkedIn walkthrough.
"""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

# Set up the page early so the title/description render immediately.
st.set_page_config(
    page_title="Attrition Impact Simulator",
    page_icon="📉",
    layout="wide",
)


@st.cache_data(show_spinner=False)
def simulate_attrition(
    starting_headcount: int,
    average_salary: float,
    monthly_attrition_rate: float,
    months: int = 12,
) -> pd.DataFrame:
    """Build a simple monthly projection with attrition.

    Assumptions for clarity:
    * Average salary is annual (base comp); payroll per month divides it by 12.
    * Attrition applies to the opening headcount of each month.
    * We keep the math float-friendly so trends are smooth for charts.
    """

    months_index = pd.date_range("2024-01-01", periods=months, freq="MS")
    headcount = []
    payroll = []
    attrition_losses = []

    current_headcount = float(starting_headcount)
    monthly_salary = average_salary / 12.0

    for _ in months_index:
        attrition_loss = current_headcount * monthly_attrition_rate
        ending_headcount = max(current_headcount - attrition_loss, 0.0)

        headcount.append(ending_headcount)
        payroll.append(ending_headcount * monthly_salary)
        attrition_losses.append(attrition_loss)

        current_headcount = ending_headcount

    return pd.DataFrame(
        {
            "Month": months_index,
            "Attrition Loss": attrition_losses,
            "Headcount": headcount,
            "Payroll Cost": payroll,
        }
    )


# --- UI ---
st.title("📉 Attrition Impact on Payroll Cost")
st.caption(
    "A lightweight FP&A-friendly demo that projects how monthly attrition shapes"
    " headcount and payroll. Adjust the sliders to tell the story in real time."
)

# Sidebar controls keep the main view focused on outcomes.
st.sidebar.header("Scenario inputs")
starting_headcount = st.sidebar.number_input(
    "Starting headcount",
    min_value=1,
    max_value=5_000,
    value=75,
    step=5,
)

average_salary = st.sidebar.number_input(
    "Average annual salary (USD)",
    min_value=30_000.0,
    max_value=500_000.0,
    value=110_000.0,
    step=5_000.0,
    format="%0.0f",
)

monthly_attrition = st.sidebar.slider(
    "Monthly attrition rate",
    min_value=0.0,
    max_value=0.2,
    value=0.04,
    step=0.01,
    help="Percentage of employees expected to depart each month.",
)

projection_months = st.sidebar.slider("Projection length (months)", 6, 24, 12)

# Calculate the mock scenario data.
data = simulate_attrition(
    starting_headcount=starting_headcount,
    average_salary=average_salary,
    monthly_attrition_rate=monthly_attrition,
    months=projection_months,
)

# Friendly KPIs: these are useful for narration in a demo.
col1, col2, col3 = st.columns(3)
col1.metric(
    "Opening headcount", f"{starting_headcount:,.0f}", "Baseline for the trend"
)
col2.metric(
    "Ending headcount",
    f"{data['Headcount'].iloc[-1]:,.0f}",
    f"{-(data['Attrition Loss'].sum()):,.0f} change",
)
col3.metric(
    "Annualized payroll impact",
    f"${(data['Payroll Cost'].sum()):,.0f}",
    "Sum of monthly payroll across the horizon",
)

st.divider()

# --- Charts ---
chart_container = st.container()

with chart_container:
    # Headcount trend visual
    headcount_chart = (
        alt.Chart(data)
        .mark_line(point=True)
        .encode(
            x=alt.X("Month", title="Month"),
            y=alt.Y("Headcount", title="Attrition-adjusted headcount"),
            tooltip=["Month:T", alt.Tooltip("Headcount", format=",.1f")],
        )
        .properties(title="Headcount trajectory with attrition")
    )

    payroll_chart = (
        alt.Chart(data)
        .mark_area(opacity=0.6)
        .encode(
            x=alt.X("Month", title="Month"),
            y=alt.Y("Payroll Cost", title="Monthly payroll cost", stack=None),
            tooltip=["Month:T", alt.Tooltip("Payroll Cost", format="$,.0f")],
        )
        .properties(title="Payroll trend (attrition-adjusted)")
    )

    charts = alt.vconcat(headcount_chart, payroll_chart).resolve_scale(x="shared")
    st.altair_chart(charts, use_container_width=True)

# Show the underlying mock data so people can screenshot or export.
st.subheader("Projection table (for screenshots or CSV downloads)")
st.dataframe(
    data.assign(
        Month=lambda df: df["Month"].dt.strftime("%b %Y"),
        **{"Monthly Attrition %": lambda df: monthly_attrition * 100},
    )["Month Attrition Loss Headcount Payroll Cost Monthly Attrition %".split()],
    use_container_width=True,
)

st.info(
    "How to explain this demo: start with the inputs on the left, narrate the"
    " headcount trajectory, then show how payroll follows the same curve."
    " Because the numbers are mock, you can focus on the storyline rather than"
    " the accuracy of any particular forecast."
)
