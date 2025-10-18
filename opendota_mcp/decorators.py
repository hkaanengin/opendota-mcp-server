"""
Decorators for logging and monitoring
"""
import logging
import time
import functools
from typing import Any, Callable

logger = logging.getLogger("opendota-server")


def log_tool_execution(func: Callable) -> Callable:
    """
    Decorator to log tool execution with parameters and results.
    Useful for debugging and monitoring during testing.
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        tool_name = func.__name__
        
        # Log tool invocation
        logger.info(f"🔧 Tool called: {tool_name}")
        
        # Log parameters (safely, without sensitive data)
        if kwargs:
            safe_kwargs = {k: v for k, v in kwargs.items() if v is not None}
            logger.info(f"   Parameters: {safe_kwargs}")
        
        # Track execution time
        start_time = time.time()
        
        try:
            # Execute the tool
            result = await func(*args, **kwargs)
            
            # Calculate execution time
            execution_time = time.time() - start_time
            
            # Log success
            if isinstance(result, dict) and "error" in result:
                logger.warning(f"⚠️  Tool {tool_name} returned error: {result.get('error')}")
            else:
                logger.info(f"✅ Tool {tool_name} completed in {execution_time:.2f}s")
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"❌ Tool {tool_name} failed after {execution_time:.2f}s: {str(e)}", exc_info=True)
            return {"error": str(e)}
    
    return wrapper