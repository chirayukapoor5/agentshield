"""AgentDojo OpenAILLM-compatible client façade over the budget-enforced client.

AgentDojo 0.1.35 calls .chat.completions.create(...) and reads choice.message.
No OpenAI SDK call is allowed outside src.llm.client.Client.
"""
from types import SimpleNamespace
from src.llm.client import Client

def _object(value):
    if isinstance(value,dict):
        return SimpleNamespace(**{k:_object(v) for k,v in value.items()})
    if isinstance(value,list):
        return [_object(v) for v in value]
    return value

def _present(value):
    # openai._types.NOT_GIVEN signals an absent argument, not a JSON object.
    return value is not None and type(value).__name__ not in ("NotGiven","NotGivenType")

class _Completions:
    def __init__(self, client):
        self.client=client

    def create(self, *, model, messages, tools=None, tool_choice=None,
               temperature=None, reasoning_effort=None, **kwargs):
        if self.client.provider=="mock":
            expected="mock-victim"
        else:
            expected=self.client.models.get("victim")
        if model!=expected:
            raise ValueError("AgentDojo cannot request a model other than configured victim")
        extra={}
        for key,value in (("tools",tools),("tool_choice",tool_choice),
                          ("reasoning_effort",reasoning_effort)):
            if _present(value):
                extra[key]=value
        # AgentDojo upstream sometimes supplies SDK's NOT_GIVEN for temp.
        temp=temperature if _present(temperature) else None
        response=self.client.chat("victim",messages,temperature=temp,extra=extra)
        choices=response.get("choices",[])
        if not choices:
            raise ValueError("no completion choices")
        normalized=[]
        for choice in choices:
            message=dict(choice.get("message",{}))
            message.setdefault("content",None)
            message.setdefault("tool_calls",None)
            normalized.append({**choice,"message":message})
        return _object({**response,"choices":normalized})

class BudgetedOpenAI:
    def __init__(self, client:Client):
        self.chat=SimpleNamespace(completions=_Completions(client))
