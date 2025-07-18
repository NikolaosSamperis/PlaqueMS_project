# syntax_ml_utils.py

from __future__ import annotations
from typing import Literal
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin, RegressorMixin

# ── 5-protein panel ────────────────────────────────────────────────────
PANEL = ["HRG", "CP", "C4B", "F13A1", "VCAN"]

# ── label-free stats ───────────────────────────────────────────────────
LABEL_FREE_MEAN = np.array([28.3118, 29.2769, 25.5675, 26.5596, 33.9064])
LABEL_FREE_STD  = np.array([ 1.1941,  1.2242,  1.2779,  1.1350,  1.7157])

# ── labelled stats ─────────────────────────────────────────────────────
LABELLED_MEAN   = np.array([ 6.5236, 6.2841, 6.4017,  6.4461, 6.2414])
LABELLED_STD    = np.array([ 0.7906, 0.9989, 0.9969, 0.8775, 1.0896])

# Map for easy lookup
_EXTRACT_TABLE = {
    "label_free": (LABEL_FREE_MEAN,  LABEL_FREE_STD),
    "labelled":   (LABELLED_MEAN,    LABELLED_STD),
}

# ── original β & α for label-free z-scores ─────────────────────────────
_COEF      = np.array([0.8375609, 0.5080263, 9.0445166, 2.1418158, -2.7828411])
_INTERCEPT = 11.9375


# ── Step 1: flip proteins↔samples ───────────────────────────────────────
def transpose_df(df: pd.DataFrame) -> pd.DataFrame:
    return df.T

# ── Step 2: select the five proteins ───────────────────────────────────
def select_panel(df: pd.DataFrame) -> pd.DataFrame:
    return df[PANEL]

# ── Auto-detecting z-scaler ───────────────────────────────────
class AutoScaler(BaseEstimator, TransformerMixin):
    """
    Decide extract type from the data, then apply the correct μ / σ.

    Heuristic: if the median log-intensity of HRG is > 17.35 ➜ label-free,
    otherwise labelled.
    """
    def __init__(self, threshold: float = 17.35):
        self.threshold = threshold

    def fit(self, X, y=None):
        return self

    def _detect_extract(self, X: np.ndarray) -> Literal["label_free", "labelled"]:
        med = np.nanmedian(X[:, 0])  # HRG = column 0 after select_panel()
        return "label_free" if med > self.threshold else "labelled"

    def transform(self, X):
        df_in = isinstance(X, pd.DataFrame)
        arr   = X.values if df_in else np.asarray(X)
        extract = self._detect_extract(arr)
        mean, std = _EXTRACT_TABLE[extract]
        scaled = (arr - mean) / std
        if df_in:
            return pd.DataFrame(scaled, index=X.index, columns=X.columns)
        return scaled

    def get_feature_names_out(self, input_features=None):
        return input_features if input_features is not None else PANEL


# ── Frozen linear regressor ───────
class SyntaxRegressor(BaseEstimator, RegressorMixin):
    """Non-trainable linear regressor  Syntax = intercept + β·X̂."""

    def __init__(self, coef=_COEF, intercept=_INTERCEPT):
        self.coef_ = np.asarray(coef, dtype=float)
        self.intercept_ = float(intercept)
        self.n_features_in_ = self.coef_.size  # sklearn metadata

    def fit(self, X, y=None):
        return self

    def predict(self, X):
        return X @ self.coef_ + self.intercept_
