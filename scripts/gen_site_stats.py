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

    # ---- 365 days ----
    resp_year = client.run_report(
        RunReportRequest(
            property=prop,
            dimensions=[],
            metrics=[
                Metric(name="screenPageViews"),
                Metric(name="activeUsers"),
            ],
            date_ranges=[DateRange(start_date="365daysAgo", end_date="yesterday")],
        )
    )
    if resp_year.rows:
        total_views_365 = int(resp_year.rows[0].metric_values[0].value)
        total_users_365 = int(resp_year.rows[0].metric_values[1].value)
    else:
        total_views_365 = 0
        total_users_365 = 0

    # ---- 90 days daily ----
    resp_daily = client.run_report(
        RunReportRequest(
            property=prop,
            dimensions=[Dimension(name="date")],
            metrics=[Metric(name="screenPageViews")],
            date_ranges=[DateRange(start_date="90daysAgo", end_date="yesterday")],
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
        )
        df_daily = df_daily.sort_values("date")
    else:
        df_daily = pd.DataFrame({"date": [], "views": []})

    # ---- country ----
    resp_country = client.run_report(
        RunReportRequest(
            property=prop,
            dimensions=[Dimension(name="country")],
            metrics=[Metric(name="screenPageViews")],
            date_ranges=[DateRange(start_date="90daysAgo", end_date="yesterday")],
        )
    )

    if resp_country.rows:
        df_country = pd.DataFrame(
            {
                "country": [r.dimension_values[0].value for r in resp_country.rows],
                "views": [int(r.metric_values[0].value) for r in resp_country.rows],
            }
        )
        df_country = df_country[df_country["views"] > 0]
        df_country = df_country.sort_values("views", ascending=False).head(20)
    else:
        df_country = pd.DataFrame({"country": [], "views": []})

    return total_views_365, total_users_365, df_daily, df_country


def draw_picture(total_views_365, total_users_365, df_daily, df_country):
    plt.style.use("seaborn-v0_8-whitegrid")

    # 
    plt.rcParams["font.size"] = 11
    plt.rcParams["font.family"] = "DejaVu Sans"
    plt.rcParams["axes.titleweight"] = "bold"

    fig = plt.figure(figsize=(10, 12))

    today = datetime.today().strftime("%Y-%m-%d")

    #
    summary = (
        f"Last Updated: {today}\n"
        f"Total Visitors (365 Days): {total_users_365:,}\n"
        f"Total Views (365 Days): {total_views_365:,}\n"
    )

    ax_text = fig.add_axes([0.05, 0.87, 0.9, 0.10])
    ax_text.axis("off")
    ax_text.text(
        0,
        0.9,
        summary,
        va="top",
        ha="left",
        fontsize=12,
        family="monospace",
    )

    # 
    ax1 = fig.add_axes([0.08, 0.55, 0.85, 0.28])
    if not df_daily.empty:
        cap = df_daily["views"].quantile(0.99)
        df_daily["winsor"] = df_daily["views"].clip(upper=cap)
        ax1.plot(df_daily["date"], df_daily["winsor"], marker="o", markersize=3)
    ax1.set_title("Daily Site Views (Past 90 Days)")
    ax1.set_ylabel("Views")
    for label in ax1.get_xticklabels():
        label.set_rotation(30)
        label.set_ha("right")

    # 
    ax2 = fig.add_axes([0.08, 0.10, 0.85, 0.38])
    if not df_country.empty:
        y = np.arange(len(df_country))
        ax2.barh(y, df_country["views"])
        ax2.set_yticks(y)
        ax2.set_yticklabels(df_country["country"])
        ax2.invert_yaxis()
    ax2.set_xlabel("Views")
    ax2.set_title("Top 20 Regions by Views (Past 90 Days)")

    fig.savefig(OUTPUT_PATH, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main():
    t365, u365, daily, country = fetch_ga()
    draw_picture(t365, u365, daily, country)


if __name__ == "__main__":
    main()
