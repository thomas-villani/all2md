"""Example module used in conversion tests."""

from __future__ import annotations


class Greeter:
    """Simple greeter with configurable salutation."""

    def __init__(self, salutation: str = "Hello") -> None:
        self.salutation = salutation

    def greet(self, name: str) -> str:
        return f"{self.salutation}, {name}!"


def main() -> None:
    greeter = Greeter()
    print(greeter.greet("World"))


if __name__ == "__main__":
    main()
