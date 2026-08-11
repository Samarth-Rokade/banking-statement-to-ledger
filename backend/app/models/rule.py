import enum
import uuid

from sqlalchemy import Boolean, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.types import GUID


class RuleType(str, enum.Enum):
    TAG = "TAG"  # matches parsed_transactions.transaction_type_tag exactly
    KEYWORD = "KEYWORD"
    REGEX = "REGEX"
    CONFIG = "CONFIG"


class RuleDirection(str, enum.Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class Rule(Base):
    __tablename__ = "rules"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    rule_type: Mapped[RuleType] = mapped_column(Enum(RuleType), nullable=False)
    pattern: Mapped[str] = mapped_column(String, nullable=False)
    direction: Mapped[RuleDirection | None] = mapped_column(Enum(RuleDirection), nullable=True)
    ledger_name: Mapped[str | None] = mapped_column(String, nullable=True)
    group_name: Mapped[str | None] = mapped_column(String, nullable=True)
    voucher_type: Mapped[str | None] = mapped_column(String, nullable=True)
    config_value: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
