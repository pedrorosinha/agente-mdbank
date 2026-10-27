import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

import numpy as np
from google.protobuf.json_format import MessageToDict
from google.protobuf.message import Message as ProtobufMessage
from pydantic import BaseModel
from rank_bm25 import BM25Okapi

AGENT_REGISTRY = {}

BM25_INDEX = None
BM25_KEYS = []

BOOST_TOOL = 0.05


# ----------------------------------------
# SERIALIZAÇÃO
# ----------------------------------------


def to_json_compatible(value: Any, path: str = "result"):
    """
    Converte objetos comuns do A2A, MCP, NumPy
    e Pydantic para tipos compatíveis com JSON.

    Tipos desconhecidos produzem erro com o caminho
    exato do campo problemático.
    """

    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, np.generic):
        return to_json_compatible(value.item(), path)

    if isinstance(value, np.ndarray):
        return to_json_compatible(value.tolist(), path)

    if isinstance(value, ProtobufMessage):
        return MessageToDict(
            value,
            preserving_proto_field_name=True,
        )

    if isinstance(value, BaseModel):
        return to_json_compatible(
            value.model_dump(mode="json"),
            path,
        )

    if isinstance(value, Enum):
        return to_json_compatible(value.value, path)

    if is_dataclass(value) and not isinstance(value, type):
        return to_json_compatible(asdict(value), path)

    if isinstance(value, Mapping):
        return {
            str(key): to_json_compatible(
                item,
                f"{path}.{key}",
            )
            for key, item in value.items()
        }

    if isinstance(value, (Sequence, set)) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        return [
            to_json_compatible(
                item,
                f"{path}[{index}]",
            )
            for index, item in enumerate(value)
        ]

    raise TypeError(
        f"Tipo não serializável em {path}: "
        f"{type(value).__module__}.{type(value).__name__}"
    )


# ----------------------------------------
# NORMALIZAÇÃO
# ----------------------------------------


def normalize(text: str) -> str:
    if not text:
        return ""

    text = str(text).lower().strip()

    text = unicodedata.normalize("NFD", text)

    text = text.encode(
        "ascii",
        "ignore",
    ).decode("utf-8")

    return text


def tokenize(text: str):
    return re.findall(
        r"\w+",
        normalize(text),
    )


# ----------------------------------------
# CONSTRUÇÃO DO ÍNDICE
# ----------------------------------------


def build_index():
    global BM25_INDEX, BM25_KEYS

    corpus = []
    keys = []

    for skill_id, data in AGENT_REGISTRY.items():
        search_text = data.get("search_text")

        if not search_text:
            search_text = " ".join(
                [
                    str(data.get("name", "")),
                    str(data.get("description", "")),
                    " ".join(str(tag) for tag in data.get("tags", [])),
                ]
            )

        tokens = tokenize(search_text)

        if not tokens:
            continue

        corpus.append(tokens)
        keys.append(skill_id)

    BM25_KEYS = keys

    if corpus:
        BM25_INDEX = BM25Okapi(corpus)
    else:
        BM25_INDEX = None


# ----------------------------------------
# BUSCA BM25
# ----------------------------------------


def search_bm25(
    query: str,
    top_k: int = 3,
    filter_type: str | None = None,
):
    if BM25_INDEX is None:
        return []

    if top_k <= 0:
        return []

    tokens = tokenize(query)

    if not tokens:
        return []

    scores = BM25_INDEX.get_scores(tokens)

    if len(scores) == 0:
        return []

    max_score = float(np.max(scores))

    if max_score <= 0:
        return []

    ranked_idx = np.argsort(scores)[::-1]

    results = []

    for idx in ranked_idx:
        idx = int(idx)

        skill_id = BM25_KEYS[idx]

        data = AGENT_REGISTRY[skill_id]

        if filter_type and data.get("type") != filter_type:
            continue

        raw_score = float(scores[idx])

        if raw_score <= 0:
            continue

        norm_score = float(raw_score / max_score)

        if not filter_type and data.get("type") == "tool":
            norm_score = min(
                norm_score + BOOST_TOOL,
                1.0,
            )

        results.append(
            {
                "skill": str(skill_id),
                "score": raw_score,
                "normalized_score": float(norm_score),
                "type": str(data.get("type", "agent")),
                "data": to_json_compatible(
                    data,
                    f"registry.{skill_id}",
                ),
            }
        )

        if len(results) >= top_k:
            break

    return results


# ----------------------------------------
# RESOLUÇÃO SEMÂNTICA
# ----------------------------------------


def resolve_agent(
    query: str,
    top_k: int = 3,
    threshold: float = 0.3,
    filter_type: str | None = None,
):
    results = search_bm25(
        query=query,
        top_k=top_k,
        filter_type=filter_type,
    )

    if not results:
        return None

    best = results[0]

    if best["normalized_score"] < threshold:
        return {
            "type": "no_confident_match",
            "best": None,
            "candidates": results,
        }

    return {
        "type": "bm25",
        "best": best,
        "candidates": results,
    }
