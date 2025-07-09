"""
Rate Limiter for Gemini API to stay within free tier limits
"""
import time
import json
import os
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class GeminiRateLimiter:
    """Rate limiter to manage Gemini API usage within free tier limits"""
    
    def __init__(self):
        self.request_history = {}  # model -> list of request timestamps
        self.token_usage = {}      # model -> {minute: tokens_used}
        self.daily_usage = {}      # model -> {date: requests_count}
        self.lock = threading.Lock()
        self.rate_limits = self._load_rate_limits()
        
    def _load_rate_limits(self) -> Dict:
        """Load rate limits configuration"""
        try:
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            config_path = os.path.join(project_root, 'config', 'gemini_rate_limits.json')
            
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                return config.get('rate_limits', {})
            else:
                logger.warning("Rate limits config not found, using defaults")
                return self._get_default_limits()
                
        except Exception as e:
            logger.error(f"Error loading rate limits: {e}")
            return self._get_default_limits()
    
    def _get_default_limits(self) -> Dict:
        """Default rate limits if config file is not available"""
        return {
            'gemini-2.5-pro': {
                'requests_per_minute': 5,
                'requests_per_day': 100,
                'tokens_per_minute': 250000
            },
            'gemini-2.5-flash': {
                'requests_per_minute': 10,
                'requests_per_day': 1000,
                'tokens_per_minute': 250000
            }
        }
    
    def wait_if_needed(self, model_name: str, estimated_tokens: int = 1000) -> float:
        """
        Check rate limits and wait if necessary before making a request
        
        Args:
            model_name: The Gemini model name
            estimated_tokens: Estimated tokens for this request
            
        Returns:
            Time waited in seconds
        """
        with self.lock:
            wait_time = 0
            
            # Get limits for this model
            limits = self._get_model_limits(model_name)
            if not limits:
                logger.warning(f"No rate limits found for model {model_name}")
                return 0
            
            # Apply safety margins
            rpm_limit = int(limits['requests_per_minute'] * 0.8)  # 80% of limit
            rpd_limit = int(limits['requests_per_day'] * 0.9)     # 90% of limit
            tpm_limit = int(limits['tokens_per_minute'] * 0.8)    # 80% of limit
            
            now = datetime.now()
            
            # Check and wait for requests per minute limit
            rpm_wait = self._check_rpm_limit(model_name, rpm_limit, now)
            if rpm_wait > 0:
                logger.info(f"Rate limit: waiting {rpm_wait:.1f}s for RPM limit ({model_name})")
                wait_time = max(wait_time, rpm_wait)
            
            # Check requests per day limit
            if self._check_rpd_limit(model_name, rpd_limit, now):
                logger.error(f"Daily request limit reached for {model_name} ({rpd_limit} requests)")
                raise Exception(f"Daily rate limit exceeded for {model_name}")
            
            # Check tokens per minute limit
            tpm_wait = self._check_tpm_limit(model_name, tpm_limit, estimated_tokens, now)
            if tpm_wait > 0:
                logger.info(f"Rate limit: waiting {tpm_wait:.1f}s for TPM limit ({model_name})")
                wait_time = max(wait_time, tpm_wait)
            
            # Wait if necessary
            if wait_time > 0:
                time.sleep(wait_time)
            
            # Record this request
            self._record_request(model_name, estimated_tokens, now)
            
            return wait_time
    
    def _get_model_limits(self, model_name: str) -> Optional[Dict]:
        """Get rate limits for a specific model"""
        # Find matching model in config
        for config_model, limits in self.rate_limits.items():
            if config_model.lower() in model_name.lower():
                return limits
        return None
    
    def _check_rpm_limit(self, model_name: str, rpm_limit: int, now: datetime) -> float:
        """Check requests per minute limit and return wait time if needed"""
        if model_name not in self.request_history:
            self.request_history[model_name] = []
        
        # Clean old requests (older than 1 minute)
        one_minute_ago = now - timedelta(minutes=1)
        self.request_history[model_name] = [
            req_time for req_time in self.request_history[model_name] 
            if req_time > one_minute_ago
        ]
        
        # Check if we're at the limit
        if len(self.request_history[model_name]) >= rpm_limit:
            # Wait until the oldest request is more than 1 minute old
            oldest_request = min(self.request_history[model_name])
            wait_until = oldest_request + timedelta(minutes=1, seconds=1)  # Add 1 second buffer
            wait_time = (wait_until - now).total_seconds()
            return max(0, wait_time)
        
        return 0
    
    def _check_rpd_limit(self, model_name: str, rpd_limit: int, now: datetime) -> bool:
        """Check if daily request limit is exceeded"""
        if model_name not in self.daily_usage:
            self.daily_usage[model_name] = {}
        
        today = now.strftime('%Y-%m-%d')
        current_daily_count = self.daily_usage[model_name].get(today, 0)
        
        return current_daily_count >= rpd_limit
    
    def _check_tpm_limit(self, model_name: str, tpm_limit: int, estimated_tokens: int, now: datetime) -> float:
        """Check tokens per minute limit and return wait time if needed"""
        if model_name not in self.token_usage:
            self.token_usage[model_name] = {}
        
        # Clean old token usage (older than 1 minute)
        current_minute = now.replace(second=0, microsecond=0)
        one_minute_ago = current_minute - timedelta(minutes=1)
        
        # Remove old entries
        self.token_usage[model_name] = {
            minute: tokens for minute, tokens in self.token_usage[model_name].items()
            if minute > one_minute_ago
        }
        
        # Calculate current token usage in the last minute
        current_tokens = sum(self.token_usage[model_name].values())
        
        # Check if adding this request would exceed the limit
        if current_tokens + estimated_tokens > tpm_limit:
            # Find the earliest minute with token usage
            if self.token_usage[model_name]:
                earliest_minute = min(self.token_usage[model_name].keys())
                wait_until = earliest_minute + timedelta(minutes=1, seconds=1)  # Add buffer
                wait_time = (wait_until - now).total_seconds()
                return max(0, wait_time)
        
        return 0
    
    def _record_request(self, model_name: str, estimated_tokens: int, now: datetime):
        """Record a request for rate limiting tracking"""
        # Record request time
        if model_name not in self.request_history:
            self.request_history[model_name] = []
        self.request_history[model_name].append(now)
        
        # Record token usage
        if model_name not in self.token_usage:
            self.token_usage[model_name] = {}
        current_minute = now.replace(second=0, microsecond=0)
        self.token_usage[model_name][current_minute] = \
            self.token_usage[model_name].get(current_minute, 0) + estimated_tokens
        
        # Record daily usage
        if model_name not in self.daily_usage:
            self.daily_usage[model_name] = {}
        today = now.strftime('%Y-%m-%d')
        self.daily_usage[model_name][today] = \
            self.daily_usage[model_name].get(today, 0) + 1
    
    def get_usage_stats(self) -> Dict:
        """Get current usage statistics"""
        with self.lock:
            now = datetime.now()
            stats = {}
            
            for model_name in set(list(self.request_history.keys()) + 
                                 list(self.daily_usage.keys())):
                
                # RPM usage
                one_minute_ago = now - timedelta(minutes=1)
                recent_requests = [
                    req_time for req_time in self.request_history.get(model_name, [])
                    if req_time > one_minute_ago
                ]
                
                # Daily usage
                today = now.strftime('%Y-%m-%d')
                daily_requests = self.daily_usage.get(model_name, {}).get(today, 0)
                
                # Token usage
                current_minute = now.replace(second=0, microsecond=0)
                one_minute_ago_minute = current_minute - timedelta(minutes=1)
                recent_tokens = sum(
                    tokens for minute, tokens in self.token_usage.get(model_name, {}).items()
                    if minute > one_minute_ago_minute
                )
                
                # Get limits
                limits = self._get_model_limits(model_name)
                
                stats[model_name] = {
                    'requests_last_minute': len(recent_requests),
                    'requests_today': daily_requests,
                    'tokens_last_minute': recent_tokens,
                    'limits': limits,
                    'rpm_usage_percent': (len(recent_requests) / limits['requests_per_minute'] * 100) if limits else 0,
                    'rpd_usage_percent': (daily_requests / limits['requests_per_day'] * 100) if limits else 0,
                    'tpm_usage_percent': (recent_tokens / limits['tokens_per_minute'] * 100) if limits else 0
                }
            
            return stats
    
    def get_recommended_batch_size(self, model_name: str) -> Dict:
        """Get recommended batch size and delay for a model"""
        limits = self._get_model_limits(model_name)
        if not limits:
            return {'batch_size': 1, 'delay_seconds': 60}
        
        # Conservative batch sizes to stay within limits
        rpm_limit = int(limits['requests_per_minute'] * 0.8)
        
        if 'pro' in model_name.lower():
            # Pro model: more conservative
            return {
                'batch_size': min(3, rpm_limit),
                'delay_seconds': 60 / rpm_limit if rpm_limit > 0 else 20
            }
        else:
            # Flash model: less conservative
            return {
                'batch_size': min(5, rpm_limit),
                'delay_seconds': 60 / rpm_limit if rpm_limit > 0 else 10
            }


# Global rate limiter instance
_rate_limiter = None

def get_rate_limiter() -> GeminiRateLimiter:
    """Get global rate limiter instance"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = GeminiRateLimiter()
    return _rate_limiter