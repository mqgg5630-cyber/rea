"""A deterministic, dependency-free scorer that stands in for the checkpoint.

Why this exists
---------------
laya's contract is a protocol plus a decode rule plus a learned encoder. The
first two are fully recoverable (and are reproduced here and verified against
real logits). The third is 421M parameters that are not redistributable inside
this repository and cannot be downloaded in an offline sandbox.

So the *decision* half is supplied by a distilled lexical scorer:

* BM25-style IDF over the state and the rendered options,
* Unicode-aware tokens plus CJK bigrams (no tokenizer, no download),
* a curated cross-lingual cue lexicon (``data/rubric.json``) that expands an
  English option description into the vocabulary a Chinese, Spanish, German,
  French, Portuguese, Japanese or Korean state would use,
* negation scoping, and character-trigram similarity for morphology.

The output is *logits*, so everything downstream - temperature, softmax,
choice/score/noul decoding, confidence, abstention - is laya's, unchanged.

An agent can replace this scorer end to end: see ``engine.py``'s ``agent``
engine, which accepts per-option logits authored by the calling model.
"""

from __future__ import annotations

import json
import math
import os
import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .protocol import QuestionError, normalize_text, render_options

_WORD = re.compile(r"[^\W\d_]+|\d+(?:[.,]\d+)*", re.UNICODE)
_CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3040-\u30ff\uac00-\ud7af]")

MATCH_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with", "at", "by", "from",
    "is", "are", "was", "were", "be", "been", "being", "it", "this", "that", "these", "those",
    "as", "if", "then", "than", "so", "such", "very", "can", "could", "would", "should", "may",
    "might", "will", "shall", "do", "does", "did", "has", "have", "had", "i", "we", "you", "they",
    "he", "she", "my", "our", "your", "their", "its", "me", "us", "them", "what", "which", "who",
    "when", "where", "why", "how", "please", "there", "here", "about", "into", "over", "after",
    "before", "all", "any", "some", "more", "most", "other", "up", "out", "just", "also",
    "的", "了", "是", "在", "我", "你", "他", "她", "它", "们", "和", "与", "或", "有", "被",
    "把", "就", "都", "而", "及", "等", "个", "这", "那", "什么", "怎么", "为什么",
    "el", "la", "los", "las", "de", "del", "que", "y", "en", "un", "una", "por", "para", "con",
    "es", "son", "se", "su", "al", "lo", "como", "pero", "más", "muy", "hay",
    "le", "les", "des", "du", "et", "est", "une", "un", "pour", "dans", "que", "qui", "avec",
    "sur", "pas", "plus", "ce", "cette", "sont", "au", "aux",
    "der", "die", "das", "und", "ist", "ein", "eine", "den", "dem", "nicht", "mit", "für", "auf",
    "von", "zu", "sich", "auch", "werden", "sind", "oder", "aber",
    "o", "os", "as", "um", "uma", "em", "com", "não", "é", "do", "da", "dos", "das", "mas", "são",
    "no", "na", "nas", "ao", "aos", "por", "foi", "ser", "tem",
    "il", "lo", "gli", "che", "di", "per", "con", "non", "è", "si", "del", "della",
    "の", "は", "が", "を", "に", "で", "と", "も", "や", "から", "まで", "です", "ます",
}

NEGATORS = {
    "not", "no", "never", "without", "cannot", "cant", "can't", "dont", "don't", "doesnt",
    "doesn't", "isnt", "isn't", "wasnt", "wasn't", "wont", "won't", "nor", "neither",
    "不", "没", "没有", "未", "无", "無", "别", "勿",
    "kein", "keine", "keinen", "nicht", "nie", "ohne",
    "ne", "pas", "aucun", "aucune", "jamais", "sans",
    "nunca", "sin", "ningún", "ninguna", "no",
    "não", "sem", "nenhum", "nenhuma",
    "nessun", "nessuna", "senza", "mai",
    "ない", "ません", "なかった", "無い", "없", "안", "아니",
}


