from dataclasses import dataclass

from sqlalchemy.sql.base import ExecutableOption
from sqlalchemy.sql.elements import ColumnElement, UnaryExpression

from app_base.utils.type_hint import SeqOrOneOrNone

WhereClause = SeqOrOneOrNone[ColumnElement[bool]]


@dataclass(frozen=True, slots=True, kw_only=True)
class ListQueryOptions:
    offset: int = 0
    limit: int | None = 100
    where: WhereClause = ()
    order_by: SeqOrOneOrNone[UnaryExpression] = ()
    select_options: SeqOrOneOrNone[ExecutableOption] = ()
    skip_count: bool = False
