from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_active_user, get_db
from app.models.models import Agent, User
from app.schemas.agent import AgentCreate, AgentOut
from app.core.security import hash_password

router = APIRouter()


@router.get("", response_model=list[AgentOut])
def list_agents(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    agents = db.query(Agent).filter(Agent.organization_id == current_user.organization_id).all()
    return [AgentOut(**agent.__dict__) for agent in agents]


@router.post("", response_model=AgentOut, status_code=201)
def create_agent(payload: AgentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    agent = Agent(
        organization_id=current_user.organization_id,
        name=payload.name,
        description=payload.description,
        api_key_hash=hash_password(f"agent-{payload.name}-{current_user.id}"),
        permissions=payload.permissions or {},
        is_active=True,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return AgentOut(**agent.__dict__)


@router.get("/{agent_id}", response_model=AgentOut)
def get_agent(agent_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    agent = db.query(Agent).filter(Agent.id == agent_id, Agent.organization_id == current_user.organization_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return AgentOut(**agent.__dict__)


@router.post("/{agent_id}/rotate-key")
def rotate_key(agent_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    agent = db.query(Agent).filter(Agent.id == agent_id, Agent.organization_id == current_user.organization_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent.api_key_hash = hash_password(f"rotated-{agent.id}-{current_user.id}")
    db.commit()
    return {"status": "rotated", "agent_id": agent.id}


@router.post("/{agent_id}/revoke-key")
def revoke_key(agent_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    agent = db.query(Agent).filter(Agent.id == agent_id, Agent.organization_id == current_user.organization_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent.is_active = False
    db.commit()
    return {"status": "revoked", "agent_id": agent.id}
