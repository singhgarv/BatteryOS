from commands.actions import launch_app, launch_browser, launch_chrome


def open_app(app_name: str) -> str:
    request = app_name.strip()
    folded_request = request.casefold()
    if folded_request == "web browser" or folded_request.startswith("web browser "):
        return launch_browser(request[len("web browser"):].strip())

    app_name, _, target = request.partition(" ")
    if app_name.casefold() == "browser":
        return launch_browser(target.strip())
    if app_name.casefold() == "chrome":
        return launch_chrome(target.strip())
    return launch_app(request)


def list_apps() -> str:
    return (
        "Available lightweight apps:\n"
        "settings     System settings\n"
        "notes        Local notes\n"
        "terminal     Current shell\n"
        "diagnostics  System status\n"
        "browser      Default browser\n"
        "chrome       Google Chrome, if installed"
    )
