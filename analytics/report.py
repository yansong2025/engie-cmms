"""Render an Analysis as a PDF report."""

import io
import textwrap
from datetime import date, datetime

import numpy as np
from matplotlib import colormaps
from matplotlib import dates as mdates
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


def _profile_line(a: Analysis) -> str:
    if a.day_profiles is None:
        return "not enough data"
    return (
        f"{len(a.day_profiles['profiles'])} typical, "
        f"{len(a.day_profiles['unusual_days'])} unusual day(s)"
    )


def _duration(minutes: int) -> str:
    hours, mins = divmod(minutes, 60)
    return f"{hours} h {mins:02d} min" if hours else f"{mins} min"


def _table(ax, columns, rows, widths):
    ax.axis("off")
    table = ax.table(cellText=rows, colLabels=columns, colWidths=widths, loc="upper center",
                     cellLoc="left")
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1, 1.5)
    for (row, _), cell in table.get_celld().items():
        cell.set_edgecolor("#d0d7de")
        if row == 0:
            cell.set_facecolor("#f0f4f8")
            cell.set_text_props(fontweight="bold")
    return table


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
        f"  Anomaly Events     : {m['anomaly_events_high']} high, {m['anomaly_events_low']} low "
        f"(vs. typical for {m['anomaly_basis']})\n"
        f"  Excess In Events   : {m['anomaly_excess_kwh']:,.2f} kWh ({m['anomaly_excess_cost']:,.2f})\n"
        f"  Day Profiles       : {_profile_line(a)}\n"
        f"{rule}"
    )
    fig.text(0.1, 0.90, summary_text, fontsize=9, family="monospace", verticalalignment="top")

    if a.notes:
        wrapped = "\n".join(textwrap.fill(f"Note: {n}", 100) for n in a.notes)
        fig.text(0.1, 0.50, wrapped, fontsize=8, color="#8a4b00", verticalalignment="top")

    ax = fig.add_axes([0.1, 0.07, 0.8, 0.34])
    # Rasterized: tens of thousands of vector segments would bloat the PDF.
    ax.plot(df["datetime"], df["consumption"], color="#2b5c8f", alpha=0.6, linewidth=0.8,
            label="Interval Usage", rasterized=True)
    high, low = df[df["anomaly"] == 1], df[df["anomaly"] == -1]
    if not high.empty:
        ax.scatter(high["datetime"], high["consumption"], color="#d7191c", s=14, zorder=5,
                   label="Anomaly event (high)")
    if not low.empty:
        ax.scatter(low["datetime"], low["consumption"], color="#e6850d", s=14, zorder=5,
                   marker="v", label="Anomaly event (low)")
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


PROFILE_COLORS = ["#2c7bb6", "#d7191c", "#1a9641", "#7b3294"]
MAX_TABLE_ROWS = 12


