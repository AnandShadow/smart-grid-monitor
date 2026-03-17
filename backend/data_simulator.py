"""
data_simulator.py — Live IoT Smart Meter Simulator with Cyber-Attack Injection
===============================================================================
Hackathon Project: Cyber Resilient Smart Energy Systems

This standalone script does four things:
  1. DATA GENERATION   — Continuously produces realistic smart-grid telemetry
                         (voltage, current, power_factor, frequency, request_rate).
  2. THREAT INJECTION  — Randomly injects two classes of simulated cyber-attacks:
                           • DDoS Simulation  (massive request_rate spikes)
                           • Data Tampering    (impossible voltage/current values)
  3. ML ANOMALY DETECTION — Trains a local Isolation Forest on a batch of normal
                         data, then scores every generated reading in real time.
  4. API POSTING       — Sends each scored payload to the FastAPI backend
                         (POST /predict) so the dashboard can visualise it.

Run:
    python data_simulator.py            (defaults to http://localhost:8000)
    python data_simulator.py --url http://192.168.1.10:8000 --interval 0.5

Dependencies:
    pip install requests scikit-learn numpy
"""

# ──────────────────────────────────────────────────────────────────────────────
# Imports
# ──────────────────────────────────────────────────────────────────────────────
import argparse
import json
import random
import sys
import time
from datetime import datetime, timezone

import numpy as np
import requests
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

# ──────────────────────────────────────────────────────────────────────────────
# Configuration constants
# ──────────────────────────────────────────────────────────────────────────────

# IDs for our virtual smart meters — each reading is tagged with one of these
METER_IDS = [f"SM-{i:03d}" for i in range(1, 11)]  # SM-001 … SM-010

# Normal operating ranges for a 230 V / 50 Hz residential grid
NORMAL_VOLTAGE_MEAN   = 230.0   # volts
NORMAL_VOLTAGE_STD    =   3.0
NORMAL_CURRENT_MEAN   =  15.0   # amperes
NORMAL_CURRENT_STD    =   2.0
NORMAL_PF_LOW         =   0.85  # power factor (unitless, 0–1)
NORMAL_PF_HIGH        =   1.0
NORMAL_FREQ_MEAN      =  50.0   # hertz
NORMAL_FREQ_STD       =   0.05
NORMAL_REQ_RATE_SCALE =   1.0   # requests/sec (exponential distribution)

# Probability that any single reading is a cyber-attack (≈15 % keeps the demo exciting)
ATTACK_PROBABILITY = 0.15

# Number of clean samples used to train the local Isolation Forest
TRAINING_SAMPLES = 1000

# ──────────────────────────────────────────────────────────────────────────────
# 1. DATA GENERATION — produce a single "normal" smart-meter reading
# ──────────────────────────────────────────────────────────────────────────────

def generate_normal_reading() -> dict:
    """
    Create one realistic, normal smart-meter reading.

    Returns a dict that matches the FastAPI MeterReading schema:
        meter_id, voltage, current, power_factor, frequency, request_rate
    """
    return {
        # Randomly pick one of our simulated meters
        "meter_id": random.choice(METER_IDS),

        # Voltage centres on 230 V with mild Gaussian noise
        "voltage": round(random.gauss(NORMAL_VOLTAGE_MEAN, NORMAL_VOLTAGE_STD), 2),

        # Current centres on 15 A with mild Gaussian noise
        "current": round(max(0.1, random.gauss(NORMAL_CURRENT_MEAN, NORMAL_CURRENT_STD)), 2),

        # Power factor is uniform between 0.85 and 1.0 (typical range)
        "power_factor": round(random.uniform(NORMAL_PF_LOW, NORMAL_PF_HIGH), 4),

        # Grid frequency stays very tight around 50 Hz
        "frequency": round(random.gauss(NORMAL_FREQ_MEAN, NORMAL_FREQ_STD), 3),

        # Normal request rate: low, exponentially distributed (most readings ≈1 req/s)
        "request_rate": round(max(0.01, random.expovariate(1.0 / NORMAL_REQ_RATE_SCALE)), 2),
    }


# ──────────────────────────────────────────────────────────────────────────────
# 2. THREAT INJECTION — randomly corrupt a reading to simulate an attack
# ──────────────────────────────────────────────────────────────────────────────

