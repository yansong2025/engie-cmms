import io
import os
import matplotlib
# CRITICAL: Headless rendering for serverless environments
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages
from fastapi import FastAPI, UploadFile, File, HTTPException
from supabase import create_client, Client

app = FastAPI()

COST_PER_KWH = 0.15  # Estimated tariff rate ($/kWh)
CO2_PER_KWH = 0.85   # Estimated grid factor (lbs CO2 / kWh)

@app.post("/api/analyze")
async def analyze_utility_data(file: UploadFile = File(...)):
    # 1. Fetch Supabase environment variables from Vercel
    supabase_url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url or not supabase_key:
        raise HTTPException(status_code=500, detail="Missing Supabase environment variables.")

    supabase: Client = create_client(supabase_url, supabase_key)

    try:
        # 2. Read file directly into memory buffer
        file_bytes = await file.read()
        file_buffer = io.BytesIO(file_bytes)

        if file.filename.lower().endswith(".csv"):
            df = pd.read_csv(file_buffer)
        else:
            df = pd.read_excel(file_buffer, header=1)

        # Standardize column headers
        df.columns = [str(col).strip() for col in df.columns]

        # Auto-detect date and consumption columns
        date_col = next(
            col for col in df.columns
            if any(x in col.lower() for x in ["date", "datetime", "timestamp", "time"])
        )
        consumption_col = next(
            col for col in df.columns
            if "consumption" in col.lower()
        )

        df = df[[date_col, consumption_col]].copy()
        df.columns = ["datetime", "consumption"]
        df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
        df["consumption"] = pd.to_numeric(df["consumption"], errors="coerce")
        df = df.dropna().sort_values("datetime")

        # ==============================================================================
        # FEATURE ENGINEERING & METRICS
        # ==============================================================================
        df["date"] = df["datetime"].dt.date
        df["day_name"] = df["datetime"].dt.day_name()
        df["day_of_week"] = df["datetime"].dt.dayofweek
        df["is_weekend"] = df["day_of_week"] >= 5
        df["hour"] = df["datetime"].dt.hour

        total_kwh = df["consumption"].sum()
        est_cost = total_kwh * COST_PER_KWH
        est_co2_lbs = total_kwh * CO2_PER_KWH

        avg_reading = df["consumption"].mean()
        max_reading = df["consumption"].max()
        min_baseload = df[df["consumption"] > 0]["consumption"].min()
        peak_row = df.loc[df["consumption"].idxmax()]

        load_factor = (
            (avg_reading / max_reading * 100) if max_reading and max_reading > 0 else 0
        )

        std_dev = df["consumption"].std()
        anomaly_threshold = avg_reading + (3 * std_dev)
        anomalies = df[df["consumption"] > anomaly_threshold]

        daily_df = df.groupby("date", as_index=False)["consumption"].sum()
        daily_df["rolling_7d"] = daily_df["consumption"].rolling(7, min_periods=1).mean()

        hourly_wkday = df[~df["is_weekend"]].groupby("hour")["consumption"].mean().reindex(range(24))
        hourly_wkend = df[df["is_weekend"]].groupby("hour")["consumption"].mean().reindex(range(24))

        heatmap_data = df.pivot_table(
            index="day_of_week", columns="hour", values="consumption", aggfunc="mean"
        ).fillna(0)

        days_map = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}
        heatmap_data.index = [days_map[i] for i in heatmap_data.index if i in days_map]

        peak_day_name = peak_row["datetime"].strftime("%A")
        offpeak_diff_pct = (
            ((hourly_wkday.mean() - hourly_wkend.mean()) / hourly_wkday.mean() * 100)
            if hourly_wkday.mean() > 0 else 0
        )

        # ==============================================================================
        # PDF GENERATION (IN-MEMORY BUFFER)
        # ==============================================================================
        pdf_buffer = io.BytesIO()

        plt.style.use(
            "seaborn-v0_8-whitegrid"
            if "seaborn-v0_8-whitegrid" in plt.style.available
            else "default"
        )

        with PdfPages(pdf_buffer) as pdf:
            # PAGE 1
            fig = plt.figure(figsize=(8.5, 11))
            fig.text(0.1, 0.94, "CMMS UTILITY & ENERGY ANALYTICS REPORT", fontsize=16, fontweight="bold")

            summary_text = (
                f"REPORTING PERIOD: {df['datetime'].min().strftime('%Y-%m-%d')} to "
                f"{df['datetime'].max().strftime('%Y-%m-%d')}\n"
                f"{'='*62}\n\n"
                f"FINANCIAL & ENVIRONMENTAL IMPACT\n"
                f"  Total Consumption  : {total_kwh:,.2f} kWh\n"
                f"  Estimated Cost     : ${est_cost:,.2f} (@ ${COST_PER_KWH}/kWh)\n"
                f"  Carbon Footprint   : {est_co2_lbs:,.2f} lbs CO2e\n\n"
                f"OPERATIONAL METRICS\n"
                f"  Average Interval   : {avg_reading:,.2f} kWh\n"
                f"  Est. Base Load     : {min_baseload:,.2f} kWh (Non-zero Min)\n"
                f"  Peak Consumption   : {max_reading:,.2f} kWh\n"
                f"  Peak Occurrence    : {peak_row['datetime'].strftime('%Y-%m-%d %H:%M')}\n"
                f"  Load Factor        : {load_factor:.2f}%\n\n"
                f"DATA INTEGRITY & ANOMALIES\n"
                f"  Zero Readings      : {(df['consumption'] == 0).sum()}\n"
                f"  Negative Readings  : {(df['consumption'] < 0).sum()}\n"
                f"  3-Sigma Spikes     : {len(anomalies)} (> {anomaly_threshold:.2f} kWh)\n"
                f"{'='*62}"
            )

            fig.text(0.1, 0.90, summary_text, fontsize=9.5, family="monospace", verticalalignment="top")

            ax1 = fig.add_axes([0.1, 0.08, 0.8, 0.38])
            ax1.plot(df["datetime"], df["consumption"], color="#2b5c8f", alpha=0.6, label="Interval Usage")
            ax1.axhline(anomaly_threshold, color="red", linestyle="--", linewidth=1.5, label="3-Sigma Limit")

            if not anomalies.empty:
                ax1.scatter(anomalies["datetime"], anomalies["consumption"], color="red", s=25, zorder=5, label="Anomalies")

            ax1.set_title("Interval Consumption & Anomaly Spikes", fontweight="bold")
            ax1.set_ylabel("kWh")
            ax1.legend(loc="upper right")

            pdf.savefig(fig)
            plt.close(fig)

            # PAGE 2
            fig, (ax_daily, ax_hourly) = plt.subplots(2, 1, figsize=(8.5, 11))
            ax_daily.plot(daily_df["date"], daily_df["consumption"], color="#abd9e9", label="Daily Total", alpha=0.8)
            ax_daily.plot(daily_df["date"], daily_df["rolling_7d"], color="#2c7bb6", linewidth=2, label="7-Day Moving Avg")
            ax_daily.set_title("Daily Consumption & 7-Day Trend", fontweight="bold")
            ax_daily.set_ylabel("kWh")
            ax_daily.legend()

            ax_hourly.plot(hourly_wkday.index, hourly_wkday.values, marker="o", label="Weekday Avg", color="#d7191c")
            ax_hourly.plot(hourly_wkend.index, hourly_wkend.values, marker="s", linestyle="--", label="Weekend Avg", color="#2b83ba")
            ax_hourly.set_title("Hourly Profile: Weekday vs. Weekend", fontweight="bold")
            ax_hourly.set_xlabel("Hour of Day (0-23)")
            ax_hourly.set_ylabel("Avg kWh")
            ax_hourly.set_xticks(range(0, 24))
            ax_hourly.legend()

            p2_insight_text = (
                f"Key Insights:\n"
                f"• Weekdays consume approximately {offpeak_diff_pct:.1f}% more energy per hour than weekends.\n"
                f"• Peak hour on weekdays occurs at {hourly_wkday.idxmax()}:00 ({hourly_wkday.max():.2f} kWh avg)."
            )
            fig.text(0.1, 0.02, p2_insight_text, fontsize=9, bbox=dict(boxstyle="round,pad=0.5", facecolor="#f0f4f8", edgecolor="#2c7bb6", alpha=0.9))
            plt.subplots_adjust(top=0.92, bottom=0.15, hspace=0.35)
            pdf.savefig(fig)
            plt.close(fig)

            # PAGE 3
            fig, ax_hm = plt.subplots(figsize=(8.5, 9))
            cax = ax_hm.imshow(heatmap_data.values, cmap="YlOrRd", aspect="auto")
            fig.colorbar(cax, ax=ax_hm, label="Average kWh")

            ax_hm.set_xticks(range(24))
            ax_hm.set_yticks(range(len(heatmap_data.index)))
            ax_hm.set_yticklabels(heatmap_data.index)
            ax_hm.set_xlabel("Hour of Day")
            ax_hm.set_title("Consumption Heatmap (Day of Week vs. Hour)", fontweight="bold", pad=15)

            p3_insight_text = (
                f"Key Insights:\n"
                f"• Highest operational intensity is centered around {peak_day_name}s near hour {peak_row['datetime'].hour}:00.\n"
                f"• Darker cells highlight peak load hours subject to potential utility demand charges."
            )
            fig.text(0.1, 0.05, p3_insight_text, fontsize=9, bbox=dict(boxstyle="round,pad=0.5", facecolor="#fff8f0", edgecolor="#e6550d", alpha=0.9))
            plt.subplots_adjust(bottom=0.22)
            pdf.savefig(fig)
            plt.close(fig)

        # ==============================================================================
        # 3. UPLOAD PDF TO SUPABASE STORAGE 'pdf-reports'
        # ==============================================================================
        clean_name = os.path.splitext(file.filename)[0]
        output_filename = f"report_{clean_name}.pdf"

        supabase.storage.from_("pdf-reports").upload(
            path=output_filename,
            file=pdf_buffer.getvalue(),
            file_options={"content-type": "application/pdf", "upsert": "true"}
        )

        pdf_url = supabase.storage.from_("pdf-reports").get_public_url(output_filename)

        return {"success": True, "pdf_url": pdf_url}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))