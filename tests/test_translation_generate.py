import pytest
from src.translate.generate import translate_one, content

class Mock:
    provider="mock"

def test_genuine_translation_rejects_mock():
    with pytest.raises(ValueError,match="mock translator"):
        translate_one(Mock(),"x","hello","de")

def test_empty_response_fails():
    with pytest.raises(ValueError):
        content({"choices":[]})

def test_translation_marks_unvalidated():
    class Fake:
        provider="openai_compatible"
        models={"translator":"fake-translator"}
        request={"temperature":0}
        def chat(self,role,messages):
            return {"choices":[{"message":{"content":"the example"}}]}
    record=translate_one(Fake(),"x","the example","fr")
    assert record["validated_by_me"] is False
    assert record["needs_native_check"] is True
    assert record["back_translation_similarity"]==1
