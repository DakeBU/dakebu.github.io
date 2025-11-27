import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange, Dimension, Metric, RunReportRequest
)
from google.oauth2 import service_account

# ========== ==========
GA_PROPERTY_ID = "514471754"
KEY_PATH = "ga-dakebu-5c9fdbc20e9e.json"      
# ==============================

creds = service_account.Credentials.from_service_account_file(KEY_PATH)
client = BetaAnalyticsDataClient(credentials=creds)

# --------------------------
# 1. Past 90 days daily pageviews
# --------------------------
resp_daily = client.run_report(
    RunReportRequest(
        property=f"properties/{GA_PROPERTY_ID}",
        dimensions=[Dimension(name="date")],
        metrics=[Metric(name="screenPageViews")],
        date_ranges=[DateRange(start_date="90daysAgo", end_date="yesterday")],
    )
)

df_daily = pd.DataFrame(
    {
        "date": [
            datetime.strptime(row.dimension_values[0].value, "%Y%m%d")
            for row in resp_daily.rows
        ],
        "views": [int(row.metric_values[0].value) for row in resp_daily.rows],
    }
).sort_values("date")

# Winsorize 99%
cap99 = df_daily["views"].quantile(0.99)
df_daily["views_win"] = df_daily["views"].clip(upper=cap99)

# --------------------------
# 2. Country 90 days
# --------------------------
resp_country = client.run_report(
    RunReportRequest(
        property=f"properties/{GA_PROPERTY_ID}",
        dimensions=[Dimension(name="country")],
        metrics=[Metric(name="screenPageViews")],
        date_ranges=[DateRange(start_date="90daysAgo", end_date="yesterday")],
    )
)

df_country = pd.DataFrame(
    {
        "country": [row.dimension_values[0].value for row in resp_country.rows],
        "views": [int(row.metric_values[0].value) for row in resp_country.rows],
    }
)

df_country = df_country.sort_values("views", ascending=False).head(20)

# --------------------------
# Plot everything into one PNG (like mingze-gao.com)
# --------------------------
plt.figure(figsize=(9, 12))

# (A) metadata text
plt.suptitle("Site statistics", fontsize=22, x=0.05, ha="left")

today = datetime.today().date()
total_365 = df_daily["views"].sum()  # simplified, GA API 可扩展

text = (
    f"Last Updated:              {today}\n"
    f"Total Views (90 Days):     {df_daily['views'].sum():,}\n"
    f"Total Views (90 Days, win99): {df_daily['views_win'].sum():,}\n"
)
plt.text(0.05, 0.86, text, family="monospace", fontsize=12)

# (B) line chart
plt.subplot(2, 1, 1)
plt.plot(df_daily["date"], df_daily["views_win"], marker="o")
plt.title("Daily Site Views (Past 90 Days), winsorized at 99%")
plt.ylabel("Views")
plt.grid(True, alpha=0.3)

# (C) bar chart
plt.subplot(2, 1, 2)
plt.barh(df_country["country"], df_country["views"])
plt.title("Top 20 Regions by Views (Past 90 Days)")
plt.xlabel("Views")
plt.gca().invert_yaxis()

plt.tight_layout(rect=[0,0,1,0.88])
plt.savefig("image/site_statistics.png", dpi=200)
plt.close()

print("Saved: image/site_statistics.png")
