# scripts/gen_site_stats.py

import os
import json
from datetime import datetime

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
)
from google.oauth2 import service_account


PROPERTY_ID = "514471754"
LOCAL_KEY_FILE = "ga-dakebu-5c9fdbc20e9e.json"
OUTPUT_PATH = "image/site_statistics.png" 


def make_client():
    if "GA_KEY_JSON" in os.environ:
        info = json.loads(os.environ["GA_KEY_JSON"])
        creds = service_account.Credentials.from_service_account_info(info)
    else:
        creds = service_account.Credentials.from_service_account_file(LOCAL_KEY_FILE)
    return BetaAnalyticsDataClient(credentials=creds)


def fetch_ga():
    client = make_client()
    prop = f"properties/{PROPERTY_ID}"

    resp_year = client.run_report(
        RunReportRequest(
            property=prop,
            dimensions=[],
            metrics=[
                Metric(name="screenPageViews"),
                Metric(name="activeUsers"),
            ],
            date_ranges=[DateRange(start_date="365daysAgo", end_date="today")],
        )
    )
    if resp_year.rows:
        total_views_365 = int(resp_year.rows[0].metric_values[0].value)
        total_users_365 = int(resp_year.rows[0].metric_values[1].value)
    else:
        total_views_365 = 0
        total_users_365 = 0

    resp_daily = client.run_report(
        RunReportRequest(
            property=prop,
            dimensions=[Dimension(name="date")],
            metrics=[Metric(name="screenPageViews")],
            date_ranges=[DateRange(start_date="90daysAgo", end_date="today")],
        )
    )

    if resp_daily.rows:
        df_daily = pd.DataFrame(
            {
                "date": [
                    datetime.strptime(r.dimension_values[0].value, "%Y%m%d")
                    for r in resp_daily.rows
                ],
                "views": [
                    int(r.metric_values[0].value) for r in resp_daily.rows
                ],
            }
        ).sort_values("date")
    else:
        df_daily = pd.DataFrame({"date": [], "views": []})

    resp_country = client.run_report(
        RunReportRequest(
            property=prop,
            dimensions=[Dimension(name="country")],
            metrics=[Metric(name="screenPageViews")],
            date_ranges=[DateRange(start_date="90daysAgo", end_date="today")],
        )
    )

    if resp_country.rows:
        df_country = pd.DataFrame(
            {
                "country": [r.dimension_values[0].value for r in resp_country.rows],
                "views": [int(r.metric_values[0].value) for r in resp_country.rows],
            }
        )
        df_country = (
            df_country[df_country["views"] > 0]
            .sort_values("views", ascending=False)
            .head(20)
        )
    else:
        df_country = pd.DataFrame({"country": [], "views": []})

    return total_views_365, total_users_365, df_daily, df_country


def draw_picture(total_views_365, total_users_365, df_daily, df_country):
    plt.style.use("seaborn-v0_8-whitegrid")
    plt.rcParams["font.size"] = 6
    plt.rcParams["font.family"] = "DejaVu Sans"

    fig = plt.figure(figsize=(9, 10))

    if not df_daily.empty:
        cap = df_daily["views"].quantile(0.99)
        total_views_90 = int(df_daily["views"].sum())
        total_views_90_win = int(df_daily["views"].clip(upper=cap).sum())
        df_daily["winsor"] = df_daily["views"].clip(upper=cap)
    else:
        cap = 0
        total_views_90 = 0
        total_views_90_win = 0
        df_daily["winsor"] = df_daily.get("views", pd.Series(dtype=int))

    today = datetime.today().strftime("%Y-%m-%d")

    summary = (
        f"Last Updated:              {today}\n"
        f"Total Visitors (365 Days): {total_users_365:,}\n"
        f"Total Views (365 Days):    {total_views_365:,}\n"
        f"Total Views (90 Days):     {total_views_90:,}\n"
        f"Total Views (90 Days):     {total_views_90_win:,} (winsorized at 99%)"
    )

    ax_text = fig.add_axes([0.08, 0.80, 0.84, 0.14])
    ax_text.axis("off")
    ax_text.text(
        0.0,
        1.0,
        summary,
        va="top",
        ha="left",
        family="monospace",
        fontsize=6,
    )

    ax1 = fig.add_axes([0.08, 0.50, 0.84, 0.24])
    if not df_daily.empty:
        ax1.plot(df_daily["date"], df_daily["winsor"], marker="o", markersize=2.5)
        min_d = df_daily["date"].min()
        max_d = df_daily["date"].max()
        if min_d == max_d:
            from datetime import timedelta
            ax1.set_xlim(min_d - timedelta(days=1), max_d + timedelta(days=1))
        else:
            ax1.set_xlim(min_d, max_d)
    ax1.set_title("Daily Site Views (Past 90 Days), winsorized at 99%", fontsize=7)
    ax1.set_ylabel("Views")
    ax1.set_xlabel("")
    for label in ax1.get_xticklabels():
        label.set_rotation(30)
        label.set_ha("right")

    ax2 = fig.add_axes([0.08, 0.12, 0.84, 0.32])
    if not df_country.empty:
        y = np.arange(len(df_country))
        ax2.barh(y, df_country["views"])
        ax2.set_yticks(y)
        ax2.set_yticklabels(df_country["country"])
        ax2.invert_yaxis()
    ax2.set_xlabel("Views")
    ax2.set_title("Top 20 Regions by Views (Past 90 Days)", fontsize=7)

    fig.savefig(OUTPUT_PATH, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main():
    t365, u365, daily, country = fetch_ga()
    draw_picture(t365, u365, daily, country)


if __name__ == "__main__":
    main()
