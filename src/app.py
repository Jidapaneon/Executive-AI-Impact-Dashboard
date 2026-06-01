from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "ai_initiatives.csv"


@st.cache_data
def load_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH)
    df["total_benefit"] = df["cost_savings"] + df["revenue_uplift"]
    df["net_benefit"] = df["total_benefit"] - df["investment_cost"]
    df["roi"] = df["net_benefit"] / df["investment_cost"]
    df["kpi_change"] = df["kpi_after"] - df["kpi_before"]
    return df


def format_currency(value: float) -> str:
    return f"${value / 1000:,.0f}K"


def portfolio_summary(df: pd.DataFrame) -> None:
    total_investment = df["investment_cost"].sum()
    total_benefit = df["total_benefit"].sum()
    total_net = df["net_benefit"].sum()
    roi = total_net / total_investment if total_investment else 0
    hours_saved = df["hours_saved"].sum()
    avg_adoption = df["automation_rate"].mean()

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Investment", format_currency(total_investment))
    col2.metric("Total Benefit", format_currency(total_benefit))
    col3.metric("Net Benefit", format_currency(total_net))
    col4.metric("Portfolio ROI", f"{roi:.1%}")
    col5.metric("Hours Saved", f"{hours_saved:,.0f}")

    st.caption(f"Average automation rate across initiatives: {avg_adoption:.1%}")


def initiative_scorecard(df: pd.DataFrame) -> pd.DataFrame:
    scorecard = (
        df.groupby(["initiative", "department", "status"], as_index=False)
        .agg(
            investment_cost=("investment_cost", "sum"),
            total_benefit=("total_benefit", "sum"),
            net_benefit=("net_benefit", "sum"),
            hours_saved=("hours_saved", "sum"),
            automation_rate=("automation_rate", "mean"),
            active_users=("active_users", "max"),
            satisfaction_score=("satisfaction_score", "mean"),
            roi=("roi", "mean"),
        )
        .sort_values("net_benefit", ascending=False)
    )
    scorecard["recommendation"] = scorecard.apply(recommend_action, axis=1)
    return scorecard


def recommend_action(row: pd.Series) -> str:
    if row["roi"] > 0.6 and row["automation_rate"] > 0.4:
        return "Scale"
    if row["roi"] > 0.2 and row["satisfaction_score"] >= 7.5:
        return "Optimize and expand"
    if row["active_users"] < 50:
        return "Increase adoption"
    return "Monitor"


def main() -> None:
    st.set_page_config(page_title="Executive AI Impact Dashboard", layout="wide")
    st.title("Executive AI Impact Dashboard")
    st.caption("Leadership view of ROI, productivity, adoption, and operational impact across AI initiatives.")

    df = load_data()

    departments = ["All"] + sorted(df["department"].unique().tolist())
    selected_department = st.sidebar.selectbox("Department", departments)
    selected_quarters = st.sidebar.multiselect(
        "Quarter",
        sorted(df["quarter"].unique().tolist()),
        default=sorted(df["quarter"].unique().tolist()),
    )

    filtered = df[df["quarter"].isin(selected_quarters)]
    if selected_department != "All":
        filtered = filtered[filtered["department"] == selected_department]

    tab_exec, tab_financial, tab_productivity, tab_adoption, tab_ops = st.tabs(
        ["Executive Summary", "Financial Impact", "Productivity", "Adoption", "Operational KPIs"]
    )

    with tab_exec:
        portfolio_summary(filtered)
        st.subheader("AI Portfolio Scorecard")
        scorecard = initiative_scorecard(filtered)
        st.dataframe(
            scorecard[
                [
                    "initiative",
                    "department",
                    "status",
                    "net_benefit",
                    "roi",
                    "hours_saved",
                    "automation_rate",
                    "active_users",
                    "satisfaction_score",
                    "recommendation",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Net Benefit By Initiative")
            fig = px.bar(scorecard, x="initiative", y="net_benefit", color="recommendation", text_auto=".2s")
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.subheader("ROI vs Adoption")
            fig = px.scatter(
                scorecard,
                x="automation_rate",
                y="roi",
                size="total_benefit",
                color="department",
                hover_name="initiative",
            )
            st.plotly_chart(fig, use_container_width=True)

    with tab_financial:
        st.subheader("Financial Impact Over Time")
        financial = filtered.groupby("quarter", as_index=False).agg(
            investment_cost=("investment_cost", "sum"),
            cost_savings=("cost_savings", "sum"),
            revenue_uplift=("revenue_uplift", "sum"),
            net_benefit=("net_benefit", "sum"),
        )
        fig = go.Figure()
        fig.add_bar(x=financial["quarter"], y=financial["cost_savings"], name="Cost Savings")
        fig.add_bar(x=financial["quarter"], y=financial["revenue_uplift"], name="Revenue Uplift")
        fig.add_scatter(x=financial["quarter"], y=financial["investment_cost"], name="Investment", mode="lines+markers")
        fig.update_layout(barmode="stack", yaxis_title="USD")
        st.plotly_chart(fig, use_container_width=True)

    with tab_productivity:
        st.subheader("Productivity Gains")
        col1, col2 = st.columns(2)
        with col1:
            fig = px.line(filtered, x="quarter", y="hours_saved", color="initiative", markers=True)
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            fig = px.line(filtered, x="quarter", y="response_time_reduction_pct", color="initiative", markers=True)
            fig.update_yaxes(tickformat=".0%")
            st.plotly_chart(fig, use_container_width=True)

    with tab_adoption:
        st.subheader("Adoption Metrics")
        col1, col2 = st.columns(2)
        with col1:
            fig = px.bar(filtered, x="quarter", y="active_users", color="initiative", barmode="group")
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            fig = px.scatter(
                filtered,
                x="usage_frequency",
                y="satisfaction_score",
                size="active_users",
                color="initiative",
                hover_name="quarter",
            )
            st.plotly_chart(fig, use_container_width=True)

    with tab_ops:
        st.subheader("Operational KPI Movement")
        latest = filtered.sort_values("quarter").groupby("initiative", as_index=False).tail(1)
        ops = latest[["initiative", "primary_operational_kpi", "kpi_before", "kpi_after"]].copy()
        ops["improvement_direction"] = ops.apply(
            lambda row: "Higher is better" if "accuracy" in row["primary_operational_kpi"].lower() or "conversion" in row["primary_operational_kpi"].lower() else "Lower is better",
            axis=1,
        )
        st.dataframe(ops, use_container_width=True, hide_index=True)
        fig = px.bar(
            ops.melt(
                id_vars=["initiative", "primary_operational_kpi"],
                value_vars=["kpi_before", "kpi_after"],
                var_name="period",
                value_name="kpi_value",
            ),
            x="initiative",
            y="kpi_value",
            color="period",
            barmode="group",
            facet_col="primary_operational_kpi",
        )
        st.plotly_chart(fig, use_container_width=True)


if __name__ == "__main__":
    main()

