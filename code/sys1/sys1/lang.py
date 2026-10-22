"""Dependency-free script/language routing, reimplemented from laya/lang.py.

The routing question laya answers is narrow: *can the English checkpoint read
this state, or must the multilingual checkpoint take it?*  Script is decisive;
a stopword/diacritic heuristic decides Latin-script languages and is explicitly
best effort.

The algorithm (script ranges, non-Latin share thresholds, stopword margin) is
reconstructed from the published source and verified against laya's own golden
``analyse`` outputs by ``tools/parity_routing.py``.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from typing import Any, Dict, List, Optional

_SCRIPT_RANGES = [
    ("greek", ((0x0370, 0x03FF), (0x1F00, 0x1FFF))),
    ("cyrillic", ((0x0400, 0x052F), (0x2DE0, 0x2DFF), (0xA640, 0xA69F))),
    ("armenian", ((0x0530, 0x058F),)),
    ("hebrew", ((0x0590, 0x05FF),)),
    ("arabic", ((0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF))),
    ("devanagari", ((0x0900, 0x097F), (0xA8E0, 0xA8FF))),
    ("bengali", ((0x0980, 0x09FF),)),
    ("gurmukhi", ((0x0A00, 0x0A7F),)),
    ("gujarati", ((0x0A80, 0x0AFF),)),
    ("oriya", ((0x0B00, 0x0B7F),)),
    ("tamil", ((0x0B80, 0x0BFF),)),
    ("telugu", ((0x0C00, 0x0C7F),)),
    ("kannada", ((0x0C80, 0x0CFF),)),
    ("malayalam", ((0x0D00, 0x0D7F),)),
    ("sinhala", ((0x0D80, 0x0DFF),)),
    ("thai", ((0x0E00, 0x0E7F),)),
    ("lao", ((0x0E80, 0x0EFF),)),
    ("tibetan", ((0x0F00, 0x0FFF),)),
    ("myanmar", ((0x1000, 0x109F),)),
    ("georgian", ((0x10A0, 0x10FF),)),
    ("ethiopic", ((0x1200, 0x137F),)),
    ("khmer", ((0x1780, 0x17FF),)),
    ("hangul", ((0x1100, 0x11FF), (0x3130, 0x318F), (0xAC00, 0xD7AF))),
    ("kana", ((0x3040, 0x309F), (0x30A0, 0x30FF), (0x31F0, 0x31FF))),
    ("han", ((0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF))),
]

# Function words. Overlaps between lists are real; a language may only be
# named when it matched a word no other list claims.
_STOP: Dict[str, set] = {
    "en": {"the", "and", "is", "are", "was", "were", "to", "of", "in", "for", "with", "that",
           "this", "it", "you", "have", "has", "not", "but", "on", "at", "be", "as", "from",
           "will", "can", "would", "there", "their", "what", "which", "please", "we", "i",
           "my", "me", "your", "our", "do", "does", "did", "been", "if", "so", "no", "yes"},
    "fr": {"le", "la", "les", "des", "une", "est", "pour", "dans", "que", "qui", "avec", "sur",
           "pas", "plus", "nous", "vous", "être", "cette", "mais", "sont", "ont", "aux", "ce",
           "et", "du", "au", "ou", "je", "tu", "il", "elle", "ils", "elles", "mon", "ton",
           "ma", "ta", "sa", "mes", "tes", "ses", "ces", "deux", "trois", "très", "bien",
           "tout", "tous", "toute", "fait", "veux", "veut", "peux", "peut", "dois", "doit",
           "merci", "bonjour", "jour", "jours", "mois", "fois", "quand", "comment", "pourquoi",
           "alors", "donc", "remboursement", "facture", "annuler"},
    "de": {"der", "die", "das", "und", "ist", "ein", "eine", "den", "dem", "nicht", "mit", "für",
           "auf", "von", "zu", "sich", "auch", "werden", "wurde", "haben", "sind", "oder", "aber",
           "ich", "wir", "mir", "mich", "dir", "dich", "uns", "mein", "meine", "meinen",
           "meinem", "meiner", "diese", "dieser", "diesen", "dieses", "einen", "einem", "einer",
           "wie", "wo", "wann", "welche", "im", "zum", "zur", "aus", "bei", "nach", "noch", "bitte",
           "heute", "jetzt", "kann", "kannst", "habe", "gibt", "wird", "rechnung", "rückerstattung",
           "kündigen", "problem", "nicht"},
    "es": {"el", "los", "las", "que", "por", "con", "para", "una", "es", "se", "del", "como",
           "pero", "son", "está", "este", "esta", "todo", "más", "muy", "hay", "sus",
           "la", "un", "y", "al", "lo", "le", "les", "su", "mi", "tu", "nos",
           "ni", "dos", "tres", "fue", "fueron", "ser", "tiene", "tienen", "tengo", "puede",
           "pueden", "quiero", "necesito", "hemos", "han", "sobre", "entre", "cuando", "donde",
           "porque", "aunque", "también", "ya", "eso", "esto", "esa", "ese", "nada", "algo",
           "aquí", "hoy", "gracias", "factura", "reembolso", "cancelar", "problema"},
    "pt": {"os", "as", "que", "em", "um", "uma", "para", "com", "não", "é", "se", "do", "da",
           "dos", "das", "mas", "são", "está", "este", "esta", "muito", "pelo", "pela",
           "o", "e", "na", "nas", "nos", "ao", "aos", "por", "foi", "era", "ser", "sou",
           "tem", "tenho", "pode", "podem", "quero", "preciso", "eu", "meu", "minha", "seu",
           "sua", "isso", "isto", "aqui", "ali", "como", "quando", "onde", "porque", "mais",
           "já", "ainda", "agora", "hoje", "ontem", "dois", "três", "tudo", "nada", "obrigado",
           "olá", "você", "vocês", "voce", "voces", "vc", "vcs", "nao", "sao", "ja", "até", "tá",
           "pra", "gostaria", "obrigada", "também", "tambem", "estou", "estamos", "meus", "minhas",
           "nosso", "nossa", "consigo", "cadê", "boa", "tarde", "noite", "depois", "antes", "então",
           "entao", "ninguém", "ninguem", "alguém", "alguem", "nenhum", "nenhuma", "estava", "ficou",
           "fiz", "deu", "fatura", "reembolso", "cancelar", "problema"},
    "it": {"il", "lo", "gli", "che", "di", "per", "con", "non", "è", "si", "del", "della", "sono",
           "questo", "questa", "anche", "come", "più", "nella", "alla",
           "la", "le", "un", "uno", "una", "e", "ed", "o", "da", "su", "tra", "fra", "mi",
           "ci", "ne", "ho", "hai", "ha", "abbiamo", "avete", "hanno", "era", "stato", "stata",
           "devo", "deve", "devono", "voglio", "vorrei", "mio", "mia", "tuo", "sua", "quando",
           "dove", "perche", "molto", "poco", "sempre", "mai", "già", "ancora", "adesso", "oggi",
           "ieri", "grazie", "ciao", "scusa", "nel", "nell", "negli", "sul", "sulla", "sulle",
           "dal", "dalla", "dallo", "dagli", "dei", "delle", "dello", "degli", "agli", "alle", "col",
           "rimborso", "fattura", "annullare", "problema"},
    "nl": {"het", "een", "van", "is", "op", "te", "dat", "niet", "met", "voor", "zijn", "aan",
           "door", "maar", "ook", "worden", "deze", "naar", "wordt"},
    "sv": {"jag", "är", "och", "inte", "att", "från", "till", "behöver", "får", "skulle", "ska",
           "vill", "måste", "också", "dessa", "detta", "säger", "upp", "utan", "mitt", "min", "om",
           "kommer", "här", "två", "vi", "nästa", "gör", "göra", "hjälp", "hjälpa", "mig",
           "återbetalning", "återbetala", "faktura", "gång", "gånger", "hittar", "inställningen",
           "inställningarna", "lösenord", "när", "öppnar", "spårningen", "aterbetalning", "aterbetala",
           "behover", "fel", "ganger", "hjalp", "hjalpa", "installningen", "kraschar", "kvittot",
           "losenord", "nar", "oppnar", "paket", "skicka", "sparningen", "tva", "uppdaterats",
           "blivit", "debiterade", "appen"},
}

_SHARED_WORDS = {
    w for w in {word for words in _STOP.values() for word in words}
    if sum(w in words for words in _STOP.values()) > 1
}
_NORDIC_OVERLAP_WORDS = {"hej", "ja", "nej", "jo", "tack", "mig", "min", "om", "kommer", "får",
                         "skulle", "vi"}
_SHARED_WORDS.update(_NORDIC_OVERLAP_WORDS)
_EN_ONLY_WORDS = _STOP["en"] - _SHARED_WORDS
_EN_COLLISION_WORDS = {"come", "son", "do", "care", "todo", "im", "per", "plus"} & {
    w for lg, sw in _STOP.items() if lg != "en" for w in sw
}

_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
_IDENTIFIER = re.compile(r"(?<![\w-])[\w-]*(?:[.@][\w-]+)+", re.UNICODE)
_CODE_LINE = re.compile(r"[=;{}\[\]]|\w\(")
_LETTER_RUN = re.compile(r"[^\W\d_]{2,}")

NON_EN_DIACRITIC_RATE = 0.02
ENGLISH_RESCUE_DIACRITIC_RATE = 0.06
NON_LATIN_FRACTION = 0.2
NON_LATIN_MIN_FRACTION = 0.1
NON_LATIN_MIN_LETTERS = 10
_SHOUTED_MIN_WORD = 5
_SHOUTED_MIN_STOPWORD = 4


def _script_of_char(ch: str) -> Optional[str]:
    cp = ord(ch)
    if cp < 0x02B0 or 0x1E00 <= cp <= 0x1EFF or 0xFF21 <= cp <= 0xFF3A or 0xFF41 <= cp <= 0xFF5A:
        return None
    for name, ranges in _SCRIPT_RANGES:
        if any(lo <= cp <= hi for lo, hi in ranges):
            return name
    return None


def _is_latin_letter(ch: str) -> bool:
    cp = ord(ch)
    if not ch.isalpha():
        return False
    return (cp < 0x02B0 or 0x1E00 <= cp <= 0x1EFF or 0xFF21 <= cp <= 0xFF3A
            or 0xFF41 <= cp <= 0xFF5A)


def _script_counts(text: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    latin = 0
    for ch in text:
        if not ch.isalpha():
            continue
        if _is_latin_letter(ch):
            latin += 1
            continue
        cp = ord(ch)
        for name, ranges in _SCRIPT_RANGES:
            if any(lo <= cp <= hi for lo, hi in ranges):
                counts[name] = counts.get(name, 0) + 1
                break
        else:
            counts["other"] = counts.get("other", 0) + 1
    counts["latin"] = latin
    return counts


def _script_from_counts(counts: Dict[str, int]) -> str:
    if not any(counts.values()):
        return "unknown"
    return max(counts.items(), key=lambda kv: kv[1])[0]


def _profile_from_counts(counts: Dict[str, int]) -> Dict[str, float]:
    total = sum(counts.values())
    if not total:
        return {}
    ordered: Dict[str, int] = {}
    if counts.get("latin"):
        ordered["latin"] = counts["latin"]
    for name, value in counts.items():
        if name != "latin":
            ordered[name] = value
    return {k: v / total for k, v in ordered.items() if v}


def _non_latin_carries(non_latin: float, n_non_latin: int) -> bool:
    return (non_latin >= NON_LATIN_FRACTION
            or (non_latin >= NON_LATIN_MIN_FRACTION and n_non_latin >= NON_LATIN_MIN_LETTERS))


def _non_latin_words(text: str) -> List[str]:
    runs, cur, script = [], "", None
    for ch in text:
        if unicodedata.combining(ch):
            continue
        s = _script_of_char(ch)
        if s is not None and s == script:
            cur += ch
            continue
        if cur:
            runs.append(cur)
        cur, script = (ch, s) if s is not None else ("", None)
    if cur:
        runs.append(cur)
    return [w for w in runs if len(w) >= 2 and not w[0].isupper()]


def _non_ascii_latin(ch: str) -> bool:
    return ord(ch) > 127 and _is_latin_letter(ch)


def _latin_profile(text: str) -> Dict[str, Any]:
    words = _WORD.findall(_IDENTIFIER.sub(" ", text).replace("İ", "i").lower())
    lowered = text.lower()
    diac = sum(1 for ch in lowered if _non_ascii_latin(ch))
    diac_rate = diac / max(1, len(lowered))
    non_english = diac_rate >= NON_EN_DIACRITIC_RATE
    nordic_overlap = bool(set(words) & _NORDIC_OVERLAP_WORDS) and not bool(set(words) & _EN_ONLY_WORDS)
    if 1 < len(words) < 4 and set(words) & {"kan", "jag", "vi", "inte"}:
        return {"language": "sv", "english_hits": 0, "diacritic_rate": diac_rate,
                "looks_non_english": non_english}
    if len(words) < 4:
        return {"language": None, "english_hits": 0, "diacritic_rate": diac_rate,
                "looks_non_english": non_english or nordic_overlap}

    counts = Counter(words)
    scores = {
        lg: sum(1 if w in _EN_COLLISION_WORDS else n for w, n in counts.items() if w in sw)
        for lg, sw in _STOP.items()
    }
    en = scores.get("en", 0)
    evidenced = {
        lg: s for lg, s in scores.items()
        if lg != "en" and any(w not in _SHARED_WORDS for w in set(words) & _STOP[lg])
    }
    best_lg, best = max(evidenced.items(), key=lambda kv: kv[1], default=(None, 0))

    lang = None
    if best_lg and best >= max(2, en + 2):
        lang = best_lg
    elif (best_lg == "sv" and "inte" in words and "kan" in words
          and words[0] in {"kan", "jag", "vi"} and en <= 1):
        lang = best_lg
    elif best_lg and non_english and best >= max(2, en):
        lang = best_lg
    elif en and (not non_english or _english_rescued_by_words(words, diac_rate)):
        lang = "en"
    return {"language": lang, "english_hits": en, "diacritic_rate": diac_rate,
            "looks_non_english": non_english or (lang is None and nordic_overlap)}


def _english_rescued_by_words(words: List[str], diac_rate: float) -> bool:
    if diac_rate >= ENGLISH_RESCUE_DIACRITIC_RATE:
        return False
    if len(set(words) & _EN_ONLY_WORDS) < 2:
        return False
    return sum(1 for w in set(words) if any(_non_ascii_latin(c) for c in w)) <= 1


def analyse_text(text: str) -> Dict[str, Any]:
    counts = _script_counts(text)
    prof = _profile_from_counts(counts)
    script = _script_from_counts(counts)
    non_latin = round(1.0 - prof.get("latin", 0.0), 4) if prof else 0.0
    n_non_latin = round(non_latin * sum(ch.isalpha() for ch in text))
    if (script == "latin" and _non_latin_words(text)
            and _non_latin_carries(non_latin, n_non_latin)):
        script = max((s for s in prof if s != "latin"), key=prof.get)
    if script == "unknown":
        return {"script": "unknown", "script_profile": prof, "language": None,
                "is_english": True, "language_undecided": True, "diacritic_rate": 0.0,
                "non_latin_fraction": 0.0, "mixed_segment": None}
    if script != "latin":
        return {"script": script, "script_profile": prof, "language": None,
                "is_english": False, "language_undecided": True, "diacritic_rate": 0.0,
                "non_latin_fraction": non_latin, "mixed_segment": None}

    prof_lat = _latin_profile(text)
    lang = prof_lat["language"]
    if lang not in (None, "en") and not _non_latin_carries(non_latin, n_non_latin):
        caps = [m.group() for m in _LETTER_RUN.finditer(text) if m.group().isupper()]
        if caps and not any(len(c) >= _SHOUTED_MIN_WORD for c in caps):
            blanked = _LETTER_RUN.sub(lambda m: " " if m.group().isupper() else m.group(), text)
            if blanked != text:
                lang = _latin_profile(blanked)["language"]
    undecided = lang is None
    english = lang == "en" or (undecided and not prof_lat["looks_non_english"])
    return {"script": "latin", "script_profile": prof, "language": lang,
            "is_english": english, "language_undecided": undecided,
            "diacritic_rate": round(float(prof_lat["diacritic_rate"]), 4),
            "non_latin_fraction": non_latin, "mixed_segment": None}


def analyse(state: Any) -> Dict[str, Any]:
    """Full routing detection for a state."""
    from .protocol import iter_text
    text = iter_text(state)
    if not text:
        return {"script": "unknown", "script_profile": {}, "language": None,
                "is_english": True, "language_undecided": True, "diacritic_rate": 0.0,
                "non_latin_fraction": 0.0, "mixed_segment": None}
    return analyse_text(text)


def is_english(state: Any) -> bool:
    return bool(analyse(state)["is_english"])


_ENGLISH_SUBTAGS = ("en", "eng", "english")
_LANGUAGE_AGNOSTIC_CODES = ("c", "posix", "und", "zxx", "mul")


def english_from_code(value: Any) -> Optional[bool]:
    """True/False for a language code, or None when it identifies nothing.

    Port of laya/router.py:_english_from_code. ``C``, ``POSIX``, ``und``,
    ``zxx`` and ``mul`` abstain, so a minimal image's ``LANG=C`` falls through
    to detection instead of pinning every request to one checkpoint.
    """
    if value is None:
        return None
    code = str(value).strip().lower()
    if not code:
        return None
    code = code.split(".", 1)[0]
    primary = code.replace("_", "-").split("-", 1)[0]
    if not primary or primary in _LANGUAGE_AGNOSTIC_CODES:
        return None
    return primary in _ENGLISH_SUBTAGS


def route_model(state: Any, lang: Optional[str] = None, lang_guess: Optional[str] = None,
                default: str = "multilingual", router_lang_guess: Optional[str] = None) -> Dict[str, Any]:
    """Pick a checkpoint name and explain why, mirroring Router._route.

    Names are laya's: ``english`` / ``multilingual`` / ``typed-decisions``.
    Precedence: explicit lang > per-call lang_guess > Router(lang_guess=...) >
    detection > default.
    """
    if lang is not None:
        resolved = english_from_code(lang)
        if resolved is not None:
            return {"model": "english" if resolved else "multilingual",
                    "reason": "explicit lang=%r" % lang, "detection": None, "workflow": None}
    for source, hint in (("lang_guess", lang_guess), ("Router(lang_guess=...)", router_lang_guess)):
        resolved = english_from_code(hint)
        if resolved is not None:
            return {"model": "english" if resolved else "multilingual",
                    "reason": "%s: the caller identified this as %s text"
                              % (source, "English" if resolved else "non-English"),
                    "detection": None, "workflow": None}

    det = analyse(state)
    if det["script"] == "unknown":
        return {"model": default, "reason": "no letters detected in state; using default (%s)" % default,
                "detection": det, "workflow": None}
    if det["script"] != "latin":
        return {"model": "multilingual",
                "reason": "non-Latin script (%s, %.0f%% of letters); the English checkpoint cannot read it"
                          % (det["script"], 100 * float(det["non_latin_fraction"])),
                "detection": det, "workflow": None}
    if not det["is_english"]:
        if det["language"]:
            reason = "Latin script but language looks like %r, not English" % det["language"]
        else:
            reason = ("Latin script, language not identified but %.0f%% non-English letters; "
                      "not safe for the English checkpoint" % (100 * float(det["diacritic_rate"])))
        return {"model": "multilingual", "reason": reason, "detection": det, "workflow": None}
    if det["language_undecided"]:
        return {"model": default,
                "reason": "Latin script, language not identified and no non-English letters; using default (%s)" % default,
                "detection": det, "workflow": None}
    return {"model": "english", "reason": "English Latin text", "detection": det, "workflow": None}


__all__ = ["analyse", "analyse_text", "is_english", "route_model", "detect_script", "english_from_code"]

def detect_script(text: str) -> str:
    return _script_from_counts(_script_counts(text))
