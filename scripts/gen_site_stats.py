# scripts/gen_site_stats.py

import os
import json
from datetime import datetime

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
)
from google.oauth2 import service_account


# ==================
PROPERTY_ID = "514471754" 
LOCAL_KEY_FILE = "ga-dakebu-5c9fdbc20e9e.json" 
OUTPUT_PATH = "image/site_statistics.png"
# =======================


def make_client():
    if "GA_KEY_JSON" in os.environ:
        info = json.loads(os.environ["GA_KEY_JSON"])
        creds = service_account.Credentials.from_service_account_info(info)
    else:
        creds = service_account.Credentials.from_service_account_file(LOCAL_KEY_FILE)
    return BetaAnalyticsDataClient(credentials=creds)


def fetch_ga_data():
    client = make_client()
    prop = f"properties/{PROPERTY_ID}"

    # 365 天总量
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

    # 90 天每日
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
        ).sort_values("date")
    else:
        df_daily = pd.DataFrame({"date": [], "views": []})

    # 90 天按国家
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
        df_country = (
            df_country[df_country["views"] > 0]
            .sort_values("views", ascending=False)
            .head(20)
        )
    else:
        df_country = pd.DataFrame({"country": [], "views": []})

    return total_views_365, total_users_365, df_daily, df_country


def plot_stats(total_views_365, total_users_365, df_daily, df_country):
    # 
    if not df_daily.empty:
        cap99 = df_daily["views"].quantile(0.99)
        total_views_90 = int(df_daily["views"].sum())
        total_views_90_win = int(df_daily["views"].clip(upper=cap99).sum())
        df_daily["views_win"] = df_daily["views"].clip(upper=cap99)
    else:
        cap99 = 0
        total_views_90 = 0
        total_views_90_win = 0
        df_daily["views_win"] = []

    today = datetime.today().date()

    # ------- 画图风格 ----------
    plt.style.use("seaborn-v0_8-whitegrid")
    fig = plt.figure(figsize=(8.27, 11.69))  # A4 比例

    # 标题 + 文本摘要
    fig.suptitle("Site statistics", fontsize=18, x=0.08, y=0.96, ha="left")

    text_lines = [
        f"Last Updated:              {today.isoformat()}",
        f"Total Visitors (365 Days): {total_users_365:,}",
        f"Total Views   (365 Days):  {total_views_365:,}",
        f"Total Views   (90 Days):   {total_views_90:,}",
        f"Total Views   (90 Days):   {total_views_90_win:,} (winsorized at 99%)",
    ]

    fig.text(
        0.08,
        0.90,
        "\n".join(text_lines),
        family="monospace",
        fontsize=10,
        va="top",
    )

    #
    ax1 = fig.add_axes([0.1, 0.56, 0.85, 0.30])  # [left, bottom, width, height]
    if not df_daily.empty:
        ax1.plot(
            df_daily["date"],
            df_daily["views_win"],
            marker="o",
            linewidth=1.3,
        )
    ax1.set_title("Daily Site Views (Past 90 Days), winsorized at 99%")
    ax1.set_ylabel("Views")
    ax1.set_xlabel("")
    for label in ax1.get_xticklabels():
        label.set_rotation(30)
        label.set_ha("right")

    #
    ax2 = fig.add_axes([0.1, 0.10, 0.85, 0.36])
    if not df_country.empty:
        y = np.arange(len(df_country))
        ax2.barh(y, df_country["views"])
        ax2.set_yticks(y)
        ax2.set_yticklabels(df_country["country"])
        ax2.invert_yaxis()
    ax2.set_xlabel("Views")
    ax2.set_title("Top 20 Regions by Views (Past 90 Days)")

    fig.savefig(OUTPUT_PATH, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved statistics figure to {OUTPUT_PATH}")


def main():
    total_views_365, total_users_365, df_daily, df_country = fetch_ga_data()
    plot_stats(total_views_365, total_users_365, df_daily, df_country)


if __name__ == "__main__":
    main()
