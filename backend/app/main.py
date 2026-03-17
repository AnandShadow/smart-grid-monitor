"""
Smart Grid Cyber-Resilience API
================================
FastAPI backend that:
  1. Accepts simulated IoT smart-meter readings.
  2. Runs them through an Isolation Forest anomaly detector.
  3. Broadcasts scored results to all connected WebSocket clients in real time.
  4. Stores a rolling window of recent predictions.
  5. Serves data to the React dashboard.
"""

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from collections import deque

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.detector import AnomalyDetector
from app.models import MeterReading, PredictionResult, HealthResponse
from app.simulated_data import generate_batch

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
detector = AnomalyDetector()

# Rolling buffer of the last N predictions for the dashboard feed
MAX_HISTORY = 200
prediction_history: deque[dict] = deque(maxlen=MAX_HISTORY)


# ---------------------------------------------------------------------------
# WebSocket Connection Manager — broadcasts scored data to every React client
# ---------------------------------------------------------------------------
class ConnectionManager:
    """Keeps track of every active WebSocket and broadcasts JSON to all."""

    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)
        print(f"[ws] Client connected  ({len(self.active)} total)")

    def disconnect(self, ws: WebSocket) -> None:
        self.active.remove(ws)
        print(f"[ws] Client disconnected ({len(self.active)} total)")

    async def broadcast(self, data: dict) -> None:
        """Send a JSON message to every connected client."""
        payload = json.dumps(data, default=str)
        # Iterate over a copy so we can safely remove dead connections
        for ws in self.active[:]:
            try:
                await ws.send_text(payload)
            except Exception:
                self.active.remove(ws)


ws_manager = ConnectionManager()


# ---------------------------------------------------------------------------
# Lifespan — train / load model on startup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Try to load a persisted model; fall back to training from synthetic data
    if not detector.load():
        detector.train()
        print("[startup] Trained new Isolation Forest on synthetic data")
    else:
        print("[startup] Loaded persisted Isolation Forest model")
    yield

# ---------------------------------------------------------------------------
# App & middleware
# ---------------------------------------------------------------------------
app = FastAPI(
    title="HCS — Smart Grid Anomaly Detector",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Lock down for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# WebSocket endpoint — /ws/metrics
# ---------------------------------------------------------------------------

@app.websocket("/ws/metrics")
async def ws_metrics(ws: WebSocket):
    """
    Real-time metric stream for the React dashboard.

    The connection stays open; the server pushes a JSON message every time
    a new reading is scored via POST /predict.  The client never needs to
    poll — data arrives the instant the simulator sends it.
    """
    await ws_manager.connect(ws)
    try:
        # Keep the connection alive — wait for the client to close
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, tags=["ops"])
def health_check():
    return HealthResponse(
        status="ok",
        model_loaded=detector.is_ready,
        version="0.1.0",
    )


@app.post("/predict", response_model=PredictionResult, tags=["detection"])
async def predict_reading(reading: MeterReading):
    """Score a single smart-meter reading and broadcast via WebSocket."""
    if not detector.is_ready:
        raise HTTPException(status_code=503, detail="Model not ready")

    features = {
        "voltage": reading.voltage,
        "current": reading.current,
        "power_factor": reading.power_factor,
        "frequency": reading.frequency,
        "request_rate": reading.request_rate,
    }
    result = detector.predict(features)

    record = {
        "meter_id": reading.meter_id,
        "timestamp": datetime.now(timezone.utc),
        **features,
        **result,
    }
    prediction_history.appendleft(record)

    # ── Broadcast to every connected WebSocket client ──
    await ws_manager.broadcast(record)

    return PredictionResult(**record)


@app.get("/predict/batch", response_model=list[PredictionResult], tags=["detection"])
async def predict_batch(count: int = 20, anomaly_ratio: float = 0.15):
    """Generate *count* simulated readings, score them, and return results.

    Handy for populating the dashboard without a real meter fleet.
    """
    if not detector.is_ready:
        raise HTTPException(status_code=503, detail="Model not ready")

    readings = generate_batch(n=count, anomaly_ratio=anomaly_ratio)
    results = []
    for r in readings:
        features = {k: r[k] for k in ["voltage", "current", "power_factor", "frequency", "request_rate"]}
        pred = detector.predict(features)
        record = {
            "meter_id": r["meter_id"],
            "timestamp": datetime.now(timezone.utc),
            **features,
            **pred,
        }
        prediction_history.appendleft(record)
        # Broadcast each reading to WebSocket clients
        await ws_manager.broadcast(record)
        results.append(PredictionResult(**record))

    return results


@app.get("/history", response_model=list[PredictionResult], tags=["dashboard"])
def get_history(limit: int = 50):
    """Return the most recent predictions for the dashboard feed."""
    items = list(prediction_history)[:limit]
    return [PredictionResult(**i) for i in items]


@app.post("/model/retrain", tags=["ops"])
def retrain_model():
    """Re-train the Isolation Forest on fresh synthetic data."""
    info = detector.train()
    prediction_history.clear()
    return {"message": "Model retrained", **info}
