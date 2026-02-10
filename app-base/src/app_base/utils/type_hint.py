from typing import Sequence, TypeAlias, TypeVar

T = TypeVar("T")
SeqOrOne: TypeAlias = Sequence[T] | T
SeqOrOneOrNone: TypeAlias = SeqOrOne | None


def to_sequence(value: SeqOrOneOrNone[T]) -> Sequence[T] | None:
    """Convert a value to a sequence."""
    if value is None:
        return None
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return value
    else:
        return [value]
