import io

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from analytics import AnalysisError, analyze, build_pdf, read_table
from api.analyze import MAX_FILE_BYTES, app

client = TestClient(app)


def make_frame(days=28, freq="15min", start="2026-06-01"):
    """Office-style load: 20 kWh in weekday working hours, 5 kWh otherwise."""
    index = pd.date_range(start, periods=int(days * pd.Timedelta(days=1) / pd.Timedelta(freq)), freq=freq)
    occupied = (index.dayofweek < 5) & (index.hour >= 8) & (index.hour < 18)
    noise = np.random.default_rng(0).normal(0, 0.2, len(index))
    return pd.DataFrame({"datetime": index, "consumption": np.where(occupied, 20.0, 5.0) + noise})


def to_csv(df, date_format="%Y-%m-%d %H:%M", header=("Timestamp", "Consumption (kWh)"), preamble=""):
    out = df.copy()
    out["datetime"] = out["datetime"].dt.strftime(date_format)
    out.columns = list(header)
    return (preamble + out.to_csv(index=False)).encode()


def run(df, **kwargs):
    return analyze(df, tariff=kwargs.get("tariff", 0.2), emission_factor=kwargs.get("emission_factor", 0.4))


# --- reading -----------------------------------------------------------------
@pytest.mark.parametrize("date_format", ["%d/%m/%Y %H:%M", "%m/%d/%Y %H:%M", "%Y-%m-%d %H:%M"])
def test_date_formats_parse_without_losing_rows(date_format):
    df = make_frame()
    result = run(read_table(to_csv(df, date_format), "meter.csv"))

    assert result.quality["rows_used"] == len(df)
    assert result.quality["unreadable_dates"] == 0
    assert result.metrics["period_start"] == "2026-06-01T00:00:00"
    assert result.metrics["period_end"] == "2026-06-28T23:45:00"


def test_header_found_below_title_rows_and_by_kwh_name():
    csv_bytes = to_csv(make_frame(), header=("Reading Time", "kWh"), preamble="Site Export\nMeter 42,,\n")
    raw = read_table(csv_bytes, "meter.csv")
    assert len(raw) == len(make_frame())


def test_xlsx_with_header_on_second_row():
    df = make_frame(days=7, freq="1h")
    buffer = io.BytesIO()
    df.rename(columns={"datetime": "Date", "consumption": "Consumption"}).to_excel(
        buffer, index=False, startrow=1
    )
    result = run(read_table(buffer.getvalue(), "meter.xlsx"))
    assert result.quality["rows_used"] == len(df)


def test_original_cmms_layout_title_row_then_header_on_second_row():
    """The layout the first version was built for: xlsx, title row, header on row 2,
    a date-like column and a "Consumption" column among others."""
    df = make_frame(days=7, freq="30min")
    sheet = pd.DataFrame(
        {
            "Meter": "MTR-01",
            "Reading Date": df["datetime"],
            "Consumption": df["consumption"],
            "Unit": "kWh",
        }
    )
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer) as writer:
        sheet.to_excel(writer, index=False, startrow=1)
        # A title row that itself mentions both keywords in separate cells.
        writer.sheets["Sheet1"]["A1"] = "Utility Consumption Report"
        writer.sheets["Sheet1"]["B1"] = "Export Date: 01/07/2026"
    content = buffer.getvalue()

    # What the first version did: header fixed on the second row.
    legacy = pd.read_excel(io.BytesIO(content), header=1)
    result = run(read_table(content, "export.xlsx"))

    assert result.quality["rows_used"] == len(legacy) == len(df)
    assert result.metrics["total_kwh"] == pytest.approx(legacy["Consumption"].sum(), abs=0.01)
    assert result.metrics["period_start"] == legacy["Reading Date"].min().isoformat()


def test_original_csv_layout_header_on_first_row():
    df = make_frame(days=7, freq="1h")
    result = run(read_table(to_csv(df, header=("Date", "Consumption")), "export.csv"))
    assert result.quality["rows_used"] == len(df)
    assert result.metrics["total_kwh"] == pytest.approx(df["consumption"].sum(), abs=0.01)


def test_missing_columns_error_names_what_was_found():
    with pytest.raises(AnalysisError, match="Reading, Value"):
        read_table(b"Reading,Value\n1,2\n", "meter.csv")


@pytest.mark.parametrize("name, content", [("meter.xls", b"x"), ("meter.csv", b""), ("meter.xlsx", b"not a workbook")])
def test_unreadable_files_raise_analysis_error(name, content):
    with pytest.raises(AnalysisError):
        read_table(content, name)


def test_no_usable_rows_raises():
    with pytest.raises(AnalysisError, match="No usable readings"):
        run(read_table(b"Date,Consumption\nfoo,bar\n", "meter.csv"))


