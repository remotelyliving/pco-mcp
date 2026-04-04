def map_pco_error(status_code: int, base_url: str) -> str:
    """Map a PCO API HTTP status code to a plain-English error message."""
    if status_code == 401:
        return (
            f"Your Planning Center session has expired. "
            f"Please reconnect at {base_url}"
        )
    if status_code == 403:
        return "You don't have permission to access this in Planning Center."
    if status_code == 404:
        return "That record wasn't found in Planning Center."
    if status_code == 429:
        return "Planning Center is rate-limiting requests. Please wait a moment and try again."
    if status_code >= 500:
        return "Planning Center is temporarily unavailable. Please try again shortly."
    return f"An unexpected error occurred (status {status_code}). Please try again."
