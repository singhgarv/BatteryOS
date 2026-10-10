def charging_state(is_charging: bool | None) -> str:
    if is_charging is None:
        return "unknown"
    return "charging" if is_charging else "not charging"
