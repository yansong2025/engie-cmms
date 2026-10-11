"""Regenerate sample-data/sample_meter_15min.csv (4 weeks of 15-minute readings)."""

import os

import numpy as np
import pandas as pd

OUTPUT = os.path.join(os.path.dirname(__file__), "..", "sample-data", "sample_meter_15min.csv")


def build() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    index = pd.date_range("2026-06-01", periods=4 * 7 * 96, freq="15min")
    hour = index.hour + index.minute / 60
    occupied = (index.dayofweek < 5) & (hour >= 7) & (hour < 19)

    load = np.where(occupied, 18 + 10 * np.sin((hour - 7) / 12 * np.pi), 6.0)
    load = load + rng.normal(0, 0.6, len(index))

    df = pd.DataFrame({"Timestamp": index, "Consumption (kWh)": load.round(2)})
    df.loc[1500, "Consumption (kWh)"] = 55.0  # spike
    df.loc[2000:2003, "Consumption (kWh)"] = 30.0  # equipment left running on a Sunday evening
    df = df.drop(index=range(900, 908))  # a two-hour gap
    return df


if __name__ == "__main__":
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    build().to_csv(OUTPUT, index=False, date_format="%Y-%m-%d %H:%M")
    print(f"Wrote {os.path.normpath(OUTPUT)}")
