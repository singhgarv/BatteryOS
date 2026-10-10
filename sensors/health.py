def battery_health_status(health: int | None) -> str:
    if health is None:
        return "unknown"
    if health >= 90:
        return "excellent"
    if health >= 70:
        return "good"
    if health >= 50:
        return "fair"
    return "low"
