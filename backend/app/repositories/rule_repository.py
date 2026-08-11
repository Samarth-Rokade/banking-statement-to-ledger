from sqlalchemy.orm import Session

from app.models.rule import Rule, RuleDirection, RuleType


class RuleRepository:
    def __init__(self, db: Session):
        self.db = db

    def find_matching_tag_rule(self, tag: str, is_debit: bool) -> Rule | None:
        direction = RuleDirection.DEBIT if is_debit else RuleDirection.CREDIT
        candidates = (
            self.db.query(Rule)
            .filter(Rule.rule_type == RuleType.TAG, Rule.pattern == tag, Rule.is_active.is_(True))
            .order_by(Rule.priority.desc())
            .all()
        )
        for rule in candidates:
            if rule.direction is None or rule.direction == direction:
                return rule
        return None
