def normalize_server_number(server: object):
    """Return a validated non-zero numeric ARK server identifier."""
    normalized = str(server).strip()
    if not normalized or normalized == "0" or not normalized.isdigit():
        raise ValueError("Server number must be a non-zero number.")
    return normalized