def inject_ddos(reading: dict) -> dict:
    """
    DDoS Simulation — a compromised meter floods the network with requests.

    We spike `request_rate` to 50–500× normal.  Every other field stays normal
    so the anomaly is *purely* in the traffic pattern, exactly what a real
    volumetric DDoS would look like against a smart-grid head-end.
    """
    reading = reading.copy()
    # Massive spike: normal ≈ 1 req/s → attack = 50 – 500 req/s
    reading["request_rate"] = round(random.uniform(50.0, 500.0), 2)
    return reading


def inject_data_tampering(reading: dict) -> dict:
    """
    Data Tampering — an attacker injects impossible sensor values.

    In a real SCADA/ICS environment, adversaries can MITM modbus or DNP3
    traffic and alter readings.  We simulate this by pushing voltage and/or
    current far outside their physically-possible range.
    """
    reading = reading.copy()

    # Choose which field(s) to corrupt — at least one
    tamper_voltage = random.random() < 0.7   # 70 % chance
    tamper_current = random.random() < 0.5   # 50 % chance

    if tamper_voltage:
        # Either a catastrophic drop (< 100 V) or a dangerous spike (> 300 V)
        if random.random() < 0.5:
            reading["voltage"] = round(random.uniform(20.0, 100.0), 2)   # impossible drop
        else:
            reading["voltage"] = round(random.uniform(300.0, 600.0), 2)  # impossible spike

    if tamper_current:
        # Current spikes to 5–10× normal
        reading["current"] = round(random.uniform(50.0, 150.0), 2)

    # Optionally distort frequency to simulate grid-destabilisation data
    if random.random() < 0.3:
        reading["frequency"] = round(random.uniform(45.0, 55.0), 3)

    return reading


def maybe_inject_attack(reading: dict) -> tuple[dict, str]:
    """
    With probability ATTACK_PROBABILITY, corrupt the reading.

    Returns:
        (reading, attack_label)
        attack_label is "none", "ddos", or "data_tampering"
    """
    if random.random() > ATTACK_PROBABILITY:
        # ---- No attack: return the clean reading as-is ----
        return reading, "none"

    # ---- Pick an attack type with equal probability ----
    if random.random() < 0.5:
        return inject_ddos(reading), "ddos"
    else:
        return inject_data_tampering(reading), "data_tampering"


# ──────────────────────────────────────────────────────────────────────────────
# 3. MACHINE LEARNING — local Isolation Forest for edge anomaly detection
# ──────────────────────────────────────────────────────────────────────────────

# Feature columns fed into the model (must match training and inference order)
FEATURE_KEYS = ["voltage", "current", "power_factor", "frequency", "request_rate"]


def train_local_model() -> tuple[IsolationForest, StandardScaler]:
    """
    Train an Isolation Forest on a batch of NORMAL data so it learns what
    "healthy" smart-meter readings look like.

    Why Isolation Forest?
    ---------------------
    It works by recursively partitioning data with random splits.  Normal
    points need many splits to isolate → long average path length.
    Anomalies sit in sparse regions → isolated quickly → short path length.
    This makes it ideal for unsupervised anomaly detection where we only
    have examples of normal behaviour (no labelled attacks needed).

    Returns:
        (model, scaler) — the fitted Isolation Forest and its StandardScaler.
    """
    print(f"[ML] Generating {TRAINING_SAMPLES} normal samples for training …")

    # Build a NumPy matrix of clean readings
    training_data = np.array([
        [r[k] for k in FEATURE_KEYS]
        for r in (generate_normal_reading() for _ in range(TRAINING_SAMPLES))
    ])

    # StandardScaler zero-means and unit-variances each feature so the
    # Isolation Forest treats all dimensions equally during random splits.
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(training_data)

    # Create and fit the Isolation Forest
    model = IsolationForest(
        n_estimators=150,         # 150 random trees in the ensemble
        contamination=0.05,       # expected anomaly rate ≈ 5 %
        random_state=42,          # reproducible results
        n_jobs=-1,                # use all CPU cores
    )
    model.fit(X_scaled)

    print("[ML] Isolation Forest trained and ready.\n")
    return model, scaler


def score_reading(
    reading: dict,
    model: IsolationForest,
    scaler: StandardScaler,
) -> dict:
    """
    Run a single reading through the trained Isolation Forest.

    Appends two keys to the reading dict:
        is_anomaly  : bool   — True if the model flagged it
        threat_score: float  — raw decision_function value
                               (more negative = more anomalous)
    """
    # Extract features in the same column order used during training
    x = np.array([[reading[k] for k in FEATURE_KEYS]])

    # Scale using the *same* scaler that was fit on training data
    x_scaled = scaler.transform(x)

    # decision_function returns a continuous anomaly score:
    #   positive  → likely normal
    #   negative  → likely anomaly
    raw_score = float(model.decision_function(x_scaled)[0])

    # predict returns  1 → normal,  -1 → anomaly
    label = int(model.predict(x_scaled)[0])

    reading["is_anomaly"]   = (label == -1)
    reading["threat_score"] = round(raw_score, 4)

    return reading


