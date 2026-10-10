HELP_TEXT = """Available commands:
help
battery
status
power
power list
power show <profile>
power set <profile>
power auto
power auto apply
idle status
idle set <seconds>
idle off
idle profile
settings
settings power
settings power set <profile>
settings idle
settings battery
settings display
settings display set <1-100>
settings display apply
settings network
apps
notes
notes add <text>
notes list
notes read <id>
notes delete <id>
time
date
sleep
shutdown
exit
quit
open browser [url]
open chrome [url]
browse <url>
thermal
thermal status
thermal tune
open settings
"""


def get_help_text() -> str:
    return HELP_TEXT.strip()
