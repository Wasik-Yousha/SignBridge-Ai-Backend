"""
SignBridge AI — LLM Text Processing Service.

Calls Ollama (local Llama 3.1 8B) to simplify English text for sign-language
display.  Falls back to deterministic rule-based processing when Ollama is
unreachable.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


# ─── Data Models ──────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class TextChange:
    """One transformation that was applied to the original text."""

    from_word: str
    to_word: str | None
    reason: str


@dataclass(frozen=True, slots=True)
class ProcessedTextResult:
    """Full output of text processing."""

    original: str
    processed_words: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    changes: list[TextChange] = field(default_factory=list)
    method: str = "ollama"  # "ollama" or "rule-based"


# ─── Constants ────────────────────────────────────────────────

ARTICLES = {"a", "an", "the"}
AUXILIARY_VERBS = {
    "am", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did",
}
PREPOSITIONS = {
    "to", "of", "for", "in", "on", "at", "by", "with", "from",
    "up", "about", "into", "through", "during", "before", "after",
}
CONTRACTIONS: dict[str, str] = {
    "don't": "do not",
    "doesn't": "does not",
    "didn't": "did not",
    "can't": "can not",
    "couldn't": "could not",
    "won't": "will not",
    "wouldn't": "would not",
    "shouldn't": "should not",
    "isn't": "is not",
    "aren't": "are not",
    "wasn't": "was not",
    "weren't": "were not",
    "haven't": "have not",
    "hasn't": "has not",
    "hadn't": "had not",
    "i'm": "i am",
    "you're": "you are",
    "we're": "we are",
    "they're": "they are",
    "he's": "he is",
    "she's": "she is",
    "it's": "it is",
    "i've": "i have",
    "you've": "you have",
    "we've": "we have",
    "they've": "they have",
    "i'll": "i will",
    "you'll": "you will",
    "we'll": "we will",
    "they'll": "they will",
    "i'd": "i would",
    "you'd": "you would",
    "we'd": "we would",
    "they'd": "they would",
    "let's": "let us",
}

SYSTEM_PROMPT = """You are a text processor for a sign language translation system.
Given English text, you must:
1. Remove articles (a, an, the)
2. Remove auxiliary/linking verbs (am, is, are, was, were, be, been, being)
3. Remove prepositions when not essential (to, of, for, in, on, at)
4. Lemmatize verbs (going → go, running → run, went → go)
5. Lemmatize nouns (groceries → grocery, children → child)
6. Expand contractions (don't → do not, can't → can not)
7. Convert to lowercase
8. Keep the meaning clear with minimal words