# ──────────────────────────────────────────────────────────────────────────────
# 4. API POSTING — send scored payloads to the FastAPI backend
# ──────────────────────────────────────────────────────────────────────────────

def post_to_api(reading: dict, api_url: str) -> dict | None:
    """
    POST a scored MeterReading to the FastAPI /predict endpoint.

    The backend runs its *own* Isolation Forest as well, so we get a
    second opinion.  The response contains the backend's prediction,
    anomaly_score, and threat_type.

    Returns the JSON response from the API, or None on failure.
    """
    # Build the payload matching the MeterReading Pydantic schema
    payload = {
        "meter_id":     reading["meter_id"],
        "voltage":      reading["voltage"],
        "current":      reading["current"],
        "power_factor": reading["power_factor"],
        "frequency":    reading["frequency"],
        "request_rate": reading["request_rate"],
    }

    try:
        resp = requests.post(f"{api_url}/predict", json=payload, timeout=5)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        # Don't crash the simulator on transient network errors
        print(f"  [API ERROR] {exc}")
        return None


# ──────────────────────────────────────────────────────────────────────────────
# 5. MAIN LOOP — tie everything together
# ──────────────────────────────────────────────────────────────────────────────

def run_simulation(api_url: str, interval: float) -> None:
    """
    Infinite loop:
      generate reading → maybe inject attack → score locally → post to API

    Press Ctrl+C to stop.
    """
    # ── Step A: Train the local Isolation Forest on clean data ──────────
    model, scaler = train_local_model()

    # ── Step B: Counters for the summary stats printed to the terminal ──
    total_sent   = 0
    total_anomal = 0

    print("=" * 72)
    print("  LIVE SMART-METER SIMULATION STARTED")
    print(f"  Posting to : {api_url}/predict")
    print(f"  Interval   : {interval}s between readings")
    print(f"  Attack prob: {ATTACK_PROBABILITY * 100:.0f}%")
    print("  Press Ctrl+C to stop")
    print("=" * 72, "\n")

    try:
        while True:
            # 1) Generate a clean reading
            reading = generate_normal_reading()

            # 2) Maybe inject a cyber-attack
            reading, attack_label = maybe_inject_attack(reading)

            # 3) Add a human-readable timestamp
            reading["timestamp"] = datetime.now(timezone.utc).isoformat()

            # 4) Score it with our LOCAL Isolation Forest
            reading = score_reading(reading, model, scaler)

            # 5) Pretty-print to the terminal
            status = "ANOMALY" if reading["is_anomaly"] else "normal "
            injected = f"[injected: {attack_label}]" if attack_label != "none" else ""
            print(
                f"  [{reading['timestamp']}]  {reading['meter_id']}  "
                f"V={reading['voltage']:7.2f}  "
                f"I={reading['current']:6.2f}  "
                f"PF={reading['power_factor']:.3f}  "
                f"f={reading['frequency']:6.3f}  "
                f"rr={reading['request_rate']:7.2f}  "
                f"| {status}  score={reading['threat_score']:+.4f}  "
                f"{injected}"
            )

            # 6) POST to the FastAPI backend for the dashboard
            api_result = post_to_api(reading, api_url)
            if api_result:
                total_sent += 1
                if api_result.get("prediction") == "anomaly":
                    total_anomal += 1

            # 7) Wait before the next reading
            time.sleep(interval)

    except KeyboardInterrupt:
        # Graceful shutdown summary
        print("\n" + "=" * 72)
        print("  SIMULATION STOPPED")
        print(f"  Total readings sent : {total_sent}")
        print(f"  Anomalies detected  : {total_anomal}")
        if total_sent:
            print(f"  Anomaly rate        : {total_anomal / total_sent * 100:.1f}%")
        print("=" * 72)


# ──────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Simulate live IoT smart-meter data with cyber-attack injection.",
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Base URL of the FastAPI backend (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Seconds between readings (default: 1.0)",
    )
    args = parser.parse_args()

    run_simulation(api_url=args.url, interval=args.interval)
