import threading
import logging
from typing import List, Optional
from .config import settings

logger = logging.getLogger("uvicorn.error")

class GroqKeyPool:
    """
    Manages multiple Groq API keys with thread-safe round-robin rotation
    and automatic failover when hitting rate limits (HTTP 429 / Quotas).
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._keys: List[str] = []
        self._index = 0
        self._reload_keys()

    def _reload_keys(self):
        raw_keys = []
        if settings.groq_api_keys:
            raw_keys.extend(settings.groq_api_keys.replace(";", ",").replace("\n", ",").split(","))
        if settings.groq_api_key:
            raw_keys.extend(settings.groq_api_key.replace(";", ",").replace("\n", ",").split(","))
        
        # Filter valid keys (ignore empty or placeholders)
        filtered = []
        for k in raw_keys:
            clean_k = k.strip().strip("'").strip('"')
            if clean_k and clean_k != "your_groq_api_key_here":
                filtered.append(clean_k)
                
        # Deduplicate while preserving order
        self._keys = list(dict.fromkeys(filtered))
        
        if self._keys:
            logger.info(f"[GroqPool] Successfully loaded {len(self._keys)} Groq API key(s) for automatic rotation.")
        else:
            logger.warning("[GroqPool] No valid Groq API keys configured.")

    def get_all_keys(self) -> List[str]:
        if not self._keys:
            self._reload_keys()
        return self._keys.copy()

    def get_next_key(self) -> Optional[str]:
        """Returns the next rotated API key in round-robin order."""
        if not self._keys:
            self._reload_keys()
        if not self._keys:
            return None
        with self._lock:
            key = self._keys[self._index % len(self._keys)]
            self._index = (self._index + 1) % len(self._keys)
            return key

    def get_ordered_keys(self) -> List[str]:
        """
        Returns a list of keys starting from the current round-robin index,
        followed by all other fallback keys.
        """
        all_k = self.get_all_keys()
        if not all_k:
            return []
        next_k = self.get_next_key()
        return [next_k] + [k for k in all_k if k != next_k]

# Global singleton
groq_pool = GroqKeyPool()
