"""Construct the AgentDojo OpenAILLM pipeline using the capped API facade."""
from src.eval.agentdojo_adapter import require_agentdojo, verify_defenses
from src.llm.agentdojo_shim import BudgetedOpenAI
from src.llm.client import Client


def build_pipeline(client: Client, defense="none"):
    require_agentdojo()
    verify_defenses()
    from agentdojo.agent_pipeline.agent_pipeline import AgentPipeline, PipelineConfig
    from agentdojo.agent_pipeline.llms.openai_llm import OpenAILLM
    if defense not in ("none", "tool_filter", "repeat_user_prompt"):
        raise ValueError("learned classifier requires a separately validated custom pipeline")
    model = "mock-victim" if client.provider == "mock" else client.models["victim"]
    llm = OpenAILLM(
        BudgetedOpenAI(client), model, temperature=client.request.get("temperature", 0)
    )
    # AgentDojo 0.1.35 gets custom-model identity via llm.name.
    llm.name = model
    return AgentPipeline.from_config(PipelineConfig(
        llm=llm,
        model_id=model,
        defense=None if defense == "none" else defense,
        system_message_name=None,
        system_message=None,
    ))
