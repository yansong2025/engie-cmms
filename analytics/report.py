"""Render an Analysis as a 3-page PDF."""

import io
import textwrap

import numpy as np
from matplotlib import colormaps
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure

from .core import BASELOAD_PERCENTILE, Analysis

# Figures are built with the object API (no pyplot) so rendering holds no
# global state and is safe to run from the server's worker threads.
PAGE_SIZE = (8.5, 11)


def _style(ax):
    ax.grid(True, alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)


def _insight_box(fig, y, lines, face, edge):
    text = "Key Insights:\n" + "\n".join(f"• {line}" for line in lines)
    fig.text(
        0.1, y, text, fontsize=9, verticalalignment="bottom",
        bbox=dict(boxstyle="round,pad=0.5", facecolor=face, edgecolor=edge, alpha=0.9),
    )


def _summary_page(a: Analysis) -> Figure:
    m, q, df = a.metrics, a.quality, a.df
    fig = Figure(figsize=PAGE_SIZE)
    fig.text(0.1, 0.94, "CMMS UTILITY & ENERGY ANALYTICS REPORT", fontsize=16, fontweight="bold")

    rule = "=" * 66
    summary_text = (
        f"REPORTING PERIOD: {m['period_start'][:10]} to {m['period_end'][:10]}\n"
        f"{rule}\n\n"
        f"COST & CARBON (ESTIMATES)\n"
        f"  Total Consumption  : {m['total_kwh']:,.2f} kWh\n"
        f"  Estimated Cost     : {m['est_cost']:,.2f} (@ {m['tariff']:g} per kWh)\n"
        f"  Carbon Footprint   : {m['est_co2_kg']:,.2f} kg CO2e (@ {m['emission_factor']:g} kg/kWh)\n\n"
        f"OPERATIONAL METRICS\n"
        f"  Reading Interval   : {q['interval_minutes']:g} min\n"
        f"  Average Reading    : {m['avg_reading_kwh']:,.2f} kWh\n"
        f"  Est. Base Load     : {m['base_load_kwh']:,.2f} kWh ({BASELOAD_PERCENTILE}th percentile)\n"
        f"  Peak Reading       : {m['peak_kwh']:,.2f} kWh at {m['peak_at'][:16].replace('T', ' ')}\n"
        f"  Load Factor        : {m['load_factor_pct']:.2f}%\n\n"
        f"DATA QUALITY\n"
        f"  Rows Read / Used   : {q['rows_read']:,} / {q['rows_used']:,}\n"
        f"  Excluded           : {q['unreadable_dates']} bad date, {q['non_numeric_values']} non-numeric,\n"
        f"                       {q['negative_readings']} negative, {q['duplicate_timestamps']} duplicate\n"
        f"  Missing Intervals  : {q['missing_intervals']:,} in {q['gaps']} gap(s), "
        f"longest {q['longest_gap_hours']:g} h\n"
        f"  Zero Readings      : {q['zero_readings']:,}\n"
        f"  Anomalies          : {m['anomalies_high']} high, {m['anomalies_low']} low "
        f"(vs. typical for {m['anomaly_basis']})\n"
        f"{rule}"
    )
    fig.text(0.1, 0.90, summary_text, fontsize=9, family="monospace", verticalalignment="top")

    if a.notes:
        wrapped = "\n".join(textwrap.fill(f"Note: {n}", 100) for n in a.notes)
        fig.text(0.1, 0.52, wrapped, fontsize=8, color="#8a4b00", verticalalignment="top")

    ax = fig.add_axes([0.1, 0.07, 0.8, 0.34])
    # Rasterized: tens of thousands of vector segments would bloat the PDF.
    ax.plot(df["datetime"], df["consumption"], color="#2b5c8f", alpha=0.6, linewidth=0.8,
            label="Interval Usage", rasterized=True)
    high, low = df[df["anomaly"] == 1], df[df["anomaly"] == -1]
    if not high.empty:
        ax.scatter(high["datetime"], high["consumption"], color="#d7191c", s=14, zorder=5,
                   label="Unusually high")
    if not low.empty:
        ax.scatter(low["datetime"], low["consumption"], color="#e6850d", s=14, zorder=5,
                   marker="v", label="Unusually low")
    ax.set_title("Interval Consumption & Anomalies", fontweight="bold")
    ax.set_ylabel("kWh per reading")
    ax.legend(loc="upper right", fontsize=8)
    _style(ax)
    fig.autofmt_xdate()
    return fig