def _profiles_page(a: Analysis) -> Figure:
    profiles = a.day_profiles["profiles"]
    unusual = a.day_profiles["unusual_days"]
    colors = {p["label"]: PROFILE_COLORS[i] for i, p in enumerate(profiles)}

    fig = Figure(figsize=PAGE_SIZE)
    fig.text(0.1, 0.95, "TYPICAL-DAY PROFILES", fontsize=14, fontweight="bold")

    ax = fig.add_axes([0.1, 0.65, 0.8, 0.25])
    for day in unusual:
        ax.plot(range(24), day["hourly_kwh"], color="#9aa0a6", linewidth=0.9, linestyle="--")
    if unusual:
        ax.plot([], [], color="#9aa0a6", linewidth=0.9, linestyle="--", label="Unusual days")
    for p in profiles:
        ax.plot(range(24), p["hourly_kwh"], color=colors[p["label"]], linewidth=2.2, marker="o",
                markersize=3,
                label=f"Profile {p['label']}: {p['days']} days, {p['description']}, "
                      f"avg {p['avg_daily_kwh']:,.0f} kWh/day")
    ax.set_title("Average Day Shape per Profile", fontweight="bold")
    ax.set_xlabel("Hour of Day")
    ax.set_ylabel("kWh per hour")
    ax.set_xticks(range(24))
    # Below the chart, so it never covers the lines.
    ax.legend(fontsize=8, loc="upper left", bbox_to_anchor=(0, -0.2), frameon=False)
    _style(ax)

    # One marker per day, coloured by profile, so runs and odd days stand out.
    strip = fig.add_axes([0.1, 0.43, 0.8, 0.04])
    for item in a.day_profiles["assignments"]:
        strip.scatter(date.fromisoformat(item["date"]), 0, marker="X" if item["unusual"] else "s",
                      s=70, color="#333333" if item["unusual"] else colors[item["profile"]])
    strip.set_yticks([])
    strip.set_title("Profile by date (X = unusual day)", fontsize=9, loc="left")
    strip.spines[["top", "right", "left"]].set_visible(False)
    strip.xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=8))
    strip.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    strip.tick_params(axis="x", labelsize=8)

    table_ax = fig.add_axes([0.1, 0.05, 0.8, 0.30])
    if unusual:
        rows = [
            [
                f"{d['date']} {d['day']}",
                d["reason"],
                f"{d['total_kwh']:,.0f}",
                "n/a" if d["diff_pct"] is None else f"{d['diff_pct']:+.0f}% vs {d['compared_to']}",
                d["main_difference"],
            ]
            for d in unusual[:MAX_TABLE_ROWS]
        ]
        _table(table_ax, ["Date", "Why", "kWh", "Day total", "Largest difference"], rows,
               [0.17, 0.33, 0.09, 0.15, 0.26])
        table_ax.set_title(f"Unusual days ({len(unusual)})", fontweight="bold", loc="left")
    else:
        table_ax.axis("off")
        table_ax.text(0, 0.9, "No unusual days: every day fits one of the profiles above.",
                      fontsize=10)
    return fig


def _events_page(a: Analysis) -> Figure:
    m = a.metrics
    fig = Figure(figsize=PAGE_SIZE)
    fig.text(0.1, 0.95, "ANOMALY EVENTS", fontsize=14, fontweight="bold")

    worst = a.events[0]
    start = datetime.fromisoformat(worst["start"])
    intro = (
        f"{len(a.events)} event(s): runs of readings well away from what is typical for that "
        f"{m['anomaly_basis']}. High events total {m['anomaly_excess_kwh']:,.0f} kWh above "
        f"expected ({m['anomaly_excess_cost']:,.2f}). Largest: {start:%d %b %H:%M}, "
        f"{_duration(worst['duration_minutes'])}, {worst['excess_kwh']:+,.0f} kWh."
    )
    fig.text(0.1, 0.92, textwrap.fill(intro, 105), fontsize=9, verticalalignment="top")

    rows = [
        [
            f"{datetime.fromisoformat(e['start']):%Y-%m-%d %H:%M}",
            _duration(e["duration_minutes"]),
            e["direction"].capitalize(),
            f"{e['peak_kwh']:,.1f}",
            f"{e['expected_kwh']:,.1f}",
            f"{e['actual_kwh']:,.1f}",
            f"{e['excess_kwh']:+,.1f}",
            f"{e['cost']:+,.2f}",
        ]
        for e in a.events[:25]
    ]
    ax = fig.add_axes([0.1, 0.08, 0.8, 0.76])
    _table(ax, ["Start", "Duration", "Type", "Peak kWh", "Expected kWh", "Actual kWh",
                "Excess kWh", "Cost"], rows, [0.2, 0.13, 0.08, 0.11, 0.14, 0.12, 0.12, 0.1])
    if len(a.events) > len(rows):
        fig.text(0.1, 0.05, f"Showing the {len(rows)} largest of {len(a.events)} events.",
                 fontsize=8)
    return fig


def build_pdf(analysis: Analysis) -> bytes:
    pages = [_summary_page, _trend_page, _heatmap_page]
    if analysis.day_profiles:
        pages.append(_profiles_page)
    if analysis.events:
        pages.append(_events_page)

    buffer = io.BytesIO()
    with PdfPages(buffer) as pdf:
        for page in pages:
            pdf.savefig(page(analysis), dpi=150)
    return buffer.getvalue()
