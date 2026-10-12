"""Typical-day profiles: cluster days by their 24-hour load shape.

Plain numpy k-means, to keep scikit-learn out of the serverless bundle.
"""

import numpy as np
import pandas as pd

MIN_DAYS = 7
MAX_PROFILES = 4
# Below this silhouette score the days are treated as one profile rather than
# split into groups that are not really distinct.
MIN_SILHOUETTE = 0.25
UNUSUAL_Z = 3.5
# An unusual day must also differ from its profile by this share of the
# profile's own size, so near-identical days are not flagged over trivia.
UNUSUAL_MIN_SHARE = 0.15
# A profile made up of at least this share of weekdays (or weekends) is
# treated as that day type's pattern.
DAY_TYPE_SHARE = 0.8

DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _distances(x, centroids):
    return np.linalg.norm(x[:, None, :] - centroids[None, :, :], axis=2)


def _kmeans(x, k, rng, n_init=5, max_iter=50):
    best = None
    for _ in range(n_init):
        # k-means++ seeding
        centroids = [x[rng.integers(len(x))]]
        for _ in range(k - 1):
            d2 = _distances(x, np.array(centroids)).min(axis=1) ** 2
            total = d2.sum()
            pick = rng.choice(len(x), p=d2 / total) if total > 0 else rng.integers(len(x))
            centroids.append(x[pick])
        centroids = np.array(centroids)

        for _ in range(max_iter):
            labels = _distances(x, centroids).argmin(axis=1)
            updated = np.array(
                [x[labels == j].mean(axis=0) if (labels == j).any() else centroids[j] for j in range(k)]
            )
            if np.allclose(updated, centroids):
                break
            centroids = updated

        labels = _distances(x, centroids).argmin(axis=1)
        inertia = ((x - centroids[labels]) ** 2).sum()
        if best is None or inertia < best[0]:
            best = (inertia, labels, centroids)
    return best[1], best[2]


def _silhouette(x, labels):
    pairwise = np.linalg.norm(x[:, None, :] - x[None, :, :], axis=2)
    clusters = np.unique(labels)
    scores = np.zeros(len(x))
    for i in range(len(x)):
        own = labels == labels[i]
        if own.sum() < 2:
            continue
        a = pairwise[i, own].sum() / (own.sum() - 1)
        b = min(pairwise[i, labels == c].mean() for c in clusters if c != labels[i])
        scores[i] = (b - a) / max(a, b) if max(a, b) > 0 else 0
    return scores.mean()