def _trend_page(a: Analysis) -> Figure:
    m = a.metrics
    fig = Figure(figsize=PAGE_SIZE)
    ax_daily, ax_hourly = fig.subplots(2, 1)

    ax_daily.plot(a.daily["date"], a.daily["consumption"], color="#abd9e9", label="Daily Total")
    ax_daily.plot(a.daily["date"], a.daily["rolling_7d"], color="#2c7bb6", linewidth=2,
                  label="7-Day Moving Avg")
    ax_daily.set_title("Daily Consumption & 7-Day Trend", fontweight="bold")
    ax_daily.set_ylabel("kWh")
    ax_daily.tick_params(axis="x", labelrotation=30)
    ax_daily.legend()
    _style(ax_daily)

    insights = []
    if a.hourly_weekday.notna().any():
        ax_hourly.plot(a.hourly_weekday.index, a.hourly_weekday.values, marker="o",
                       label="Weekday Avg", color="#d7191c")
        insights.append(
            f"Weekday consumption peaks at {m['weekday_peak_hour']:02d}:00 "
            f"({a.hourly_weekday.max():.2f} kWh avg per reading)."
        )
    if a.hourly_weekend.notna().any():
        ax_hourly.plot(a.hourly_weekend.index, a.hourly_weekend.values, marker="s",
                       linestyle="--", label="Weekend Avg", color="#2b83ba")
    ax_hourly.set_title("Hourly Profile: Weekday vs. Weekend", fontweight="bold")
    ax_hourly.set_xlabel("Hour of Day (0-23)")
    ax_hourly.set_ylabel("Avg kWh per reading")
    ax_hourly.set_xticks(range(24))
    ax_hourly.legend()
    _style(ax_hourly)

    pct = m["weekday_vs_weekend_pct"]
    if pct is None:
        insights.append("The data does not cover both weekdays and weekends, so they are not compared.")
    else:
        direction = "more" if pct >= 0 else "less"
        insights.insert(0, f"Weekdays use about {abs(pct):.1f}% {direction} energy per reading than weekends.")

    _insight_box(fig, 0.03, insights, "#f0f4f8", "#2c7bb6")
    fig.subplots_adjust(top=0.94, bottom=0.17, hspace=0.4)
    return fig


def _heatmap_page(a: Analysis) -> Figure:
    m = a.metrics
    fig = Figure(figsize=(8.5, 9))
    ax = fig.subplots()

    # Cells with no data are masked (drawn grey) rather than shown as zero usage.
    values = np.ma.masked_invalid(a.heatmap.to_numpy(dtype=float))
    cmap = colormaps["YlOrRd"].with_extremes(bad="#e6e6e6")
    image = ax.imshow(values, cmap=cmap, aspect="auto")
    fig.colorbar(image, ax=ax, label="Average kWh per reading")

    ax.set_xticks(range(24))
    ax.set_yticks(range(len(a.heatmap.index)))
    ax.set_yticklabels(a.heatmap.index)
    ax.set_xlabel("Hour of Day")
    ax.set_title("Consumption Heatmap (Day of Week vs. Hour)", fontweight="bold", pad=15)

    insights = [
        f"Average consumption is highest on {m['busiest_day']}s around {m['busiest_hour']:02d}:00.",
        "Darker cells mark the hours most likely to drive utility demand charges.",
    ]
    if values.mask.any():
        insights.append("Grey cells have no readings.")
    _insight_box(fig, 0.04, insights, "#fff8f0", "#e6550d")
    fig.subplots_adjust(bottom=0.24)
    return fig


def build_pdf(analysis: Analysis) -> bytes:
    buffer = io.BytesIO()
    with PdfPages(buffer) as pdf:
        for page in (_summary_page, _trend_page, _heatmap_page):
            pdf.savefig(page(analysis), dpi=150)
    return buffer.getvalue()
