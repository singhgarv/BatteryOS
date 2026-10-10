if __package__ in (None, ""):
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from commands.registry import execute_command
else:
    from commands.registry import execute_command


def route_command(raw_command: str) -> str:
    return execute_command(raw_command)