Return ONLY a JSON object with no extra text:
{"words": ["word1", "word2", ...], "changes": [{"from": "original", "to": "result", "reason": "..."}]}"""


# ─── Service ──────────────────────────────────────────────────


class LLMService:
    """Manages Ollama communication with automatic rule-based fallback."""

    def __init__(self) -> None:
        self.base_url = settings.ollama_base_url
        self.model = settings.ollama_model
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(connect=5.0, read=60.0, write=5.0, pool=10.0),
        )

    # ── Public API ────────────────────────────────────────────

    async def process_text(self, text: str) -> ProcessedTextResult:
        """
        Process English text for sign language display.

        Tries Ollama first; on failure transparently falls back to rule-based
        processing so the caller never sees an error.
        """
        try:
            return await self._process_with_ollama(text)
        except Exception as exc:
            logger.warning("Ollama processing failed (%s) — using rule-based fallback.", exc)
            return self._process_rule_based(text)

    async def health_check(self) -> bool:
        """Return ``True`` if Ollama is reachable."""
        try:
            response = await self.client.get("/api/tags")
            return response.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    async def close(self) -> None:
        """Gracefully close the HTTP client."""
        await self.client.aclose()

    # ── Ollama Processing ─────────────────────────────────────

    async def _process_with_ollama(self, text: str) -> ProcessedTextResult:
        """Send text to Ollama and parse the structured JSON response."""
        payload = {
            "model": self.model,
            "system": SYSTEM_PROMPT,
            "prompt": f'Text: "{text}"',
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0,
                "num_predict": 512,
            },
        }

        response = await self.client.post("/api/generate", json=payload)
        response.raise_for_status()

        data = response.json()
        raw_response = data.get("response", "")

        # Extract JSON from the LLM response (may contain markdown fences)
        json_str = self._extract_json(raw_response)
        result = json.loads(json_str)

        if "words" not in result:
            raise ValueError("LLM response missing 'words' key")

        words: list[str] = [w.lower().strip() for w in result["words"] if w.strip()]
        changes: list[TextChange] = []
        removed: list[str] = []

        for change in result.get("changes", []):
            to_word = change.get("to")
            if to_word is None or to_word == "":
                removed.append(change.get("from", ""))
            changes.append(
                TextChange(
                    from_word=change.get("from", ""),
                    to_word=to_word,
                    reason=change.get("reason", ""),
                )
            )

        logger.info("Ollama processed %d words → %d signs", len(text.split()), len(words))

        return ProcessedTextResult(
            original=text,
            processed_words=words,
            removed=removed,
            changes=changes,
            method="ollama",
        )

    # ── Rule-Based Fallback ───────────────────────────────────

    def _process_rule_based(self, text: str) -> ProcessedTextResult:
        """Deterministic text cleanup when Ollama is unavailable."""
        original_words = self._tokenize(text)
        processed: list[str] = []
        removed: list[str] = []
        changes: list[TextChange] = []

        for word in original_words:
            lower = word.lower()

            # Expand contractions
            if lower in CONTRACTIONS:
                expanded = CONTRACTIONS[lower].split()
                changes.append(TextChange(from_word=word, to_word=CONTRACTIONS[lower], reason="contraction expanded"))
                for part in expanded:
                    # Still filter articles / aux verbs from expanded forms
                    if part in ARTICLES or part in AUXILIARY_VERBS:
                        removed.append(part)
                    else:
                        processed.append(part)
                continue

            # Remove articles
            if lower in ARTICLES:
                removed.append(word)
                changes.append(TextChange(from_word=word, to_word=None, reason="article removed"))
                continue

            # Remove auxiliary verbs
            if lower in AUXILIARY_VERBS:
                removed.append(word)
                changes.append(TextChange(from_word=word, to_word=None, reason="auxiliary verb removed"))
                continue

            # Remove prepositions
            if lower in PREPOSITIONS:
                removed.append(word)
                changes.append(TextChange(from_word=word, to_word=None, reason="preposition removed"))
                continue

            # Basic lemmatization
            lemma = self._lemmatize(lower)
            if lemma != lower:
                changes.append(TextChange(from_word=word, to_word=lemma, reason="lemmatized"))
            processed.append(lemma)

        logger.info("Rule-based processed %d words → %d signs", len(original_words), len(processed))

        return ProcessedTextResult(
            original=text,
            processed_words=processed,
            removed=removed,
            changes=changes,
            method="rule-based",
        )

    # ── Helpers ───────────────────────────────────────────────

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Split text into words, removing punctuation."""
        return re.findall(r"[a-zA-Z'-]+", text)

    # Endings that are inherent to the base word (not added by conjugation)
    # e.g. call, miss, off — should NOT have a letter stripped
    _INHERENT_DOUBLES: frozenset[str] = frozenset({"ll", "ss", "ff"})

    @staticmethod
    def _lemmatize(word: str) -> str:
        """Very simple suffix-based lemmatization."""
        # Order matters — check longer suffixes first
        if word.endswith("ies") and len(word) > 4:
            return word[:-3] + "y"    # groceries → grocery
        if word.endswith("ves") and len(word) > 4:
            return word[:-3] + "f"    # wolves → wolf
        if word.endswith("ing") and len(word) > 4:
            base = word[:-3]
            # If stripping -ing yields a vowel-less base (e.g. "bring"→"br",
            # "string"→"str"), the word is not a gerund — keep as-is.
            if not re.search(r"[aeiou]", base):
                return word
            # Strip doubled consonant only when it was added for conjugation
            # (e.g. run→runn+ing, sit→sitt+ing) but not inherent doubles.
            if (
                len(base) > 2
                and base[-1] == base[-2]                        # double last char
                and base[-2:] not in LLMService._INHERENT_DOUBLES  # not inherent
            ):
                return base[:-1]      # running → run
            return base               # going → go, filling → fill
        if word.endswith("ed") and len(word) > 3:
            base = word[:-2]
            if (
                len(base) > 2
                and base[-1] == base[-2]
                and base[-2:] not in LLMService._INHERENT_DOUBLES
            ):
                return base[:-1]      # stopped → stop
            return base               # walked → walk, called → call
        if word.endswith("es") and len(word) > 3:
            return word[:-2]          # watches → watch
        if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
            return word[:-1]          # cats → cat
        return word

    @staticmethod
    def _extract_json(text: str) -> str:
        """Pull the first JSON object out of text that may include markdown fences."""
        # Strip markdown code fences
        text = re.sub(r"```(?:json)?\s*", "", text)
        text = text.replace("```", "")

        # Find first { … } block
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return match.group(0)
        raise ValueError("No JSON object found in LLM response")


# ─── Module-level singleton ──────────────────────────────────
llm_service = LLMService()
