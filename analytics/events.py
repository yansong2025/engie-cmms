"""Group flagged readings into anomaly events."""

import numpy as np
import pandas as pd

# Flagged readings separated by at most this many normal readings are one event.
EVENT_BRIDGE_READINGS = 1
# A lone flagged reading is only reported when it is this far out; milder
# one-off readings are treated as noise.
SINGLE_READING_Z = 6.0


def build_events(df: pd.DataFrame, interval: pd.Timedelta, tariff: float) -> tuple:
    """Return (events, kept) from a frame with datetime, consumption, expected, z, anomaly.

    events is a list of dicts, largest excess first. kept is a boolean array
    marking the flagged readings that belong to a reported event.
    """
    times = df["datetime"].to_numpy()
    actual = df["consumption"].to_numpy(dtype=float)
    expected = df["expected"].to_numpy(dtype=float)
    z = df["z"].to_numpy(dtype=float)
    flags = df["anomaly"].to_numpy()

    max_step = interval * (EVENT_BRIDGE_READINGS + 1.5)
    groups: list = []
    for pos in np.flatnonzero(flags):
        last = groups[-1][-1] if groups else None
        if last is not None and flags[last] == flags[pos] and times[pos] - times[last] <= max_step:
            groups[-1].append(pos)
        else:
            groups.append([pos])

    events = []
    kept = np.zeros(len(df), dtype=bool)
    for group in groups:
        if len(group) < 2 and abs(z[group[0]]) < SINGLE_READING_Z:
            continue
        kept[group] = True

        span = slice(group[0], group[-1] + 1)
        high = flags[group[0]] > 0
        start = pd.Timestamp(times[group[0]])
        end = pd.Timestamp(times[group[-1]]) + interval
        excess = float((actual[span] - expected[span]).sum())
        events.append(
            {
                "start": start.isoformat(),
                "end": end.isoformat(),
                "duration_minutes": round((end - start).total_seconds() / 60),
                "direction": "high" if high else "low",
                "readings": int(span.stop - span.start),
                "peak_kwh": round(float(actual[span].max() if high else actual[span].min()), 3),
                "actual_kwh": round(float(actual[span].sum()), 2),
                "expected_kwh": round(float(expected[span].sum()), 2),
                "excess_kwh": round(excess, 2),
                "cost": round(excess * tariff, 2),
            }
        )

    events.sort(key=lambda e: abs(e["excess_kwh"]), reverse=True)
    return events, kept
