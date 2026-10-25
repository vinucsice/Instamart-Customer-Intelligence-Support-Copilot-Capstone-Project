"""Part D, tasks 1-4 — chunk the policy documents, vectorise and retrieve with TF-IDF,
ground the answers through mock_llm and evaluate retrieval + grounding.

Run:  python -m pipeline.d_policy

The retrieval index is rebuilt here and reused by the refund agent and by the web
backend's live policy assistant (import get_index / retrieve / answer from this module).
"""

from __future__ import annotations

import json
from collections import Counter

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

import mock_llm
from pipeline.paths import POLICIES, OUTPUTS, RAW, save_metrics

CHUNK_WORDS = 40
CHUNK_OVERLAP = 10
POLICY_SYSTEM = ("You are the Instamart POLICY ASSISTANT. Answer only from the supplied context. "
                 "If the context does not contain the answer, say that you could not find that "
                 "information in the policy documents.")

_INDEX: dict | None = None


def chunk_documents(overlap: int = CHUNK_OVERLAP) -> list[dict]:
    """Split every policy file into CHUNK_WORDS-word chunks with `overlap`-word overlap.

    The first chunk covers words 0-39, the next starts 30 words later (overlap 10), and we
    stop after the first chunk whose end reaches or passes the last word of the document.
    """
    chunks = []
    for path in sorted(POLICIES.glob("*.txt")):
        words = path.read_text(encoding="utf-8").split()
        start = 0
        while True:
            piece = words[start:start + CHUNK_WORDS]
            chunks.append({"source": path.name, "text": " ".join(piece)})
            if start + CHUNK_WORDS >= len(words):
                break
            start += CHUNK_WORDS - overlap
    return chunks


def get_index(overlap: int = CHUNK_OVERLAP) -> dict:
    """Fit TfidfVectorizer on the chunk texts (rebuilt only when the overlap changes)."""
    global _INDEX
    if _INDEX is None or _INDEX["overlap"] != overlap:
        chunks = chunk_documents(overlap)
        vec = TfidfVectorizer()
        matrix = vec.fit_transform([c["text"] for c in chunks])
        _INDEX = {"overlap": overlap, "chunks": chunks, "vectorizer": vec, "matrix": matrix}
    return _INDEX


def retrieve(query: str, k: int = 3, index: dict | None = None) -> list[dict]:
    """Top-k chunks for a query: [{source, score, text}], best first."""
    idx = index or get_index()
    scores = cosine_similarity(idx["vectorizer"].transform([query]), idx["matrix"]).ravel()
    order = scores.argsort()[::-1][:k]
    return [{"source": idx["chunks"][i]["source"], "score": round(float(scores[i]), 4),
             "text": idx["chunks"][i]["text"]} for i in order]


def answer(question: str, index: dict | None = None) -> tuple[str, list[str]]:
    """Retrieve three chunks and ask the grounded policy assistant; return (text, sources)."""
    chunks = retrieve(question, k=3, index=index)
    context = "\n".join(f"[{c['source']}] {c['text']}" for c in chunks)
    user = f"CONTEXT:\n{context}\nQUESTION:\n{question}"
    response = mock_llm.chat([
        {"role": "system", "content": POLICY_SYSTEM},
        {"role": "user", "content": user},
    ])
    return response.choices[0].message.content, [c["source"] for c in chunks]


def evaluate(overlap: int) -> dict:
    """Run the 14 policy_eval questions against an index built with the given overlap."""
    idx = get_index(overlap)
    rows = []
    for q in pd.read_csv(RAW / "policy_eval.csv", keep_default_na=False).itertuples():
        text, sources = answer(q.question, index=idx)
        row = {"question": q.question, "expected_doc": q.expected_doc, "expected_fact": q.expected_fact,
               "sources": sources, "answer": text}
        if q.expected_doc == "NONE":
            row["fallback_hit"] = text.startswith("I could not find")
            row["doc_hit"] = row["fact_hit"] = None
        else:
            row["doc_hit"] = q.expected_doc in sources
            row["fact_hit"] = q.expected_fact in text
            row["fallback_hit"] = None
        rows.append(row)

    answerable = [r for r in rows if r["expected_doc"] != "NONE"]
    unanswerable = [r for r in rows if r["expected_doc"] == "NONE"]
    return {
        "overlap": overlap,
        "doc_hits": sum(r["doc_hit"] for r in answerable),
        "fact_hits": sum(r["fact_hit"] for r in answerable),
        "fallback_hits": sum(r["fallback_hit"] for r in unanswerable),
        "answerable": len(answerable),
        "unanswerable": len(unanswerable),
        "rows": rows,
        "failures": [r for r in rows if r["expected_doc"] != "NONE" and not (r["doc_hit"] and r["fact_hit"])],
    }


def main() -> None:
    chunks = chunk_documents()
    counts = Counter(c["source"] for c in chunks)
    sample = retrieve("refund policy late delivery", k=3)

    eval10 = evaluate(CHUNK_OVERLAP)
    eval0 = evaluate(0)

    assert sum(counts.values()) == 15 and counts["refund_policy.txt"] == 4 and counts["privacy_policy.txt"] == 2, counts
    assert eval10["doc_hits"] == 12 and eval10["fact_hits"] == 12 and eval10["fallback_hits"] == 2
    assert len(eval0["failures"]) >= 1, "the zero-overlap run must break at least one question"
    assert all(r["source"] == "refund_policy.txt" for r in sample)

    metrics = {
        "total_chunks": sum(counts.values()),
        "chunk_counts": dict(counts),
        "tfidf_explanation": ("TF measures how often a word occurs inside a chunk; IDF down-weights words that "
                              "occur across many chunks, so policy-specific terms drive the similarity. "
                              "Limitation: TF-IDF is purely lexical, so two phrasings with the same meaning but "
                              "different words ('money back' vs 'refund') never match."),
        "retrieval_sample": {"query": "refund policy late delivery", "sources": [r["source"] for r in sample]},
        "eval_overlap10": eval10, "eval_overlap0": eval0,
        "zero_overlap_reading": ("With 40-word chunks and zero overlap at least one answerable question breaks "
                                 "because its answer sentence straddles a chunk boundary, so the retrieved "
                                 "chunks never contain the complete sentence that holds the expected fact."),
    }
    save_metrics("policy", metrics)
    OUTPUTS.joinpath("policy_eval_results.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"chunks={sum(counts.values())} {dict(counts)}")
    print(f"overlap10: docs {eval10['doc_hits']}/12 facts {eval10['fact_hits']}/12 fallback {eval10['fallback_hits']}/2")
    print(f"overlap0: failures {len(eval0['failures'])} -> {[r['question'] for r in eval0['failures']]}")


if __name__ == "__main__":
    main()