def _fit(x):
    """Pick the number of profiles by silhouette score; one profile if none is distinct."""
    rng = np.random.default_rng(0)
    best = (MIN_SILHOUETTE, np.zeros(len(x), dtype=int), x.mean(axis=0, keepdims=True))
    for k in range(2, min(MAX_PROFILES, len(x) // 3) + 1):
        labels, centroids = _kmeans(x, k, rng)
        if len(np.unique(labels)) < k:
            continue
        score = _silhouette(x, labels)
        if score > best[0]:
            best = (score, labels, centroids)
    return best[1], best[2]


def _outliers(x, labels, centroids):
    """Days much further from their profile than days normally are."""
    distance = np.linalg.norm(x - centroids[labels], axis=1)
    median = np.median(distance)
    spread = max(1.4826 * np.median(np.abs(distance - median)), 0.1 * median, 1e-9)
    size = np.linalg.norm(centroids[labels], axis=1)
    return (distance > median + UNUSUAL_Z * spread) & (distance > UNUSUAL_MIN_SHARE * size)


def _main_difference(day, typical):
    """Describe the block of hours where a day departs most from the typical profile."""
    diff = day - typical
    peak = int(np.abs(diff).argmax())
    if diff[peak] == 0:
        return "no clear difference"
    inside = (np.sign(diff) == np.sign(diff[peak])) & (np.abs(diff) >= np.abs(diff[peak]) / 2)
    start = end = peak
    while start > 0 and inside[start - 1]:
        start -= 1
    while end < 23 and inside[end + 1]:
        end += 1
    amount = diff[start : end + 1].sum()
    return f"{start:02d}:00-{end + 1:02d}:00 ({amount:+,.0f} kWh)"


def day_profiles(df: pd.DataFrame, complete_dates, interval_minutes: float):
    """Cluster complete days into typical profiles and list the days that don't fit.

    Returns None when the data is too coarse or too short to profile.
    """
    if interval_minutes > 60:
        return None

    dates = df["datetime"].dt.date
    matrix = (
        df[dates.isin(set(complete_dates))]
        .pivot_table(index=dates, columns="hour", values="consumption", aggfunc="sum")
        .reindex(columns=range(24))
    )
    matrix = matrix.fillna(matrix.median()).fillna(0)
    if len(matrix) < MIN_DAYS:
        return None

    x = matrix.to_numpy(dtype=float)
    day_index = pd.to_datetime(pd.Index(matrix.index))
    weekday = np.asarray(day_index.dayofweek)
    is_weekend = weekday >= 5

    # Fit, set aside the days that don't fit, then refit on the rest so the
    # typical profiles are not distorted by the odd days.
    labels, centroids = _fit(x)
    odd = _outliers(x, labels, centroids) | (np.bincount(labels)[labels] < 2)
    if odd.any() and (~odd).sum() >= MIN_DAYS:
        _, centroids = _fit(x[~odd])
        labels = _distances(x, centroids).argmin(axis=1)
        odd = _outliers(x, labels, centroids)

    # A profile needs at least two ordinary days behind it.
    members = np.array([((labels == j) & ~odd).sum() for j in range(len(centroids))])
    keep = np.flatnonzero(members >= 2)
    if len(keep) == 0:
        return None
    keep = keep[np.argsort(-members[keep])]  # largest profile first
    centroids = np.array([x[(labels == j) & ~odd].mean(axis=0) for j in keep])
    nearest = _distances(x, centroids).argmin(axis=1)
    remap = {old: new for new, old in enumerate(keep)}
    in_dropped = np.array([label not in remap for label in labels])
    odd = odd | in_dropped
    labels = np.where(in_dropped, nearest, [remap.get(label, 0) for label in labels])

    profiles = []
    day_type = []  # "weekday", "weekend" or None per profile
    for j, centroid in enumerate(centroids):
        normal = (labels == j) & ~odd
        weekday_share = (~is_weekend[normal]).mean()
        if weekday_share >= DAY_TYPE_SHARE:
            kind, description = "weekday", "mostly weekdays"
        elif weekday_share <= 1 - DAY_TYPE_SHARE:
            kind, description = "weekend", "mostly weekends"
        else:
            kind, description = None, "weekdays and weekends"
        day_type.append(kind)
        counts = np.bincount(weekday[normal], minlength=7)
        profiles.append(
            {
                "label": "ABCD"[j],
                "days": int(normal.sum()),
                "description": description,
                "day_counts": {DAY_LABELS[d]: int(c) for d, c in enumerate(counts) if c},
                "avg_daily_kwh": round(float(centroid.sum()), 2),
                "peak_hour": int(centroid.argmax()),
                "hourly_kwh": [round(float(v), 3) for v in centroid],
            }
        )

    unusual_days = []
    for i in range(len(x)):
        own_type = "weekend" if is_weekend[i] else "weekday"
        profile_type = day_type[labels[i]]
        mismatch = profile_type is not None and profile_type != own_type
        if not (odd[i] or mismatch):
            continue

        # Compare against what this kind of day normally looks like.
        same_type = [j for j, kind in enumerate(day_type) if kind == own_type]
        reference = same_type[0] if mismatch and same_type else labels[i]
        if odd[i]:
            reason = "Unlike any typical profile"
        else:
            reason = f"{own_type.capitalize()} that ran like a {profile_type}"

        typical = centroids[reference]
        total, typical_total = x[i].sum(), typical.sum()
        unusual_days.append(
            {
                "date": day_index[i].date().isoformat(),
                "day": DAY_LABELS[weekday[i]],
                "reason": reason,
                "compared_to": profiles[reference]["label"],
                "total_kwh": round(float(total), 2),
                "typical_kwh": round(float(typical_total), 2),
                "diff_pct": round(float((total - typical_total) / typical_total * 100), 1)
                if typical_total > 0
                else None,
                "main_difference": _main_difference(x[i], typical),
                "hourly_kwh": [round(float(v), 3) for v in x[i]],
            }
        )

    unusual_dates = {d["date"] for d in unusual_days}
    assignments = [
        {
            "date": day_index[i].date().isoformat(),
            "profile": profiles[labels[i]]["label"],
            "unusual": day_index[i].date().isoformat() in unusual_dates,
        }
        for i in range(len(x))
    ]
    return {"profiles": profiles, "unusual_days": unusual_days, "assignments": assignments}
