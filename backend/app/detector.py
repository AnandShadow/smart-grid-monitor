"""
Anomaly Detection Pipeline for Smart Grid Cyber Security
---------------------------------------------------------
Uses an Isolation Forest to learn the distribution of *normal* smart-meter
telemetry and flag outliers that may indicate:
  • DDoS attacks  (abnormal request_rate spikes)
  • Data injection (voltage / current / frequency out of learned range)

The model is intentionally lightweight so it can retrain on fresh synthetic
data every time the backend boots — ideal for a hackathon demo.
"""

import os
import pickle
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "ml")
MODEL_PATH = os.path.join(MODEL_DIR, "trained_model.pkl")

# Feature order must be consistent between training and inference
FEATURE_NAMES = ["voltage", "current", "power_factor", "frequency", "request_rate"]


def _generate_training_data(n_samples: int = 2000, seed: int = 42) -> np.ndarray:
    """Synthesize realistic *normal* smart-meter readings for training.

    Ranges mirror a 230 V / 50 Hz residential grid.
    """
    rng = np.random.default_rng(seed)
    data = np.column_stack(
        [
            rng.normal(loc=230.0, scale=3.0, size=n_samples),   # voltage
            rng.normal(loc=15.0, scale=2.0, size=n_samples),    # current
            rng.uniform(low=0.85, high=1.0, size=n_samples),    # power_factor
            rng.normal(loc=50.0, scale=0.05, size=n_samples),   # frequency
            rng.exponential(scale=1.0, size=n_samples),         # request_rate
        ]
    )
    return data


class AnomalyDetector:
    """Wraps an Isolation Forest with scaler for smart-grid anomaly detection."""

    def __init__(self) -> None:
        self.scaler: StandardScaler = StandardScaler()
        self.model: IsolationForest = IsolationForest(
            n_estimators=150,
            contamination=0.05,   # expect ~5 % anomalies
            random_state=42,
            n_jobs=-1,
        )
        self._is_fitted: bool = False

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------
    def train(self, data: np.ndarray | None = None) -> dict:
        """Train (or retrain) on the given data, or generate synthetic data."""
        if data is None:
            data = _generate_training_data()

        X_scaled = self.scaler.fit_transform(data)
        self.model.fit(X_scaled)
        self._is_fitted = True

        # Persist for optional reuse across restarts
        os.makedirs(MODEL_DIR, exist_ok=True)
        with open(MODEL_PATH, "wb") as f:
            pickle.dump({"scaler": self.scaler, "model": self.model}, f)

        return {
            "status": "trained",
            "samples": len(data),
            "features": FEATURE_NAMES,
        }

    def load(self) -> bool:
        """Load a previously-persisted model from disk."""
        if not os.path.exists(MODEL_PATH):
            return False
        with open(MODEL_PATH, "rb") as f:
            artefacts = pickle.load(f)
        self.scaler = artefacts["scaler"]
        self.model = artefacts["model"]
        self._is_fitted = True
        return True

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------
    def predict(self, features: dict) -> dict:
        """Classify a single meter reading.

        Parameters
        ----------
        features : dict
            Must contain keys matching ``FEATURE_NAMES``.

        Returns
        -------
        dict with ``prediction`` ('normal' | 'anomaly'), ``anomaly_score``,
        and ``threat_type``.
        """
        if not self._is_fitted:
            raise RuntimeError("Model is not trained — call train() first.")

        x = np.array([[features[f] for f in FEATURE_NAMES]])
        x_scaled = self.scaler.transform(x)

        raw_score: float = float(self.model.decision_function(x_scaled)[0])
        label: int = int(self.model.predict(x_scaled)[0])  # 1 = normal, -1 = anomaly

        prediction = "normal" if label == 1 else "anomaly"
        threat_type = None
        if prediction == "anomaly":
            threat_type = self._classify_threat(features)

        return {
            "prediction": prediction,
            "anomaly_score": round(raw_score, 4),
            "threat_type": threat_type,
        }

    @staticmethod
    def _classify_threat(features: dict) -> str:
        """Rule-based heuristic to label the *kind* of suspected attack."""
        if features["request_rate"] > 10:
            return "DDoS / flooding"
        if features["voltage"] > 260 or features["voltage"] < 190:
            return "data injection (voltage)"
        if features["frequency"] > 51 or features["frequency"] < 49:
            return "data injection (frequency)"
        if features["current"] > 30:
            return "data injection (current)"
        return "unknown anomaly"

    @property
    def is_ready(self) -> bool:
        return self._is_fitted
