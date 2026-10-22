from dataclasses import dataclass, field


@dataclass
class Result:
    """What one measure says about one brief."""

    metrics: dict[str, str | int | float]  # one value per column in the score table
    details: list[str] = field(default_factory=list)  # extra lines for `vc-evals measure`
