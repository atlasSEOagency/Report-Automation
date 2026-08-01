import time
from functools import wraps
from gspread.exceptions import APIError

def is_quota_error(error: APIError) -> bool:
    """Check if the given APIError is a quota or rate-limit error."""
    # APIError wraps the requests.Response
    try:
        err_json = error.response.json()
        status_code = error.response.status_code
        if status_code == 429:
            return True
        if status_code == 403 and "error" in err_json:
            errors = err_json["error"].get("errors", [])
            for e in errors:
                reason = e.get("reason", "")
                if reason in ("rateLimitExceeded", "userRateLimitExceeded"):
                    return True
    except Exception:
        pass

    return False

def retry_quota_error(sleep_func=time.sleep):
    """
    Decorator that catches gspread API quota errors and retries with exponential backoff.
    Retries up to 3 times (4 total attempts) with delays of 10s, 20s, 40s.
    """
    delays = [10, 20, 40]

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except APIError as e:
                    if not is_quota_error(e):
                        raise

                    if attempts >= len(delays):
                        print(f"API Error ({func.__name__}): Quota exceeded. Max retries reached (4 attempts). Failing.")
                        raise

                    delay = delays[attempts]
                    attempts += 1
                    print(f"API Error ({func.__name__}): Quota exceeded. Retrying in {delay} seconds... (Attempt {attempts}/{len(delays)})")
                    sleep_func(delay)
        return wrapper
    return decorator

@retry_quota_error()
def open_sheet_with_retry(gc, title):
    return gc.open(title)

@retry_quota_error()
def get_worksheets_with_retry(sh):
    return sh.worksheets()

@retry_quota_error()
def get_all_values_with_retry(worksheet):
    return worksheet.get_all_values()

@retry_quota_error()
def col_values_with_retry(worksheet, col):
    return worksheet.col_values(col)

@retry_quota_error()
def batch_clear_with_retry(worksheet, ranges):
    return worksheet.batch_clear(ranges)
