from collections.abc import Sequence

type SeqOrOne[T] = Sequence[T] | T
type SeqOrOneOrNone[T] = Sequence[T] | T | None


def to_sequence[T](value: SeqOrOne[T]) -> Sequence[T]:
    """Convert a value to a sequence."""
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return value
    else:
        return [value]  # type: ignore


def to_sequence_or_none[T](value: SeqOrOneOrNone[T]) -> Sequence[T] | None:
    """Convert a value to a sequence."""
    if value is None:
        return None
    return to_sequence(value)