def _strip_marks(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def tokens(text: str, *, keep_stop: bool = False) -> List[str]:
    norm = normalize_text(text)
    words = _WORD.findall(norm)
    cjk_chars = [ch for ch in norm if _CJK.match(ch)]
    bigrams = [cjk_chars[i] + cjk_chars[i + 1] for i in range(len(cjk_chars) - 1)]
    out = words + cjk_chars + bigrams
    if not keep_stop:
        out = [w for w in out if w not in MATCH_STOP]
    # Fold accents for matching as well, so "facture" matches "facturé".
    out = [w for w in out if w.strip()]
    return out


def token_set(text: str) -> set:
    out = set(tokens(text))
    out.update(_strip_marks(w) for w in list(out) if any(ord(c) > 127 for c in w))
    return out


def _trigrams(text: str) -> set:
    letters = "".join(ch for ch in normalize_text(text) if ch.isalpha())
    if len(letters) < 6:
        return set()
    return {letters[i:i + 3] for i in range(len(letters) - 2)}


def dice(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return 2.0 * len(a & b) / (len(a) + len(b))


def _clip(value: float, lo: float, hi: float) -> float:
    return lo if value < lo else hi if value > hi else value


class Rubric:
    """The distilled cue lexicon, loaded once and reused."""

    def __init__(self, cues: Optional[List[Dict[str, Any]]] = None,
                 scales: Optional[Dict[str, Any]] = None):
        self.cues: List[Dict[str, Any]] = []
        for cue in cues or []:
            match = [normalize_text(m) for m in cue.get("match", []) if m]
            terms = [normalize_text(t) for t in cue.get("terms", []) if t]
            if match and terms:
                self.cues.append({"id": cue.get("id", "cue"), "match": match, "terms": terms})
        self.scales: Dict[str, Dict[str, Any]] = {}
        for name, spec in (scales or {}).items():
            levels = []
            for level in spec.get("levels", []):
                terms = [normalize_text(t) for t in level.get("terms", []) if t]
                if terms:
                    levels.append({"terms": terms, "value": float(level.get("value", 0.5))})
            if levels:
                self.scales[name] = {
                    "match": [normalize_text(m) for m in spec.get("match", []) if m],
                    "levels": sorted(levels, key=lambda item: item["value"]),
                }

    @classmethod
    def load(cls, path: Optional[str] = None) -> "Rubric":
        path = path or os.path.join(os.path.dirname(__file__), "data", "rubric.json")
        try:
            with open(path, "r", encoding="utf-8") as fh:
                doc = json.load(fh)
            return cls(doc.get("cues", []), doc.get("scales", {}))
        except (OSError, ValueError):
            return cls([])

    def scale_for(self, instructions: str) -> Optional[Dict[str, Any]]:
        norm = normalize_text(instructions)
        for name, scale in self.scales.items():
            if any(term in norm for term in scale["match"]):
                return scale
        return None

    @staticmethod
    def intensity(scale: Dict[str, Any], text: str) -> Tuple[float, str]:
        """The strongest intensity cue the state carries, and which one matched."""
        norm = normalize_text(text)
        best_value, best_term = 0.35, ""
        for level in scale["levels"]:
            for term in level["terms"]:
                if term in norm and level["value"] > best_value:
                    best_value, best_term = level["value"], term
        return best_value, best_term

    def expansions(self, text: str) -> List[str]:
        """Terms from every cue the text semantically belongs to."""
        norm = normalize_text(text)
        terms: List[str] = []
        for cue in self.cues:
            if any(term in norm for term in cue["match"]):
                terms.extend(cue["terms"])
        return terms


def _docs_for(q: Dict[str, Any], rubric: Rubric) -> List[str]:
    """The text profile of each option, in option order."""
    if q["t"] == "noul":
        crit = q.get("crit") or {}
        ins = str(q.get("ins") or "")
        true_text = str(crit.get("true") or "")
        false_text = str(crit.get("false") or "")
        if not true_text:
            true_text = "yes, the statement holds. " + ins
        if not false_text:
            false_text = "no, the statement does not hold"
        return [false_text, true_text]
    return render_options(q)


def _doc_terms(doc: str, rubric: Rubric) -> Tuple[Dict[str, float], Dict[str, float]]:
    """Token weights for one option profile: base 1.0, label 1.5, cue 0.55."""
    weights: Dict[str, float] = {}
    base_tokens = tokens(doc)
    for tok in base_tokens:
        weights[tok] = 1.0
    if ":" in doc:
        label = doc.split(":", 1)[0]
        for tok in tokens(label):
            weights[tok] = 1.5
    for term in rubric.expansions(doc):
        for tok in tokens(term):
            weights.setdefault(tok, 0.55)
    folded: Dict[str, float] = {}
    for tok, weight in weights.items():
        folded[tok] = max(folded.get(tok, 0.0), weight)
        plain = _strip_marks(tok)
        if plain != tok:
            folded[plain] = max(folded.get(plain, 0.0), weight)
    return folded, weights


class LexicalScorer:
    """IDF + cue-expansion scorer. Deterministic, offline, ~1 ms per question."""

    def __init__(self, rubric: Optional[Rubric] = None, beta: float = 1.35,
                 trigram_weight: float = 1.1, negation_penalty: float = 1.25,
                 noul_beta: float = 1.2):
        self.rubric = rubric or Rubric.load()
        self.beta = beta
        self.trigram_weight = trigram_weight
        self.negation_penalty = negation_penalty
        self.noul_beta = noul_beta

    def score(self, state_text: str, q: Dict[str, Any]) -> List[float]:
        if q["t"] == "noul":
            return self._score_noul(state_text, q)
        raw = self._raw_choice(state_text, q)
        # Exact label mention: a state that names an option outright gets a nudge.
        if q["t"] == "choice":
            norm_state = normalize_text(state_text)
            for i, doc in enumerate(_docs_for(q, self.rubric)):
                if ":" in doc:
                    label = normalize_text(doc.split(":", 1)[0]).strip()
                    if label and label in norm_state:
                        raw[i] += 1.6
        elif q["t"] == "score":
            raw = self._apply_scale(state_text, q, raw)
        return self._to_logits(raw)

    def _apply_scale(self, state_text: str, q: Dict[str, Any], raw: List[float]) -> List[float]:
        """Ordinal anchoring for a score question that names an intensity scale.

        A score's levels are ordered, so an agent-readable scale ("urgent",
        "frustration") turns intensity cues in the state into a position on it.
        Without this a rubric whose levels do not share vocabulary with the
        state ("today" vs "blocking") decodes uniform.
        """
        scale = self.rubric.scale_for(str(q.get("ins") or ""))
        k = len(raw)
        if scale is None or k < 2:
            return raw
        intensity, _term = Rubric.intensity(scale, state_text)
        target = intensity * (k - 1)
        sigma = 0.85 + 0.15 * (k - 2)
        out = list(raw)
        for i in range(k):
            out[i] += 2.4 * math.exp(-((i - target) ** 2) / (2 * sigma ** 2))
        return out

    def _score_noul(self, state_text: str, q: Dict[str, Any]) -> List[float]:
        docs = _docs_for(q, self.rubric)
        # Reuse the choice scorer's evidence for the two profiles, then centre.
        fake = {"t": "choice", "ins": q["ins"], "crit": {"false": docs[0], "true": docs[1]}}
        raw = self._raw_choice(state_text, fake)
        d = (raw[1] - raw[0]) * self.noul_beta - 0.35
        d = _clip(d, -8.0, 8.0)
        return [0.0, d]

    def _raw_choice(self, state_text: str, q: Dict[str, Any]) -> List[float]:
        # A shared implementation behind score()/noul; no label bonus for noul.
        docs = _docs_for(q, self.rubric)
        state_tokens_all = tokens(state_text, keep_stop=True)
        state_content = [t for t in state_tokens_all if t not in MATCH_STOP]
        state_counts: Dict[str, int] = {}
        for tok in state_content:
            state_counts[tok] = state_counts.get(tok, 0) + 1
        state_set = set(state_content)
        per_doc_terms = [_doc_terms(doc, self.rubric) for doc in docs]
        df: Dict[str, int] = {tok: 1 for tok in state_set}
        for weights, _ in per_doc_terms:
            for tok in weights:
                df[tok] = df.get(tok, 0) + 1
        n_docs = len(docs) + 1
        idf = {tok: math.log((n_docs + 1) / (count + 0.5)) + 0.1 for tok, count in df.items()}
        state_tri = _trigrams(state_text)
        raw = []
        for doc, (weights, _) in zip(docs, per_doc_terms):
            score = 0.0
            for tok, count in state_counts.items():
                weight = weights.get(tok)
                if weight is None:
                    continue
                contribution = idf.get(tok, 0.5) * weight * (1.0 + 0.35 * math.log(count))
                if self._negated(state_tokens_all, tok):
                    contribution *= -self.negation_penalty
                score += contribution
            if state_tri:
                score += self.trigram_weight * dice(state_tri, _trigrams(doc))
            raw.append(score)
        return raw

    def _negated(self, state_tokens: List[str], token: str) -> bool:
        window = 3
        for i, candidate in enumerate(state_tokens):
            if candidate != token:
                continue
            lo = max(0, i - window)
            if any(t in NEGATORS for t in state_tokens[lo:i]):
                return True
        return False

    def _to_logits(self, raw: Sequence[float]) -> List[float]:
        """Centre the evidence and keep its magnitude.

        Earlier this divided by the mean absolute deviation, which made two
        options always land on +/-beta however strong the evidence was - a
        two-option choice could never be more confident than 0.75 (at T=1) and
        a temperature could only move that constant. Scaling the raw margin
        instead keeps "this state names the option" distinguishable from
        "this state mentions one word".
        """
        k = len(raw)
        if k == 0:
            return []
        mean = sum(raw) / k
        if max(raw) - min(raw) < 0.15:
            return [0.0] * k
        return [_clip((v - mean) * self.beta, -8.0, 8.0) for v in raw]


__all__ = ["Rubric", "LexicalScorer", "tokens", "token_set", "dice"]
