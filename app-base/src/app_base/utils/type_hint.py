from typing import Sequence, TypeAlias, TypeVar

T = TypeVar("T")
SeqOrOne: TypeAlias = Sequence[T] | T
SeqOrOneOrNone: TypeAlias = Sequence[T] | T | None


def to_sequence(value: SeqOrOne[T]) -> Sequence[T]:
    """Convert a value to a sequence."""
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return value
    else:
        return [value]  # type: ignore


def to_sequence_or_none(value: SeqOrOneOrNone[T]) -> Sequence[T] | None:
    """Convert a value to a sequence."""
    if value is None:
        return None
    return to_sequence(value)
