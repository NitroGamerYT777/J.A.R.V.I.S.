from dataclasses import dataclass


@dataclass(frozen=True)
class Response:
    text: str
    should_exit: bool = False
