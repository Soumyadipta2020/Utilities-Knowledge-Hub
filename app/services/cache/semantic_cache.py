import time
from collections import OrderedDict
from typing import Any, Dict, Optional, Tuple
import hashlib
import json

class SimpleLRUCache:
    """Basic LRU Cache with TTL."""
    def __init__(self, capacity: int, ttl_seconds: int):
        self.cache: OrderedDict[str, Tuple[float, Any]] = OrderedDict()
        self.capacity = capacity
        self.ttl_seconds = ttl_seconds

    def get(self, key: str) -> Optional[Any]:
        if key not in self.cache:
            return None
        
        timestamp, value = self.cache[key]
        if time.time() - timestamp > self.ttl_seconds:
            # Expired
            del self.cache[key]
            return None
            
        self.cache.move_to_end(key)
        return value

    def set(self, key: str, value: Any):
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = (time.time(), value)
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)

class SemanticCache:
    """
    Multi-level semantic cache implementing L1 (Metadata), L2 (Query Results).
    L3 (Retrieval) could be added here in a full deployment.
    """
    def __init__(self):
        # L1: Metadata Cache (Longer TTL, 1 hour)
        self.l1_metadata = SimpleLRUCache(capacity=1000, ttl_seconds=3600)
        
        # L2: Query Results Cache (Shorter TTL, 5 minutes)
        self.l2_results = SimpleLRUCache(capacity=500, ttl_seconds=300)

    def _generate_key(self, tool_name: str, args: Dict[str, Any]) -> str:
        # Sort keys to ensure deterministic cache keys
        sorted_args = json.dumps(args, sort_keys=True)
        return hashlib.sha256(f"{tool_name}:{sorted_args}".encode('utf-8')).hexdigest()

    def get_query_result(self, tool_name: str, args: Dict[str, Any]) -> Optional[Any]:
        key = self._generate_key(tool_name, args)
        return self.l2_results.get(key)

    def set_query_result(self, tool_name: str, args: Dict[str, Any], result: Any):
        key = self._generate_key(tool_name, args)
        self.l2_results.set(key, result)

    def get_metadata(self, key: str) -> Optional[Any]:
        return self.l1_metadata.get(key)
        
    def set_metadata(self, key: str, value: Any):
        self.l1_metadata.set(key, value)

# Global cache instance
semantic_cache = SemanticCache()
