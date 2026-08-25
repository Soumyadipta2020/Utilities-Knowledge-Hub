"""
Document RAG retriever - the retrieval engine behind the *baseline* arm of the
side-by-side comparison.

This is a deliberately conventional RAG stack, and a deliberately *capable* one:
the corpus is knowledge base articles, business-rule/metric definitions **and
flat reporting extracts pre-aggregated from the datasets themselves** (weekly
volumes, category distributions, dataset profiles) - the kind of BI export a real
enterprise RAG index is built over. Everything is chunked, vectorised as TF-IDF
and searched by cosine similarity; top-k chunks go into the prompt.

So the baseline can answer a data question with real figures. What it cannot do
is the whole point of the comparison:

  * no knowledge graph - chunks are flat and unrelated, so nothing can be
    traversed from one entity to another (dataset -> owner -> platform -> tier,
    or appointments -> region -> weather -> engineer shifts);
  * every extract is single-dataset, so no join is possible. It can report
    *gross* weekly appointments from appointment_schedule, but "net" needs the
    cancellation and no-access statuses that live in visit_outcome, keyed by
    job_id - a relationship only the graph holds. Its answer is therefore
    numerically real, slightly wrong for the question asked, and unverifiable;
  * pre-aggregated, so it cannot re-cut by a dimension nobody exported (region,
    weather, engineer shift) or drill into a specific week;
  * single hop, single shot - one retrieval, one answer, no tool loop.

TF-IDF rather than a hosted embedding model keeps retrieval deterministic and
dependency-free, which matters for a demo that has to behave the same way every
time it is shown. The retrieval *behaviour* being illustrated - lexical/semantic
chunk matching with no relationship awareness - is identical either way.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from math import log, sqrt
from pathlib import Path
from threading import Lock
from typing import Any, Iterable
import json
import re

import pandas as pd

# Roughly 300 tokens - a conventional RAG chunk size, and wide enough to hold a
# full quarter of weekly figures in one piece rather than splitting a series.
MAX_CHUNK_CHARS = 1200

# At most this many chunks from any one source may occupy the top-k. Without a cap
# a single 26-week series monopolises every slot with near-identical chunks and
# crowds out the outcome mix - the classic redundancy failure of plain top-k.
MAX_CHUNKS_PER_SOURCE = 2

# Below this cosine score a chunk is noise rather than context. Passing noise to
# the model is what produces confident, wrong RAG answers.
MIN_SIMILARITY = 0.04

STOPWORDS = frozenset("""
a an and are as at be been but by can could did do does for from had has have how
i if in into is it its me my of on or our over should show so than that the their
them then there these they this to was were what when where which who why will with
would you your me tell give list please
""".split())

# Reporting extracts the RAG index is built over. Each one is deliberately
# derived from a SINGLE dataset - that is what makes the baseline's numbers real
# but its answers incomplete. The governance register (dataset_ownership) stays
# out of the corpus entirely: ownership, platform and tier are relationships, and
# relationships belong to the knowledge graph.
EXTRACT_SPECS: tuple[dict[str, Any], ...] = (
    {
        "dataset": "appointment_schedule",
        "date_col": "appointment_date",
        "title": "Weekly Appointment Volume Extract",
        "measure": "appointments booked",
        "weeks": 26,
        "category_cols": ("job_category", "severity"),
    },
    {
        # No weekly series: visit_date mirrors appointment_date row for row, so a
        # second identical trend would only crowd the top-k. What this dataset
        # uniquely contributes to the corpus is the outcome mix - and only as a
        # whole-period total, since netting it off per week needs the job_id join.
        "dataset": "visit_outcome",
        "date_col": "visit_date",
        "title": "Engineer Visit Outcome Extract",
        "measure": "engineer visits recorded",
        "weeks": 26,
        "weekly": False,
        "category_cols": ("visit_status",),
    },
    {
        "dataset": "engineer_productivity",
        "date_col": "shift_date",
        "title": "Weekly Engineer Shift Extract",
        "measure": "engineer shifts logged",
        "weeks": 26,
        "category_cols": (),
    },
)

# One quarter of weekly figures per chunk, so "the past 3 months" lands in a
# single retrievable chunk rather than straddling two.
WEEKS_PER_CHUNK = 13

# Extracts are cached so only the first boot after a data change pays the
# aggregation cost (a few seconds over ~5M rows per dataset).
EXTRACT_CACHE_FILE = ".rag_data_extracts.json"

# Files that make up the unstructured document corpus a RAG chatbot would index.
CORPUS_FILES: tuple[dict[str, str], ...] = (
    {
        "file": "knowledge_base.csv",
        "label": "Knowledge Base article",
        "id_col": "doc_id",
        "title_col": "title",
        "body_col": "content",
    },
    {
        "file": "business_rules.csv",
        "label": "Business rule / metric definition",
        "id_col": "rule_id",
        "title_col": "rule_name",
        "body_col": "description",
    },
)


def _singularize(token: str) -> str:
    """Crude plural stripping. Enough to match 'appointments' to 'appointment'."""
    if len(token) <= 3 or not token.endswith("s") or token.endswith("ss"):
        return token
    if token.endswith("ies"):
        return token[:-3] + "y"
    if token.endswith(("ches", "shes", "sses", "xes", "zes")):
        return token[:-2]
    return token[:-1]


def _tokenize(text: str) -> list[str]:
    """Lowercase, split, singularize.

    Identifiers such as `customer_master` are indexed both whole and split, so a
    question about `customer_master` still matches prose about "customer master".
    """
    tokens: list[str] = []
    for raw in re.findall(r"[a-z0-9_]+", str(text).casefold()):
        parts = [raw] if "_" not in raw else [raw, *raw.split("_")]
        for part in parts:
            if len(part) > 1 and part not in STOPWORDS:
                stem = _singularize(part)
                if stem not in STOPWORDS:
                    tokens.append(stem)
    return tokens


def _split_chunks(text: str) -> list[str]:
    """Split an over-long document on sentence boundaries, greedily packed."""
    text = " ".join(str(text).split())
    if len(text) <= MAX_CHUNK_CHARS:
        return [text] if text else []

    chunks: list[str] = []
    current = ""
    for sentence in re.split(r"(?<=[.;])\s+", text):
        if current and len(current) + len(sentence) + 1 > MAX_CHUNK_CHARS:
            chunks.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        chunks.append(current)
    return chunks


def _drop_partial_tail(series: list[tuple[str, int]]) -> list[tuple[str, int]]:
    """Drop a trailing part-week so the extract does not read as a collapse.

    The datasets end mid-week, which leaves a final bucket holding a day or two of
    rows. Reporting that as a week would put a fake cliff at the end of the trend
    for both arms to explain.
    """
    if len(series) < 4:
        return series
    volumes = sorted(volume for _, volume in series)
    median = volumes[len(volumes) // 2]
    while series and series[-1][1] < median * 0.4:
        series = series[:-1]
    while series and series[0][1] < median * 0.4:
        series = series[1:]
    return series


def _render_extract(spec: dict[str, Any], aggregate: dict[str, Any]) -> list[dict[str, str]]:
    """One extract becomes a profile document, weekly series documents and a mix.

    Every figure here is real, computed over every row of ONE dataset. That
    single-source boundary is deliberate: it is what leaves the baseline reporting
    gross volumes it cannot net off, and totals it cannot cut by region.
    """
    dataset = aggregate["dataset"]
    series: list[tuple[str, int]] = [tuple(item) for item in aggregate["series"]]  # type: ignore[misc]
    documents: list[dict[str, str]] = []
    source = f"{dataset}.csv (reporting extract)"
    doc_type = "Reporting extract - single dataset, gross"

    period = (
        f"{series[0][0]} to {series[-1][0]}" if series else "whole-period totals only"
    )
    documents.append({
        "doc_id": f"EXT-{dataset}-profile",
        "title": f"{spec['title']}: dataset profile",
        "doc_type": doc_type,
        "source": source,
        "body": (
            f"Reporting extract profile for the {dataset} dataset. "
            f"Total rows: {_fmt(aggregate['rows'])}. "
            f"Reporting period covered: {period}. "
            f"Date column: {spec['date_col']}. "
            f"Columns available in this extract: {', '.join(aggregate['columns'])}. "
            f"Measure: {spec['measure']}, counted gross from {dataset} only. "
            "This extract is a pre-aggregated single-dataset export: it contains no "
            "keys or columns from any other dataset, so it cannot be joined, "
            "filtered by another dataset's status, or re-cut by region, weather, "
            "customer or engineer attributes."
        ),
    })

    for start in range(0, len(series), WEEKS_PER_CHUNK):
        window = series[start:start + WEEKS_PER_CHUNK]
        lines = "; ".join(
            f"week commencing {week}: {_fmt(volume)}" for week, volume in window
        )
        total = sum(volume for _, volume in window)
        documents.append({
            "doc_id": f"EXT-{dataset}-weekly-{start // WEEKS_PER_CHUNK + 1}",
            "title": (
                f"{spec['title']}: weekly trend {window[0][0]} to {window[-1][0]}"
            ),
            "doc_type": doc_type,
            "source": source,
            "body": (
                f"Weekly gross {spec['measure']} from {dataset}, "
                f"per week commencing Monday, covering {window[0][0]} to {window[-1][0]} "
                f"({len(window)} weeks, {_fmt(total)} in total). {lines}. "
                "These are gross counts of every row in the period: no cancellations, "
                "no-access visits or any other outcome have been excluded, because "
                "outcome status is not part of this extract."
            ),
        })

    for column, pairs in (aggregate.get("categories") or {}).items():
        total = sum(volume for _, volume in pairs) or 1
        breakdown = "; ".join(
            f"{value}: {_fmt(volume)} ({volume / total * 100:.1f}%)" for value, volume in pairs
        )
        documents.append({
            "doc_id": f"EXT-{dataset}-{column}",
            "title": f"{spec['title']}: {column.replace('_', ' ')} distribution",
            "doc_type": doc_type,
            "source": source,
            "body": (
                f"Distribution of {column.replace('_', ' ')} across the whole "
                f"{dataset} dataset ({_fmt(total)} rows). {breakdown}. "
                "This is a whole-period total only. The extract holds no weekly, "
                "regional or per-job breakdown of these categories, and no key that "
                "would let them be matched to rows in another dataset."
            ),
        })

    return documents


def _fmt(value: Any) -> str:
    """Thousands-separated integers; everything else passed through."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number.is_integer():
        return f"{int(number):,}"
    return f"{number:,.1f}"


