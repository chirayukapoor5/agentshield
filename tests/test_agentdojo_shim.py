from pathlib import Path
from tempfile import TemporaryDirectory
import pytest
from src.llm.client import Client
from src.llm.agentdojo_shim import BudgetedOpenAI

def test_budgeted_agentdojo_shim_mock():
    with TemporaryDirectory() as d:
        client=Client(config={"provider":"mock","models":{},
               "limits":{},"request":{"temperature":0,"max_tokens":4}},
               ledger=Path(d)/"ledger.db",cache_dir=Path(d)/"cache")
        sdk=BudgetedOpenAI(client)
        response=sdk.chat.completions.create(model="mock-victim",
                   messages=[{"role":"user","content":"test"}],tools=[])
        assert response.choices[0].message.content.startswith("MOCK_RESPONSE")
        assert response.choices[0].message.tool_calls is None
        with pytest.raises(ValueError,match="configured victim"):
            sdk.chat.completions.create(model="unconfigured",messages=[])
