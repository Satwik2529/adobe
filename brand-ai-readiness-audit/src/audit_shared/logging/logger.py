"""
Basic structured logging foundation.
"""

import logging
import sys

def setup_logger(name: str = "ai_audit") -> logging.Logger:
    """
    Initializes a basic structured logger.
    Later phases will implement specific categories: [CRAWL], [RULE], etc.
    """
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    return logger

logger = setup_logger()
