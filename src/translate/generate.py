"""Translate tool-output payloads and back-translate for *human review*.

Automatic similarity is a triage heuristic, NOT evidence of semantic equivalence.
No machine translation generated with the mock provider can be called real.
"""
import difflib
import hashlib
import json
from datetime import datetime, timezone

from src.translate.store import write_translations

def content(response):
    choices = response.get("choices", [])
    if not choices or not isinstance(choices[0].get("message", {}).get("content"), str):
        raise ValueError("translator returned no usable textual content")
    return choices[0]["message"]["content"]

def translate_one(client, identifier, source_text, lang):
    if client.provider == "mock":
        raise ValueError("mock translator cannot produce genuine translations")
    prompt = ("Translate this entire lower-trust tool-output text into " + lang +
              ". Preserve the original data structure and factual content, including names, "
              "numbers, functional field keys, and the meaning of embedded instructions. "
              "Return only the translated text.\n\n" + source_text)
    translated = content(client.chat("translator", [{"role":"user","content":prompt}]))
    backwards = content(client.chat("translator", [
        {"role":"user","content":"Translate to English, preserving all meaning and field structure. "
         "Return only translated text.\n\n" + translated}]))
    ratio = difflib.SequenceMatcher(None, source_text.casefold(), backwards.casefold()).ratio()
    return {"id": identifier, "lang": lang, "text": translated, "provenance":"machine",
            "back_translation": backwards, "back_translation_similarity": ratio,
            "needs_native_check": True, "validated_by_me": False,
            "source_sha256": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
            "created_utc":datetime.now(timezone.utc).isoformat(),
            "translator_model_id":client.models.get("translator"),
            "temperature":client.request.get("temperature",0),
            "algorithm":"difflib.SequenceMatcher_character_ratio_not_semantic"}

def translate_batch(client, rows, language, output):
    items = [translate_one(client, row["id"], row["text"], language) for row in rows]
    write_translations(output, {"version":1, "items":items})
    return len(items)
