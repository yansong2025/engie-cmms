"""Parsing, cleaning and metrics for interval utility data.

Everything here is pure (bytes/DataFrame in, Analysis out) so it can be tested
without the web layer.
"""

import csv
import io
import re
import warnings
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .events import build_events
from .profiles import day_profiles

DATE_KEYWORDS = ("datetime", "timestamp", "date", "time")
CONSUMPTION_KEYWORDS = ("consumption", "kwh", "usage", "energy")
HEADER_SCAN_ROWS = 20
HEADER_PROBE_ROWS = 5

BASELOAD_PERCENTILE = 5
ANOMALY_Z = 3.5
# A bucket's spread is never taken to be tighter than this share of its median,
# so flat periods don't flag trivial wobble.
ANOMALY_MIN_SPREAD = 0.10
MIN_BUCKET_SAMPLES = 8
COMPLETE_DAY_SHARE = 0.9

DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class AnalysisError(ValueError):
    """A problem with the uploaded file that the user can act on."""


@dataclass
class Analysis:
    # datetime, consumption, day_of_week, hour, is_weekend, expected, z, anomaly
    df: pd.DataFrame
    daily: pd.DataFrame  # date, consumption, complete, rolling_7d
    hourly_weekday: pd.Series  # indexed 0-23, NaN where no data
    hourly_weekend: pd.Series
    heatmap: pd.DataFrame  # 7 x 24, NaN where no data
    metrics: dict
    quality: dict
    events: list = field(default_factory=list)  # anomaly events, largest excess first
    day_profiles: dict | None = None  # None when the data is too coarse or short
    notes: list = field(default_factory=list)

    def summary(self) -> dict:
        """JSON-safe view for the API response."""
        return {
            "metrics": self.metrics,
            "quality": self.quality,
            "events": self.events,
            "day_profiles": self.day_profiles,
            "notes": self.notes,
        }


# ------------------------------------------------------------------------------
# Reading
# ------------------------------------------------------------------------------
def _read_csv_rows(file_bytes: bytes) -> pd.DataFrame:
    try:
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = file_bytes.decode("latin-1")

    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel

    # Parsed by hand because exports often carry title rows above the header
    # with a different number of fields, which pandas' parser rejects.
    rows = [row for row in csv.reader(io.StringIO(text), dialect) if any(c.strip() for c in row)]
    return pd.DataFrame(rows)


def _matches(cell, keywords) -> bool:
    return isinstance(cell, str) and any(k in cell.lower() for k in keywords)


def _pick_columns(header: list) -> tuple:
    """Return (date_idx, consumption_idx), either of which may be None."""
    consumption_idx = None
    for keyword in CONSUMPTION_KEYWORDS:  # keyword order is priority order
        consumption_idx = next(
            (i for i, c in enumerate(header) if isinstance(c, str) and keyword in c.lower()), None
        )
        if consumption_idx is not None:
            break

    date_idx = next(
        (i for i, c in enumerate(header) if i != consumption_idx and _matches(c, DATE_KEYWORDS)),
        None,
    )
    return date_idx, consumption_idx


