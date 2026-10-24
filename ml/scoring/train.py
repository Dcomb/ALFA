import json
import sys
from pathlib import Path

import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.policy import POLICY
from app.scoring.features import features

VERSION = "logreg-v1"
DATA = ROOT / "data" / "applications.csv"
OUT = ROOT / "backend" / "app" / "scoring" / "model.json"


def load(path):
    df = pd.read_csv(path, dtype={"inn": str})
    X = pd.DataFrame([features(row) for row in df.to_dict("records")]).astype(float)
    return X, df["default_12m"].to_numpy()


def report(y, p):
    metrics = {
        "roc_auc": round(float(roc_auc_score(y, p)), 4),
        "pr_auc": round(float(average_precision_score(y, p)), 4),
        "brier": round(float(brier_score_loss(y, p)), 4),
        "mean_pd": round(float(p.mean()), 4),
        "default_rate": round(float(y.mean()), 4),
    }
    print(metrics)

    print("\nкалибровка по децилям предсказанной PD")
    bins = pd.qcut(p, 10, duplicates="drop")
    table = pd.DataFrame({"pd": p, "y": y}).groupby(bins, observed=True).agg(
        predicted=("pd", "mean"), actual=("y", "mean"), n=("y", "size"))
    print(table.round(4).to_string(index=False))

    print("\nклассы риска")
    bounds = POLICY.risk_classes
    for cls, low, high in [("A", 0, bounds.A), ("B", bounds.A, bounds.B), ("C", bounds.B, bounds.C), ("D", bounds.C, 1.01)]:
        mask = (p >= low) & (p < high)
        print(f"{cls}: доля {mask.mean():.1%}, дефолтов {y[mask].mean():.1%}")
    return metrics


def export(model, columns, metrics, n_train):
    imputer, scaler, lr = model.named_steps.values()
    payload = {
        "version": VERSION,
        "intercept": round(float(lr.intercept_[0]), 6),
        "features": [
            {"name": name, "median": round(float(median), 6), "mean": round(float(mean), 6),
             "std": round(float(std), 6), "coef": round(float(coef), 6)}
            for name, median, mean, std, coef in zip(
                columns, imputer.statistics_, scaler.mean_, scaler.scale_, lr.coef_[0])
        ],
        "n_train": n_train,
        "test_metrics": metrics,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\r\n")


def main(path=DATA):
    X, y = load(path)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)
    model = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
        ("lr", LogisticRegression(max_iter=2000)),
    ]).fit(X_train, y_train)

    metrics = report(y_test, model.predict_proba(X_test)[:, 1])
    export(model, list(X.columns), metrics, len(X_train))

    print("\nкоэффициенты на стандартизованных признаках")
    print(pd.Series(model.named_steps["lr"].coef_[0], index=X.columns).sort_values().round(3).to_string())
    print(f"\nмодель сохранена: {OUT}")


if __name__ == "__main__":
    main(*sys.argv[1:])
