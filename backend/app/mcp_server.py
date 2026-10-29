from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.models import Policy, PolicyDecision, Website


def evaluate_policy(db: Session, *, website_id: int, action: str = "read", data_classification: str = "public", agent_id: int | None = None) -> dict:
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise ValueError("Website not found")

    policy_records = db.query(Policy).filter(
        Policy.organization_id == website.organization_id,
        (Policy.website_id == website_id) | (Policy.website_id.is_(None))
    ).all()

    if not policy_records:
        decision = "allow" if action == "read" and data_classification == "public" else "deny"
        reason = "No custom policy found; default public-read policy applied."
        final = {
            "allowed": decision == "allow",
            "decision": decision,
            "reason": reason,
            "trace_id": uuid4().hex,
        }
        return final

    for policy in policy_records:
        rules = policy.rules or {}
        if action == "read" and rules.get("allow_public_read") and data_classification == "public":
            decision = policy.effect if policy.effect in {"allow", "deny"} else "allow"
            reason = f"Matched policy '{policy.name}' with public-read allowance."
            trace_id = uuid4().hex
            record_decision(db, policy.id, website_id, agent_id, decision, reason, trace_id)
            return {"allowed": decision == "allow", "decision": decision, "reason": reason, "trace_id": trace_id}

        if action in {"write", "delete", "admin"} and rules.get("require_approval"):
            decision = "deny"
            reason = f"Matched policy '{policy.name}'; sensitive action requires approval."
            trace_id = uuid4().hex
            record_decision(db, policy.id, website_id, agent_id, decision, reason, trace_id)
            return {"allowed": False, "decision": decision, "reason": reason, "trace_id": trace_id}

    decision = policy_records[0].effect if policy_records[0].effect in {"allow", "deny"} else "allow"
    reason = f"Default policy '{policy_records[0].name}' evaluated without a specific match."
    trace_id = uuid4().hex
    record_decision(db, policy_records[0].id, website_id, agent_id, decision, reason, trace_id)
    return {"allowed": decision == "allow", "decision": decision, "reason": reason, "trace_id": trace_id}


def record_decision(db: Session, policy_id: int, website_id: int, agent_id: int | None, decision: str, reason: str, trace_id: str) -> PolicyDecision:
    decision_record = PolicyDecision(
        policy_id=policy_id,
        website_id=website_id,
        agent_id=agent_id,
        decision=decision,
        reason=reason,
        trace_id=trace_id,
    )
    db.add(decision_record)
    db.commit()
    db.refresh(decision_record)
    return decision_record
