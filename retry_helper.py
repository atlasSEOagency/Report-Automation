import time
from functools import wraps
from gspread.exceptions import APIError

class RateLimiter:
    def __init__(self, delay=1.5):
        self.delay = delay
        self.last_call = 0.0

    def wait(self):
        now = time.monotonic()
        elapsed = now - self.last_call
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self.last_call = time.monotonic()

limiter = RateLimiter(1.5)

def is_quota_error(error: APIError) -> bool:
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
    delays = [10, 20, 40]
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            while True:
                limiter.wait()
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

# No retry decorator for mutating append_rows! Just pace it.
def paced_append_rows(worksheet, rows):
    limiter.wait()
    return worksheet.append_rows(rows)

def paced_update(worksheet, range_name, values):
    limiter.wait()
    return worksheet.update(range_name, values)
