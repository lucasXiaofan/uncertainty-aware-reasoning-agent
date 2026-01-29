"""Simple BM25 Search for JSON document retrieval."""
import json
import math
import re
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Any, Optional


class BM25Search:
    """BM25 search class for JSON documents.

    Args:
        json_file_path: Path to JSON file
        search_field: Field to search in (default: 'observation')
        output_field: Field to return (default: 'observation')
        id_field: Unique ID field (default: 'id')
    """

    def __init__(
        self,
        json_file_path: str,
        search_field: str = "observation",
        output_field: str = "observation",
        id_field: str = "id",
        k1: float = 1.5,
        b: float = 0.75
    ):
        self.json_file_path = Path(json_file_path)
        self.search_field = search_field
        self.output_field = output_field
        self.id_field = id_field
        self.k1 = k1
        self.b = b

        self.documents: List[Dict] = []
        self.doc_lengths: List[int] = []
        self.avg_doc_length: float = 0
        self.inverted_index: Dict[str, Dict[int, int]] = defaultdict(dict)
        self.doc_freq: Dict[str, int] = defaultdict(int)
        self.id_to_index: Dict[Any, int] = {}

        self._load_and_index()

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text."""
        if not text:
            return []
        return re.findall(r'\b[a-z0-9]+\b', text.lower())

    def _load_and_index(self) -> None:
        """Load JSON and build index."""
        if not self.json_file_path.exists():
            return

        with open(self.json_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.documents = data if isinstance(data, list) else [data]
        if not self.documents:
            return

        total_length = 0
        for idx, doc in enumerate(self.documents):
            self.id_to_index[doc.get(self.id_field, idx)] = idx
            tokens = self._tokenize(str(doc.get(self.search_field, "")))
            self.doc_lengths.append(len(tokens))
            total_length += len(tokens)

            term_freq = defaultdict(int)
            for token in tokens:
                term_freq[token] += 1

            for term, freq in term_freq.items():
                self.inverted_index[term][idx] = freq
                self.doc_freq[term] += 1

        self.avg_doc_length = total_length / len(self.documents)

    def search(self, query: str, top_k: int = 10) -> List[Dict]:
        """Search and return results with id, output_field text, and score."""
        if not self.documents:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        scores = []
        for idx in range(len(self.documents)):
            score = 0.0
            doc_len = self.doc_lengths[idx]
            for term in query_tokens:
                if term not in self.inverted_index:
                    continue
                tf = self.inverted_index[term].get(idx, 0)
                if tf == 0:
                    continue
                df = self.doc_freq[term]
                idf = math.log((len(self.documents) - df + 0.5) / (df + 0.5) + 1)
                score += idf * (tf * (self.k1 + 1)) / (tf + self.k1 * (1 - self.b + self.b * doc_len / self.avg_doc_length))

            if score > 0:
                scores.append((idx, score))

        scores.sort(key=lambda x: x[1], reverse=True)

        results = []
        for idx, score in scores[:top_k]:
            doc = self.documents[idx]
            results.append({
                "id": doc.get(self.id_field),
                "observation": doc.get(self.output_field, ""),
                "score": round(score, 4)
            })
        return results

    def get_by_id(self, doc_id: Any) -> Optional[Dict]:
        """Get entire JSON object by ID."""
        idx = self.id_to_index.get(doc_id)
        if idx is not None:
            return self.documents[idx]
        return None

    def reload(self) -> None:
        """Reload from file."""
        self.documents = []
        self.doc_lengths = []
        self.inverted_index = defaultdict(dict)
        self.doc_freq = defaultdict(int)
        self.id_to_index = {}
        self._load_and_index()


class SearchSessionManager:
    """Manages search sessions with unique results (max 30 per session)."""

    def __init__(self, bm25: BM25Search, max_results: int = 30):
        self.bm25 = bm25
        self.max_results = max_results
        self.sessions: Dict[str, Dict[Any, Dict]] = {}

    def create_session(self, session_id: str) -> None:
        """Create new session."""
        self.sessions[session_id] = {}

    def search_and_add(self, session_id: str, query: str, top_k: int = 10) -> List[Dict]:
        """Search and add unique results to session. Returns newly added results."""
        if session_id not in self.sessions:
            raise ValueError(f"Session '{session_id}' not found")

        session = self.sessions[session_id]
        results = self.bm25.search(query, top_k)

        new_results = []
        for r in results:
            if r["id"] not in session and len(session) < self.max_results:
                session[r["id"]] = r
                new_results.append(r)
        return new_results

    def get_results(self, session_id: str) -> List[Dict]:
        """Get all session results (id, observation) sorted by score."""
        if session_id not in self.sessions:
            return []
        results = list(self.sessions[session_id].values())
        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        return [{"id": r["id"], "observation": r["observation"]} for r in results]

    def get_by_id(self, session_id: str, result_id: Any) -> Optional[Dict]:
        """Get full document by ID from BM25."""
        return self.bm25.get_by_id(result_id)

    def clear_session(self, session_id: str) -> None:
        """Clear session."""
        if session_id in self.sessions:
            self.sessions[session_id] = {}
