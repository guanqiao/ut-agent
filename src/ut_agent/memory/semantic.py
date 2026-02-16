"""语义记忆管理器."""

from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import hashlib


class SemanticMemoryManager:
    """语义记忆管理器 - 基于向量相似度的知识检索."""
    
    def __init__(
        self,
        storage_path: Optional[Path] = None,
        embedding_model: str = "text-embedding-3-small",
        use_simple_mode: bool = True,
    ):
        self._storage_path = storage_path or Path.home() / ".ut-agent" / "vectors"
        self._storage_path.mkdir(parents=True, exist_ok=True)
        
        self._embedding_model = embedding_model
        self._use_simple_mode = use_simple_mode
        
        self._vector_store = None
        self._embeddings = None
        self._patterns: Dict[str, Dict[str, Any]] = {}
        self._index_file = self._storage_path / "patterns_index.json"
        
        self._load_index()
    
    def _load_index(self) -> None:
        if self._index_file.exists():
            try:
                with open(self._index_file, "r", encoding="utf-8") as f:
                    self._patterns = json.load(f)
            except Exception:
                self._patterns = {}
    
    def _save_index(self) -> None:
        with open(self._index_file, "w", encoding="utf-8") as f:
            json.dump(self._patterns, f, ensure_ascii=False, indent=2)
    
    def _init_vector_store(self) -> None:
        if self._vector_store is not None:
            return
        
        try:
            from langchain_openai import OpenAIEmbeddings
            from langchain_community.vectorstores import Chroma
            
            self._embeddings = OpenAIEmbeddings(model=self._embedding_model)
            self._vector_store = Chroma(
                embedding_function=self._embeddings,
                persist_directory=str(self._storage_path / "chroma"),
            )
        except ImportError:
            self._use_simple_mode = True
    
    def add_pattern(
        self,
        pattern_id: str,
        content: str,
        metadata: Dict[str, Any],
    ) -> None:
        if self._use_simple_mode:
            self._add_pattern_simple(pattern_id, content, metadata)
        else:
            self._add_pattern_vector(pattern_id, content, metadata)
    
    def _add_pattern_simple(
        self,
        pattern_id: str,
        content: str,
        metadata: Dict[str, Any],
    ) -> None:
        content_hash = hashlib.md5(content.encode()).hexdigest()
        
        keywords = self._extract_keywords(content)
        
        self._patterns[pattern_id] = {
            "id": pattern_id,
            "content": content,
            "content_hash": content_hash,
            "keywords": keywords,
            "metadata": metadata,
        }
        
        self._save_index()
    
    def _add_pattern_vector(
        self,
        pattern_id: str,
        content: str,
        metadata: Dict[str, Any],
    ) -> None:
        self._init_vector_store()
        
        if self._vector_store:
            self._vector_store.add_texts(
                texts=[content],
                metadatas=[{"id": pattern_id, **metadata}],
                ids=[pattern_id],
            )
    
    def find_similar(
        self,
        query: str,
        k: int = 5,
        language: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if self._use_simple_mode:
            return self._find_similar_simple(query, k, language)
        else:
            return self._find_similar_vector(query, k, language)
    
    def _find_similar_simple(
        self,
        query: str,
        k: int,
        language: Optional[str],
    ) -> List[Dict[str, Any]]:
        query_keywords = set(self._extract_keywords(query))
        
        scores = []
        for pattern_id, pattern in self._patterns.items():
            if language and pattern.get("metadata", {}).get("language") != language:
                continue
            
            pattern_keywords = set(pattern.get("keywords", []))
            
            if query_keywords and pattern_keywords:
                intersection = len(query_keywords & pattern_keywords)
                union = len(query_keywords | pattern_keywords)
                score = intersection / union if union > 0 else 0
            else:
                score = 0
            
            scores.append((pattern_id, score, pattern))
        
        scores.sort(key=lambda x: x[1], reverse=True)
        
        return [
            {
                "id": pattern_id,
                "content": pattern["content"],
                "metadata": pattern.get("metadata", {}),
                "score": score,
            }
            for pattern_id, score, pattern in scores[:k]
            if score > 0
        ]
    
    def _find_similar_vector(
        self,
        query: str,
        k: int,
        language: Optional[str],
    ) -> List[Dict[str, Any]]:
        self._init_vector_store()
        
        if not self._vector_store:
            return self._find_similar_simple(query, k, language)
        
        filter_dict = None
        if language:
            filter_dict = {"language": language}
        
        try:
            results = self._vector_store.similarity_search_with_score(
                query,
                k=k,
                filter=filter_dict,
            )
            
            return [
                {
                    "id": doc.metadata.get("id", ""),
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "score": 1 - score,
                }
                for doc, score in results
            ]
        except Exception:
            return self._find_similar_simple(query, k, language)
    
    def _extract_keywords(self, text: str) -> List[str]:
        import re
        
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        
        stop_words = {
            "the", "and", "for", "are", "but", "not", "you", "all",
            "can", "had", "her", "was", "one", "our", "out", "has",
            "have", "been", "will", "would", "could", "should", "this",
            "that", "with", "from", "they", "them", "then", "than",
        }
        
        keywords = [w for w in words if w not in stop_words]
        
        from collections import Counter
        word_counts = Counter(keywords)
        
        return [word for word, _ in word_counts.most_common(20)]
    
    def get_pattern(self, pattern_id: str) -> Optional[Dict[str, Any]]:
        return self._patterns.get(pattern_id)
    
    def remove_pattern(self, pattern_id: str) -> bool:
        if pattern_id in self._patterns:
            del self._patterns[pattern_id]
            self._save_index()
            return True
        return False
    
    def get_all_patterns(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": pattern_id,
                "content": pattern["content"],
                "metadata": pattern.get("metadata", {}),
            }
            for pattern_id, pattern in self._patterns.items()
        ]
    
    def get_pattern_count(self) -> int:
        return len(self._patterns)
    
    def clear_all(self) -> None:
        self._patterns.clear()
        self._save_index()