def _has_readings(sample: pd.DataFrame) -> bool:
    """True if any row holds both a parseable date and a number."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        dates = pd.to_datetime(sample["datetime"].astype("string"), errors="coerce")
    values = pd.to_numeric(
        sample["consumption"].astype("string").str.replace(",", "", regex=False), errors="coerce"
    )
    return bool((dates.notna() & values.notna()).any())


def read_table(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """Load a CSV/XLSX export and return a raw two-column frame: datetime, consumption."""
    name = (filename or "").lower()
    if not file_bytes:
        raise AnalysisError("The file is empty.")

    try:
        if name.endswith(".csv"):
            raw = _read_csv_rows(file_bytes)
        elif name.endswith(".xlsx"):
            raw = pd.read_excel(io.BytesIO(file_bytes), header=None, engine="openpyxl")
            raw = raw.dropna(how="all").reset_index(drop=True)
        else:
            raise AnalysisError("Unsupported file type. Please upload a .csv or .xlsx file.")
    except AnalysisError:
        raise
    except Exception as exc:
        raise AnalysisError(
            "The file could not be read. Check that it is a valid CSV or XLSX file."
        ) from exc

    if raw.empty:
        raise AnalysisError("The file contains no rows.")

    # The header is the first row naming both a date and a consumption column
    # that is followed by actual readings. Checking for readings stops a title
    # row such as "Consumption Report | Export Date: ..." being taken as the header.
    fallback = None
    for row_idx in range(min(HEADER_SCAN_ROWS, len(raw))):
        date_idx, consumption_idx = _pick_columns(raw.iloc[row_idx].tolist())
        if date_idx is None or consumption_idx is None:
            continue
        data = raw.iloc[row_idx + 1 :, [date_idx, consumption_idx]].copy()
        data.columns = ["datetime", "consumption"]
        data = data.reset_index(drop=True)
        if _has_readings(data.head(HEADER_PROBE_ROWS)):
            return data
        if fallback is None:
            fallback = data
    if fallback is not None:
        return fallback

    found = [str(c).strip() for c in raw.iloc[0].tolist() if pd.notna(c) and str(c).strip()]
    raise AnalysisError(
        "Could not find the required columns. The file needs a date/time column "
        f"(name containing one of: {', '.join(DATE_KEYWORDS)}) and a consumption column "
        f"(name containing one of: {', '.join(CONSUMPTION_KEYWORDS)}). "
        f"First row found: {', '.join(found[:12]) or '(blank)'}."
    )


# ------------------------------------------------------------------------------
# Cleaning
# ------------------------------------------------------------------------------
def _parse_datetimes(values: pd.Series, notes: list) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(values):
        return values

    text = values.astype("string").str.strip()
    filled = text.dropna()
    filled = filled[filled != ""]
    if filled.empty:
        return pd.to_datetime(text, errors="coerce")

    # Year-first strings are unambiguous, and dayfirst=True would misread them.
    year_first = filled.str.match(r"^\d{4}\D").mean() > 0.5
    candidates = []
    for dayfirst in (False,) if year_first else (True, False):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            parsed = pd.to_datetime(text, errors="coerce", dayfirst=dayfirst)
        if getattr(parsed.dt, "tz", None) is not None:
            parsed = parsed.dt.tz_localize(None)
        valid = parsed.dropna()
        span = (valid.max() - valid.min()) if not valid.empty else pd.Timedelta.max
        candidates.append((parsed.isna().sum(), span, dayfirst, parsed))

    # Prefer the reading that parses the most rows, then the one where the data
    # covers the shortest period: DD/MM read as MM/DD scatters days across months.
    candidates.sort(key=lambda c: (c[0], c[1]))
    best = candidates[0]
    if len(candidates) > 1 and candidates[1][:2] == best[:2]:
        notes.append(
            "Dates could be read as either DD/MM or MM/DD; DD/MM was assumed. "
            "Use YYYY-MM-DD dates to remove the ambiguity."
        )
    return best[3]


def _parse_numbers(values: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(values):
        return values.astype(float)
    text = values.astype("string").str.strip().str.replace(",", "", regex=False)
    return pd.to_numeric(text, errors="coerce")


def _clean(raw: pd.DataFrame, notes: list) -> tuple:
    total_rows = len(raw)
    df = pd.DataFrame(
        {
            "datetime": _parse_datetimes(raw["datetime"], notes),
            "consumption": _parse_numbers(raw["consumption"]),
        }
    )

    bad_dates = int(df["datetime"].isna().sum())
    bad_values = int((df["datetime"].notna() & df["consumption"].isna()).sum())
    df = df.dropna()

    negatives = int((df["consumption"] < 0).sum())
    df = df[df["consumption"] >= 0]

    duplicates = int(df["datetime"].duplicated().sum())
    df = df.drop_duplicates("datetime").sort_values("datetime").reset_index(drop=True)

    if len(df) < 2:
        raise AnalysisError(
            f"No usable readings found: of {total_rows} rows, {bad_dates} had an unreadable "
            f"date, {bad_values} a non-numeric consumption value, {negatives} a negative value."
        )

    steps = df["datetime"].diff().dropna()
    interval = steps.median()
    gaps = steps[steps > interval * 1.5]
    expected = int(round((df["datetime"].iloc[-1] - df["datetime"].iloc[0]) / interval)) + 1

    quality = {
        "rows_read": total_rows,
        "rows_used": len(df),
        "unreadable_dates": bad_dates,
        "non_numeric_values": bad_values,
        "negative_readings": negatives,
        "duplicate_timestamps": duplicates,
        "zero_readings": int((df["consumption"] == 0).sum()),
        "interval_minutes": round(interval.total_seconds() / 60, 2),
        "missing_intervals": max(expected - len(df), 0),
        "gaps": len(gaps),
        "longest_gap_hours": round(gaps.max().total_seconds() / 3600, 2) if len(gaps) else 0,
    }

    dropped = total_rows - len(df)
    if dropped:
        notes.append(
            f"{dropped} of {total_rows} rows were excluded (unreadable date, non-numeric, "
            "negative or duplicate) and are not in the totals."
        )
    if quality["missing_intervals"]:
        notes.append(
            f"{quality['missing_intervals']} expected readings are missing, so totals "
            "understate actual consumption."
        )
    return df, quality


# ------------------------------------------------------------------------------
# Metrics
# ------------------------------------------------------------------------------
def _flag_anomalies(df: pd.DataFrame) -> tuple:
    """Flag readings far from what is typical for that time of the week.

    Returns (flags, expected, z, basis): flags is +1 (high), -1 (low) or 0,
    expected is the typical reading for that time, z the robust distance from it.
    """
    by_hour_of_week = [df["day_of_week"], df["hour"]]
    by_day_type = [df["is_weekend"], df["hour"]]

    # Fall back to coarser buckets when the data is too short to give each
    # hour of the week a meaningful baseline.
    for keys, basis in ((by_hour_of_week, "hour of week"), (by_day_type, "weekday/weekend hour")):
        if df.groupby(keys)["consumption"].size().median() >= MIN_BUCKET_SAMPLES:
            grouped = df.groupby(keys)["consumption"]
            median = grouped.transform("median")
            mad = grouped.transform(lambda s: (s - s.median()).abs().median())
            break
    else:
        basis = "whole period"
        median = pd.Series(df["consumption"].median(), index=df.index)
        mad = pd.Series((df["consumption"] - median).abs().median(), index=df.index)

    floor = max(df["consumption"].median() * ANOMALY_MIN_SPREAD, 1e-9)
    spread = np.maximum(1.4826 * mad, np.maximum(median * ANOMALY_MIN_SPREAD, floor))
    z = (df["consumption"] - median) / spread
    flags = np.where(z > ANOMALY_Z, 1, np.where(z < -ANOMALY_Z, -1, 0))
    return pd.Series(flags, index=df.index), median, z, basis


def _number(value, digits=2):
    """Round to a plain float, mapping NaN/inf to None so the result is valid JSON."""
    if value is None or not np.isfinite(value):
        return None
    return round(float(value), digits)


def analyze(raw: pd.DataFrame, tariff: float, emission_factor: float) -> Analysis:
    """Compute report metrics from a raw (datetime, consumption) frame.

    tariff is cost per kWh; emission_factor is kg CO2e per kWh.
    """
    notes: list = []
    df, quality = _clean(raw, notes)

    df["day_of_week"] = df["datetime"].dt.dayofweek
    df["hour"] = df["datetime"].dt.hour
    df["is_weekend"] = df["day_of_week"] >= 5
    df["anomaly"], df["expected"], df["z"], anomaly_basis = _flag_anomalies(df)

    # Report anomalies as events; flagged readings that form no event are noise.
    interval = pd.Timedelta(minutes=quality["interval_minutes"])
    events, in_event = build_events(df, interval, tariff)
    df.loc[~in_event, "anomaly"] = 0
    high_events = [e for e in events if e["direction"] == "high"]

    consumption = df["consumption"]
    total_kwh = consumption.sum()
    avg_reading = consumption.mean()
    max_reading = consumption.max()
    peak_row = df.loc[consumption.idxmax()]
    positive = consumption[consumption > 0]

    # Daily totals; days with too few readings would look like dips in the trend.
    readings_per_day = pd.Timedelta(days=1) / interval
    by_date = df.groupby(df["datetime"].dt.date)["consumption"]
    daily = by_date.sum().rename("consumption").reset_index().rename(columns={"datetime": "date"})
    daily["complete"] = (by_date.size() >= readings_per_day * COMPLETE_DAY_SHARE).to_numpy()
    complete_dates = daily.loc[daily["complete"], "date"].tolist()
    if daily["complete"].any():
        incomplete = int((~daily["complete"]).sum())
        if incomplete:
            notes.append(f"{incomplete} partial day(s) are left out of the daily trend chart.")
        daily = daily[daily["complete"]].reset_index(drop=True)
    daily["rolling_7d"] = daily["consumption"].rolling(7, min_periods=1).mean()

    hours = range(24)
    hourly_weekday = df[~df["is_weekend"]].groupby("hour")["consumption"].mean().reindex(hours)
    hourly_weekend = df[df["is_weekend"]].groupby("hour")["consumption"].mean().reindex(hours)

    heatmap = (
        df.pivot_table(index="day_of_week", columns="hour", values="consumption", aggfunc="mean")
        .reindex(index=range(7), columns=hours)
    )
    heatmap.index = DAY_LABELS
    hot_day, hot_hour = np.unravel_index(np.nanargmax(heatmap.to_numpy()), heatmap.shape)

    weekday_mean, weekend_mean = hourly_weekday.mean(), hourly_weekend.mean()
    has_both = np.isfinite(weekday_mean) and np.isfinite(weekend_mean) and weekend_mean > 0
    weekday_vs_weekend_pct = (weekday_mean - weekend_mean) / weekend_mean * 100 if has_both else None

    metrics = {
        "period_start": df["datetime"].iloc[0].isoformat(),
        "period_end": df["datetime"].iloc[-1].isoformat(),
        "total_kwh": _number(total_kwh),
        "tariff": tariff,
        "est_cost": _number(total_kwh * tariff),
        "emission_factor": emission_factor,
        "est_co2_kg": _number(total_kwh * emission_factor),
        "avg_reading_kwh": _number(avg_reading, 3),
        "base_load_kwh": _number(
            np.percentile(positive, BASELOAD_PERCENTILE) if len(positive) else 0, 3
        ),
        "peak_kwh": _number(max_reading, 3),
        "peak_at": peak_row["datetime"].isoformat(),
        "load_factor_pct": _number(avg_reading / max_reading * 100 if max_reading > 0 else 0),
        "anomaly_events_high": len(high_events),
        "anomaly_events_low": len(events) - len(high_events),
        "anomaly_excess_kwh": _number(sum(e["excess_kwh"] for e in high_events)),
        "anomaly_excess_cost": _number(sum(e["cost"] for e in high_events)),
        "anomaly_basis": anomaly_basis,
        "weekday_vs_weekend_pct": _number(weekday_vs_weekend_pct, 1),
        "weekday_peak_hour": int(hourly_weekday.idxmax()) if hourly_weekday.notna().any() else None,
        "busiest_day": DAY_NAMES[hot_day],
        "busiest_hour": int(hot_hour),
    }

    return Analysis(
        df=df,
        daily=daily,
        hourly_weekday=hourly_weekday,
        hourly_weekend=hourly_weekend,
        heatmap=heatmap,
        metrics=metrics,
        quality=quality,
        events=events,
        day_profiles=day_profiles(df, complete_dates, quality["interval_minutes"]),
        notes=notes,
    )