def _as_date(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y-%m-%d")
    return str(value)[:10]


class RagService:
    """TF-IDF retriever over the knowledge documents plus flat data extracts."""

    def __init__(self, data_dir: Path, sql_service: Any = None) -> None:
        self.data_dir = Path(data_dir)
        self._sql_service = sql_service
        self._lock = Lock()
        self._chunks: list[dict[str, Any]] | None = None
        self._idf: dict[str, float] = {}
        self._documents = 0
        self._extract_datasets: list[str] = []

    # ------------------------------------------------------------------ index

    def _read(self, filename: str) -> pd.DataFrame:
        path = self.data_dir / filename
        if not path.exists():
            return pd.DataFrame()
        try:
            return pd.read_csv(path)
        except Exception:  # noqa: BLE001 - a bad corpus file must not break chat
            return pd.DataFrame()

    def _sql(self) -> Any:
        if self._sql_service is None:
            from app.services.sql_service import get_sql_service

            self._sql_service = get_sql_service(self.data_dir)
        return self._sql_service

    # ------------------------------------------------- pre-aggregated extracts

    def _fingerprint(self, spec: dict[str, Any]) -> str:
        """Identify the source file's state so a cached extract can be trusted."""
        path = self.data_dir / f"{spec['dataset']}.csv"
        try:
            stat = path.stat()
        except OSError:
            return "missing"
        return f"{int(stat.st_mtime)}:{stat.st_size}:{spec['weeks']}"

    def _load_extract_cache(self) -> dict[str, Any]:
        path = self.data_dir / EXTRACT_CACHE_FILE
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except Exception:  # noqa: BLE001 - a corrupt cache is simply rebuilt
            return {}

    def _save_extract_cache(self, cache: dict[str, Any]) -> None:
        try:
            with open(self.data_dir / EXTRACT_CACHE_FILE, "w", encoding="utf-8") as handle:
                json.dump(cache, handle)
        except OSError:  # noqa: BLE001 - caching is an optimisation, not a requirement
            pass

    def _aggregate(self, spec: dict[str, Any]) -> dict[str, Any] | None:
        """Run the single-dataset aggregations behind one reporting extract."""
        service = self._sql()
        if service is None or not service.available:
            return None

        dataset, date_col = spec["dataset"], spec["date_col"]
        if dataset not in service.datasets:
            return None
        columns = [name for name, _ in service.columns_with_types(dataset)]
        if date_col not in columns:
            return None

        series: list[tuple[str, int]] = []
        if spec.get("weekly", True):
            series = self._weekly_series(spec, dataset, date_col)

        categories: dict[str, list[tuple[str, int]]] = {}
        for column in spec.get("category_cols", ()):
            if column not in columns:
                continue
            try:
                result = service.query(
                    f'SELECT "{column}" AS value, count(*) AS volume FROM "{dataset}" '
                    "GROUP BY 1 ORDER BY volume DESC LIMIT 12",
                    max_rows=12,
                )
            except Exception:  # noqa: BLE001 - a missing breakdown is not fatal
                continue
            if result.get("success"):
                categories[column] = [(str(row[0]), int(row[1])) for row in result["rows"]]

        return {
            "dataset": dataset,
            "date_col": date_col,
            "rows": service.row_count(dataset),
            "columns": columns,
            "series": series,
            "categories": categories,
        }

    def _weekly_series(
        self, spec: dict[str, Any], dataset: str, date_col: str
    ) -> list[tuple[str, int]]:
        service = self._sql()
        try:
            weekly = service.query(
                f'SELECT date_trunc(\'week\', CAST("{date_col}" AS DATE)) AS week, '
                f'count(*) AS volume FROM "{dataset}" '
                f'WHERE CAST("{date_col}" AS DATE) > ('
                f'  SELECT max(CAST("{date_col}" AS DATE)) FROM "{dataset}"'
                f") - INTERVAL '{int(spec['weeks'])} weeks' "
                "GROUP BY 1 ORDER BY 1",
                max_rows=spec["weeks"] + 2,
            )
        except Exception as error:  # noqa: BLE001
            print(f"[RAG Extract Error] {dataset}: {error}")
            return []
        if not weekly.get("success"):
            return []

        return _drop_partial_tail([(_as_date(row[0]), int(row[1])) for row in weekly["rows"]])

    def _extract_documents(self) -> list[dict[str, str]]:
        """Render each dataset's extract as flat, retrievable report text."""
        cache = self._load_extract_cache()
        cache_dirty = False
        documents: list[dict[str, str]] = []
        datasets: list[str] = []

        for spec in EXTRACT_SPECS:
            key = spec["dataset"]
            fingerprint = self._fingerprint(spec)
            entry = cache.get(key)
            if not entry or entry.get("fingerprint") != fingerprint:
                aggregate = self._aggregate(spec)
                if aggregate is None:
                    continue
                entry = {"fingerprint": fingerprint, "aggregate": aggregate}
                cache[key] = entry
                cache_dirty = True
            aggregate = entry["aggregate"]
            datasets.append(key)
            documents.extend(_render_extract(spec, aggregate))

        if cache_dirty:
            self._save_extract_cache(cache)

        self._extract_datasets = datasets
        return documents

    def _build_index(self) -> None:
        chunks: list[dict[str, Any]] = []
        documents = 0

        for document in self._extract_documents():
            documents += 1
            for index, piece in enumerate(_split_chunks(document["body"]), start=1):
                chunks.append({
                    "chunk_id": f"{document['doc_id']}#{index}",
                    "doc_id": document["doc_id"],
                    "title": document["title"],
                    "doc_type": document["doc_type"],
                    "source": document["source"],
                    "text": piece,
                    "_tokens": _tokenize(f"{document['title']} {document['title']} {piece}"),
                })

        for spec in CORPUS_FILES:
            frame = self._read(spec["file"])
            if frame.empty:
                continue
            for _, row in frame.iterrows():
                title = str(row.get(spec["title_col"], "")).strip()
                body = str(row.get(spec["body_col"], "")).strip()
                if not body or body.lower() == "nan":
                    continue
                documents += 1
                doc_id = str(row.get(spec["id_col"], f"DOC{documents:03d}"))
                pieces = _split_chunks(body)
                for index, piece in enumerate(pieces, start=1):
                    chunk_id = doc_id if len(pieces) == 1 else f"{doc_id}#{index}"
                    chunks.append({
                        "chunk_id": chunk_id,
                        "doc_id": doc_id,
                        "title": title or doc_id,
                        "doc_type": spec["label"],
                        "source": spec["file"],
                        "text": piece,
                        # Titles carry a lot of signal in short docs, so they are
                        # indexed alongside the body rather than only displayed.
                        "_tokens": _tokenize(f"{title} {title} {piece}"),
                    })

        total = len(chunks) or 1
        document_frequency: Counter[str] = Counter()
        for chunk in chunks:
            document_frequency.update(set(chunk["_tokens"]))

        idf = {
            term: log((1 + total) / (1 + count)) + 1.0
            for term, count in document_frequency.items()
        }

        for chunk in chunks:
            chunk["_vector"] = self._vectorize(chunk["_tokens"], idf)

        self._chunks = chunks
        self._idf = idf
        self._documents = documents

    @staticmethod
    def _vectorize(tokens: Iterable[str], idf: dict[str, float]) -> dict[str, float]:
        """Sublinear TF weighting, IDF scaling, L2 normalization."""
        counts = Counter(tokens)
        if not counts:
            return {}
        weights = {
            term: (1.0 + log(count)) * idf.get(term, 0.0)
            for term, count in counts.items()
            if idf.get(term)
        }
        norm = sqrt(sum(value * value for value in weights.values()))
        if not norm:
            return {}
        return {term: value / norm for term, value in weights.items()}

    def _ensure_index(self) -> list[dict[str, Any]]:
        with self._lock:
            if self._chunks is None:
                self._build_index()
            return self._chunks or []

    # ----------------------------------------------------------------- search

    def search(self, query: str, top_k: int = 4) -> list[dict[str, Any]]:
        """Return the top-k most similar chunks, highest cosine score first."""
        chunks = self._ensure_index()
        if not chunks:
            return []

        query_vector = self._vectorize(_tokenize(query), self._idf)
        if not query_vector:
            return []

        scored: list[tuple[float, dict[str, Any]]] = []
        for chunk in chunks:
            vector = chunk.get("_vector") or {}
            # Iterate the shorter vector; queries are far shorter than chunks.
            score = sum(weight * vector.get(term, 0.0) for term, weight in query_vector.items())
            if score >= MIN_SIMILARITY:
                scored.append((score, chunk))

        scored.sort(key=lambda pair: pair[0], reverse=True)

        # Take best-first, but cap each source so one long series cannot fill the
        # window. Anything skipped is kept as a fallback in case the cap leaves the
        # context short.
        selected: list[tuple[float, dict[str, Any]]] = []
        overflow: list[tuple[float, dict[str, Any]]] = []
        per_source: Counter[str] = Counter()
        for score, chunk in scored:
            if per_source[chunk["source"]] >= MAX_CHUNKS_PER_SOURCE:
                overflow.append((score, chunk))
                continue
            per_source[chunk["source"]] += 1
            selected.append((score, chunk))
            if len(selected) >= top_k:
                break

        if len(selected) < top_k:
            selected.extend(overflow[: top_k - len(selected)])

        return [
            {
                "chunk_id": chunk["chunk_id"],
                "doc_id": chunk["doc_id"],
                "title": chunk["title"],
                "doc_type": chunk["doc_type"],
                "source": chunk["source"],
                "text": chunk["text"],
                "score": round(float(score), 3),
            }
            for score, chunk in selected[:top_k]
        ]

    def corpus_stats(self) -> dict[str, Any]:
        chunks = self._ensure_index()
        return {
            "documents": self._documents,
            "chunks": len(chunks),
            "sources": len({chunk["source"] for chunk in chunks}),
            "extract_datasets": list(self._extract_datasets),
        }

    def warm(self) -> None:
        """Build the index up front so the first comparison is not slowed by it."""
        try:
            import time
            time.sleep(2.0)
            self._ensure_index()
        except Exception as error:
            print(f"[RagService] Warmup notice: {error}")


_SERVICE: RagService | None = None


def get_rag_service(data_dir: Path, sql_service: Any = None) -> RagService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = RagService(data_dir, sql_service=sql_service)
    return _SERVICE
