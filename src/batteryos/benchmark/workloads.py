from dataclasses import dataclass


@dataclass(frozen=True)
class WorkloadDefinition:
    name: str
    description: str
    execution: str


WORKLOADS = {
    "idle": WorkloadDefinition(
        name="idle",
        description="Observe the machine without intentionally starting a workload.",
        execution="observe_only",
    ),
    "cpu-placeholder": WorkloadDefinition(
        name="cpu-placeholder",
        description="Reserved for a future controlled CPU workload; no load is started.",
        execution="not_implemented",
    ),
    "manual": WorkloadDefinition(
        name="manual",
        description="User performs a manually controlled workload outside BatteryOS.",
        execution="user_controlled",
    ),
}


def describe_workload(name: str, description: str | None = None) -> dict[str, str]:
    try:
        workload = WORKLOADS[name]
    except KeyError as error:
        raise ValueError(f"Unknown workload: {name}") from error
    return {
        "name": workload.name,
        "description": description if description is not None else workload.description,
        "execution": workload.execution,
    }