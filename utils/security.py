"""Security and rate limiting middleware for FastAPI"""
import time
from collections import defaultdict
from fastapi import Request, HTTPException
from typing import Dict, Tuple

class RateLimiter:
    """Simple in-memory rate limiter (per IP address)."""
    
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.requests: Dict[str, list] = defaultdict(list)
    
    def is_rate_limited(self, client_ip: str) -> bool:
        """Check if client has exceeded rate limit."""
        now = time.time()
        minute_ago = now - 60
        
        # Clean old requests
        self.requests[client_ip] = [
            req_time for req_time in self.requests[client_ip]
            if req_time > minute_ago
        ]
        
        # Check limit
        if len(self.requests[client_ip]) >= self.requests_per_minute:
            return True
        
        # Record request
        self.requests[client_ip].append(now)
        return False


class SecurityHeaders:
    """Add security headers to responses."""
    
    @staticmethod
    def get_headers() -> Dict[str, str]:
        """Return recommended security headers."""
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https:",
            "Referrer-Policy": "strict-origin-when-cross-origin",
        }
