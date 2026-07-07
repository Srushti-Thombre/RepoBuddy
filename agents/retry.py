import time
import sys
from functools import wraps
import google.genai.errors as errors

def with_retry(delays=(2, 5, 10)):
    """
    A decorator that retries a function on specific google.genai.errors.APIError
    exceptions (429 Too Many Requests, 503 Service Unavailable).
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt, delay in enumerate(delays):
                try:
                    return func(*args, **kwargs)
                except errors.APIError as e:
                    # Determine if the error is retryable (429 or 503)
                    code = getattr(e, "code", None)
                    err_str = str(e)
                    is_retryable = False

                    # Check structured HTTP status code if available
                    if code in (429, 503):
                        is_retryable = True
                    # Fallback to exception type parsing
                    elif type(e).__name__ == "ServerError" or "503" in err_str or "429" in err_str:
                        is_retryable = True

                    if is_retryable:
                        print(f"[RETRY] {func.__name__} failed due to rate limits or high demand (429/503). Retrying in {delay} seconds... (Attempt {attempt + 1}/{len(delays)})", file=sys.stderr)
                        time.sleep(delay)
                    else:
                        raise e
                        
            # Final attempt
            try:
                return func(*args, **kwargs)
            except errors.APIError as e:
                print(f"[RETRY] All retry attempts exhausted for {func.__name__}.", file=sys.stderr)
                raise e
        return wrapper
    return decorator
