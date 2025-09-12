from dataclasses import dataclass


@dataclass
class Agent:
    id: int
    state: str = "idle"


class Queue:
    def __init__(self) -> None:
        self.items: list[int] = []

    def add(self, item: int) -> None:
        self.items.append(item)

    def pop(self) -> int | None:
        return self.items.pop(0) if self.items else None

    def __len__(self) -> int:  # for tests
        return len(self.items)