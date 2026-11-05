"""Unit tests must run offline without AgentDojo or API credentials."""
import json
import tempfile
from pathlib import Path

import pytest

from src.llm.client import BudgetExceeded, Client, ConfigError
from src.attack.search import run_search
from src.translate.store import load_translations, spotcheck
from src.analysis.metrics import rate, wilson, paired_bootstrap


MOCK = {
    "provider": "mock",
    "models": {"victim":"FILL_IN", "attacker":"FILL_IN","translator":"FILL_IN"},
    "limits": {"max_requests_per_min":"FILL_IN", "max_tokens_per_min":"FILL_IN",
               "max_total_requests":"FILL_IN","max_total_usd":0},
    "request":{"temperature":0,"max_tokens":16,"timeout_s":1}
}

def create_client(tmp,config=None,**kwargs):
    return Client(config=config or MOCK,ledger=tmp/"requests.sqlite3",
                  cache_dir=tmp/"cache",**kwargs)

def test_mock_is_deterministic_and_cached():
    with tempfile.TemporaryDirectory() as d:
        tmp=Path(d)
        client=create_client(tmp)
        msg=[{"role":"user","content":"hello"}]
        assert client.chat("victim",msg)==client.chat("victim",msg)
        assert client.usage()[0]["requests"]==1
        assert client.chat("attacker",msg)["model"]=="mock-attacker"
        assert client.usage()[0]["requests"]==2

def test_real_provider_fails_closed_on_zero_cost_limit():
    with tempfile.TemporaryDirectory() as d:
        cfg={**MOCK,"provider":"openai_compatible",
             "base_url":"https://example.invalid/v1",
             "models":{"victim":"v","attacker":"a","translator":"t"},
             "limits":{"max_requests_per_min":3,"max_tokens_per_min":500,
                       "max_total_requests":2,"max_total_usd":0}}
        with pytest.raises(ConfigError):
            create_client(Path(d),cfg)

def test_global_request_cap_across_clients(monkeypatch):
    monkeypatch.setenv("API_KEY","fake")
    with tempfile.TemporaryDirectory() as d:
        cfg={**MOCK,"provider":"openai_compatible",
             "base_url":"https://example.invalid/v1",
             "models":{"victim":"v","attacker":"a","translator":"t"},
             "limits":{"max_requests_per_min":10,"max_tokens_per_min":10000,
                       "max_total_requests":2,"max_total_usd":1,"max_usd_per_request":0.01}}
        tmp=Path(d)
        calls=[]
        def fake_transport(url,key,payload,timeout):
            calls.append(payload)
            return {"choices":[{"message":{"content":"OK"}}]}
        a=create_client(tmp,cfg,transport=fake_transport)
        b=create_client(tmp,cfg,transport=fake_transport)
        for i,client in enumerate((a,b)):
            client.chat("victim",[{"role":"user","content":str(i)}])
        with pytest.raises(BudgetExceeded):
            a.chat("victim",[{"role":"user","content":"third"}])
        assert len(calls)==2

def test_rate_limiter_limits_rpm(monkeypatch):
    monkeypatch.setenv("API_KEY","fake")
    with tempfile.TemporaryDirectory() as d:
        cfg={**MOCK,"provider":"openai_compatible",
             "base_url":"https://example.invalid/v1",
             "models":{"victim":"v","attacker":"a","translator":"t"},
             "limits":{"max_requests_per_min":1,"max_tokens_per_min":10000,
                       "max_total_requests":10,"max_total_usd":1,"max_usd_per_request":0.01}}
        c=create_client(Path(d),cfg,transport=lambda *args: {"choices":[]},clock=lambda:1000.0)
        c.chat("victim",[{"role":"user","content":"a"}])
        with pytest.raises(BudgetExceeded,match="minute"):
            c.chat("victim",[{"role":"user","content":"b"}])

def test_translation_loader_and_validation():
    with tempfile.TemporaryDirectory() as d:
        path=Path(d)/"example.json"
        item={"id":"a","lang":"en","text":"placeholder","provenance":"machine",
              "back_translation":"placeholder","back_translation_similarity":None,
              "needs_native_check":True,"validated_by_me":False}
        path.write_text(json.dumps({"version":1,"items":[item]}))
        assert len(load_translations(path)["items"])==1
        assert spotcheck(load_translations(path),20)[0]["validated_by_me"] is False
        item["validated_by_me"]="yes"
        path.write_text(json.dumps({"version":1,"items":[item]}))
        with pytest.raises(ValueError):
            load_translations(path)

def test_adaptive_loop_resumes_without_repeating_budget():
    with tempfile.TemporaryDirectory() as d:
        path=Path(d)/"attempts.jsonl"
        def propose(initial,history,condition,languages):
            return {"text":initial+str(len(history)),"language":"en","script":"Latn",
                    "code_mix_ratio":0,"strategy":"mock"}
        def evaluate(text):
            return {"success":text.endswith("2"),"visible_defense_output":"blocked"}
        a=run_search(propose=propose,evaluate=evaluate,initial="p",condition="C3",
                     languages=["en"],budget=10,log_path=path)
        assert a["first_success"]==3
        b=run_search(propose=propose,evaluate=evaluate,initial="p",condition="C3",
                     languages=["en"],budget=10,log_path=path)
        assert b["attempts"]==3
        assert len(path.read_text().splitlines())==3

def test_adaptive_language_restriction():
    with pytest.raises(ValueError,match="C3"):
        run_search(propose=lambda *x:{"text":"x","language":"es","script":"Latn",
                   "code_mix_ratio":0,"strategy":"translation"},
                   evaluate=lambda x:{"success":False},initial="a",
                   condition="C3",languages=["en","es"],budget=1)

def test_wilson_and_rates():
    assert wilson(0,0) is None
    assert rate([True,False])["n"]==2
    assert wilson(0,1)[0]==0
    assert wilson(1,1)[1]==1
    with pytest.raises(ValueError):
        rate([1,0])

def test_cluster_bootstrap():
    result=paired_bootstrap([("a",False,True),("b",True,True)],samples=100,seed=7)
    assert result["n_families"]==2
    assert result["difference_c4_minus_c3"]==0.5
