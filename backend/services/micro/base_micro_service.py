"""
Base Microservice Class - Common functionality for all microservices
"""
import logging
from typing import Callable, Any
from functools import wraps
from backend.database.config import SessionLocal

logger = logging.getLogger(__name__)


class BaseMicroService:
    """
    Base class for all microservices
    
    Provides:
    - Database session management
    - Common error handling
    - Logging utilities
    """
    
    def __init__(self):
        """Initialize base microservice"""
        self.get_db = SessionLocal
    
    @staticmethod
    def with_db(func: Callable) -> Callable:
        """
        Decorator for methods that need database access
        
        Automatically manages database session lifecycle:
        - Creates session before method execution
        - Passes session as first argument after self
        - Closes session after method completes
        
        Usage:
            @BaseMicroService.with_db
            def my_method(self, db, other_args):
                # Use db session here
                return db.query(Model).all()
        """
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            db = self.get_db()
            try:
                # Insert db as the first argument after self
                return func(self, db, *args, **kwargs)
            except Exception as e:
                logger.error(f"Database operation failed in {func.__name__}: {e}")
                raise
            finally:
                db.close()
        return wrapper
    
    def log_operation(self, operation: str, details: dict = None):
        """
        Log microservice operations
        
        Args:
            operation: Operation name
            details: Additional details to log
        """
        log_msg = f"[{self.__class__.__name__}] {operation}"
        if details:
            log_msg += f" - {details}"
        logger.info(log_msg)