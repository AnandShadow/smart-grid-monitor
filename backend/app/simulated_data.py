"""Simulated IoT data generator for demo / hackathon use."""

import random
import string


def random_meter_id() -> str:
    return f"SM-{random.randint(1, 200):03d}"


def generate_normal_reading() -> dict:
    """Return a single realistic *normal* meter reading."""
    return {
        "meter_id": random_meter_id(),
        "voltage": round(random.gauss(230.0, 3.0), 2),
        "current": round(random.gauss(15.0, 2.0), 2),
        "power_factor": round(random.uniform(0.85, 1.0), 3),
        "frequency": round(random.gauss(50.0, 0.05), 3),
        "request_rate": round(random.expovariate(1.0), 2),
    }


def generate_attack_reading() -> dict:
    """Return a reading that mimics a cyber-attack pattern."""
    attack = random.choice(["ddos", "voltage_injection", "frequency_injection"])

    reading = generate_normal_reading()

    if attack == "ddos":
        reading["request_rate"] = round(random.uniform(15, 100), 2)
    elif attack == "voltage_injection":
        reading["voltage"] = round(random.choice([
            random.uniform(140, 185),
            random.uniform(270, 350),
        ]), 2)
    elif attack == "frequency_injection":
        reading["frequency"] = round(random.choice([
            random.uniform(45, 48.5),
            random.uniform(52, 55),
        ]), 3)

    return reading


def generate_batch(n: int = 20, anomaly_ratio: float = 0.15) -> list[dict]:
    """Generate a mixed batch of normal + attack readings."""
    batch = []
    for _ in range(n):
        if random.random() < anomaly_ratio:
            batch.append(generate_attack_reading())
        else:
            batch.append(generate_normal_reading())
    return batch
