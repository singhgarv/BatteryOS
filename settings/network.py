from sensors.telemetry import WifiSensor


def show_network_settings() -> str:
    connected = WifiSensor().is_connected()
    state = "connected" if connected is True else "disconnected" if connected is False else "unknown"
    return f"Wi-Fi: {state}\nNetwork changes are unavailable; no control backend is configured."