# --- cleaning & metrics ------------------------------------------------------
def test_totals_cost_and_carbon():
    df = make_frame()
    result = run(df, tariff=0.3, emission_factor=0.5)
    total = df["consumption"].sum()

    assert result.metrics["total_kwh"] == pytest.approx(total, abs=0.01)
    assert result.metrics["est_cost"] == pytest.approx(total * 0.3, abs=0.01)
    assert result.metrics["est_co2_kg"] == pytest.approx(total * 0.5, abs=0.01)


def test_bad_rows_are_excluded_and_counted():
    df = make_frame().astype({"datetime": "object", "consumption": "object"})
    df.loc[10, "consumption"] = -5
    df.loc[11, "consumption"] = "n/a"
    df.loc[12, "datetime"] = "not a date"
    df = pd.concat([df, df.iloc[[20]]])

    result = run(df)
    q = result.quality
    assert (q["negative_readings"], q["non_numeric_values"], q["unreadable_dates"], q["duplicate_timestamps"]) == (1, 1, 1, 1)
    assert q["rows_used"] == q["rows_read"] - 4
    assert result.df["consumption"].min() >= 0


def test_gaps_are_reported():
    df = make_frame().drop(index=range(100, 108))
    q = run(df).quality
    assert q["interval_minutes"] == 15
    assert q["missing_intervals"] == 8
    assert q["gaps"] == 1
    assert q["longest_gap_hours"] == 2.25


def test_base_load_ignores_a_single_low_glitch():
    df = make_frame()
    df.loc[50, "consumption"] = 0.01
    assert run(df).metrics["base_load_kwh"] == pytest.approx(5, abs=0.5)


def test_anomalies_use_time_of_week_baseline():
    df = make_frame()
    night = df.index[(df["datetime"].dt.hour == 3) & (df["datetime"].dt.dayofweek == 2)][0]
    midday = df.index[(df["datetime"].dt.hour == 12) & (df["datetime"].dt.dayofweek == 2)][0]
    df.loc[night, "consumption"] = 15.0  # below the daytime norm, but far too high for 3 a.m.
    df.loc[midday, "consumption"] = 2.0  # abnormally low for midday

    result = run(df)
    assert result.df.loc[result.df["datetime"] == df.loc[night, "datetime"], "anomaly"].item() == 1
    assert result.df.loc[result.df["datetime"] == df.loc[midday, "datetime"], "anomaly"].item() == -1
    assert result.metrics["anomalies_high"] + result.metrics["anomalies_low"] < 20
    assert result.metrics["anomaly_basis"] == "hour of week"


def test_busiest_cell_comes_from_the_heatmap_not_one_spike():
    df = make_frame()
    df.loc[df["datetime"] == "2026-06-07 03:00", "consumption"] = 90.0  # lone Sunday 3 a.m. spike
    df.loc[(df["datetime"].dt.dayofweek == 1) & (df["datetime"].dt.hour == 14), "consumption"] += 5

    m = run(df).metrics
    assert m["peak_at"] == "2026-06-07T03:00:00"
    assert (m["busiest_day"], m["busiest_hour"]) == ("Tuesday", 14)


def test_weekday_only_data_still_produces_a_report():
    df = make_frame(days=5)  # Monday to Friday
    result = run(df)

    assert result.metrics["weekday_vs_weekend_pct"] is None
    assert result.heatmap.shape == (7, 24)
    assert build_pdf(result).startswith(b"%PDF")


def test_partial_days_left_out_of_daily_trend():
    df = make_frame(days=10).iloc[40:-40]
    daily = run(df).daily
    assert len(daily) == 8
    assert daily["complete"].all()


# --- API ---------------------------------------------------------------------
def post(content, name="meter.csv", **data):
    return client.post("/api/analyze", files={"file": (name, content)}, data=data)


def test_api_returns_metrics_and_pdf():
    response = post(to_csv(make_frame()), tariff="0.3", emission_factor="0.5")
    body = response.json()

    assert response.status_code == 200
    assert body["metrics"]["tariff"] == 0.3
    assert body["pdf_base64"].startswith("JVBERi")  # "%PDF-"
    assert len(response.content) < 4_000_000  # stays under Vercel's response limit


def test_api_rejects_bad_input_with_400():
    response = post(b"Reading,Value\n1,2\n")
    assert response.status_code == 400
    assert "Could not find the required columns" in response.json()["detail"]


def test_api_rejects_oversized_file_with_413():
    assert post(b"x" * (MAX_FILE_BYTES + 1)).status_code == 413


def test_api_rejects_negative_tariff():
    assert post(to_csv(make_frame()), tariff="-1").status_code == 422
