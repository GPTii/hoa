"""Machine Learning hỗ trợ phân tích (đề cương mục 4.9).

1. Phân cụm (K-Means) các đơn vị theo vector 7 điểm trụ cột → nhận diện nhóm đơn vị có đặc điểm
   chuyển đổi số tương đồng (để hoạch định chính sách theo nhóm thay vì từng đơn vị).
2. Dự báo xu hướng: hồi quy tuyến tính DTI theo thời gian cho từng đơn vị → dự báo kỳ kế tiếp.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from ..models import DTIScore, Period, Pillar, PillarScore, UnitCluster

CLUSTER_NAMES = ["Nhóm dẫn đầu", "Nhóm phát triển khá", "Nhóm trung bình – cần hỗ trợ", "Nhóm yếu – ưu tiên cao",
                 "Nhóm 5", "Nhóm 6"]


def run_clustering(db: Session, period: Period, k: int = 4) -> dict:
    pillars = list(db.scalars(select(Pillar).order_by(Pillar.sort_order)))
    df = pd.DataFrame(db.execute(select(PillarScore.unit_id, PillarScore.pillar_id, PillarScore.score)
                                 .where(PillarScore.period_id == period.id)).all(),
                      columns=["unit_id", "pillar_id", "score"])
    if df.empty:
        return {"error": "Chưa có dữ liệu điểm trụ cột cho kỳ này"}
    X = df.pivot(index="unit_id", columns="pillar_id", values="score").fillna(0)
    X = X[[p.id for p in pillars if p.id in X.columns]]
    k = max(2, min(k, len(X) - 1))
    Xs = StandardScaler().fit_transform(X.values)
    km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(Xs)
    sil = float(silhouette_score(Xs, km.labels_)) if len(X) > k else None

    # đặt tên cụm theo điểm trung bình của tâm cụm (cao → thấp)
    X = X.assign(cluster=km.labels_)
    means = X.groupby("cluster").mean().mean(axis=1).sort_values(ascending=False)
    names = {c: CLUSTER_NAMES[i] for i, c in enumerate(means.index)}
    order = {c: i for i, c in enumerate(means.index)}

    # dự báo xu hướng
    hist = pd.DataFrame(db.execute(select(DTIScore.unit_id, Period.start_date, DTIScore.score)
                                   .join(Period, Period.id == DTIScore.period_id)
                                   .where(Period.start_date <= period.start_date)).all(),
                        columns=["unit_id", "start", "score"]).sort_values("start")
    forecasts = {}
    for uid, g in hist.groupby("unit_id"):
        y = g.score.values
        if len(y) >= 3:
            x = np.arange(len(y))
            slope, intercept = np.polyfit(x, y, 1)
            forecasts[uid] = (float(np.clip(slope * len(y) + intercept, 0, 100)), float(slope))
        else:
            forecasts[uid] = (float(y[-1]), 0.0)

    db.execute(delete(UnitCluster).where(UnitCluster.period_id == period.id))
    rows = [{"unit_id": int(uid), "period_id": period.id, "cluster": order[int(c)], "cluster_label": names[int(c)],
             "forecast_next": round(forecasts.get(uid, (None, None))[0], 2) if uid in forecasts else None,
             "trend_slope": round(forecasts[uid][1], 3) if uid in forecasts else None}
            for uid, c in zip(X.index, X.cluster)]
    db.execute(pg_insert(UnitCluster), rows)
    db.commit()

    centroids = X.groupby("cluster").mean()
    profile = []
    for c in means.index:
        profile.append({
            "cluster": order[int(c)], "label": names[int(c)], "size": int((X.cluster == c).sum()),
            "pillars": {p.code: round(float(centroids.loc[c, p.id]), 1) for p in pillars if p.id in centroids.columns},
        })
    return {"period": period.code, "k": k, "silhouette": round(sil, 3) if sil is not None else None,
            "clusters": sorted(profile, key=lambda x: x["cluster"])}



def evaluate(db: Session, period: Period) -> dict:
    """Đánh giá mô hình (đề cương 4.9):
    - Phân cụm: silhouette và inertia (elbow) với k = 2..6 → căn cứ chọn số cụm.
    - Dự báo: backtest – dùng các kỳ trước để dự báo kỳ đang xét, so với thực tế; so sánh với mô hình cơ sở
      'giữ nguyên kỳ trước' (naive). MAE, RMSE, MAPE."""
    pillars = list(db.scalars(select(Pillar).order_by(Pillar.sort_order)))
    df = pd.DataFrame(db.execute(select(PillarScore.unit_id, PillarScore.pillar_id, PillarScore.score)
                                 .where(PillarScore.period_id == period.id)).all(), columns=["unit_id", "pillar_id", "score"])
    out = {"period": period.code, "clustering": [], "forecast": None}
    if not df.empty:
        X = df.pivot(index="unit_id", columns="pillar_id", values="score").fillna(0)
        Xs = StandardScaler().fit_transform(X.values)
        for k in range(2, 7):
            if k >= len(X):
                break
            km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(Xs)
            out["clustering"].append({"k": k, "silhouette": round(float(silhouette_score(Xs, km.labels_)), 3),
                                      "inertia": round(float(km.inertia_), 1)})
        if out["clustering"]:
            out["best_k"] = max(out["clustering"], key=lambda x: x["silhouette"])["k"]
    hist = pd.DataFrame(db.execute(select(DTIScore.unit_id, Period.start_date, DTIScore.score)
                                   .join(Period, Period.id == DTIScore.period_id)
                                   .where(Period.start_date <= period.start_date)).all(), columns=["unit_id", "start", "score"]).sort_values("start")
    err_lr, err_nv, actual = [], [], []
    for _, g in hist.groupby("unit_id"):
        y = g.score.values
        if len(y) < 4:
            continue
        train, target = y[:-1], y[-1]
        slope, intercept = np.polyfit(np.arange(len(train)), train, 1)
        pred = float(np.clip(slope * len(train) + intercept, 0, 100))
        err_lr.append(pred - target)
        err_nv.append(train[-1] - target)
        actual.append(target)
    if err_lr:
        e1, e2, a = np.array(err_lr), np.array(err_nv), np.array(actual)
        m = lambda e: {"mae": round(float(np.abs(e).mean()), 2), "rmse": round(float(np.sqrt((e ** 2).mean())), 2),  # noqa: E731
                       "mape": round(float((np.abs(e) / np.maximum(a, 1)).mean() * 100), 2)}
        out["forecast"] = {"units": len(e1), "linear": m(e1), "naive": m(e2),
                           "improvement_pct": round(float((1 - np.abs(e1).mean() / max(np.abs(e2).mean(), 1e-9)) * 100), 1)}
    return out
