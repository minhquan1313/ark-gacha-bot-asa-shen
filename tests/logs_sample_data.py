"""Synthetic records used only by isolated Logs tests and design previews."""

def sample_lines(count=4200):
    """Generate preview-only data; never append these records to application logs."""
    levels = ("INFO", "DEBUG", "INFO", "WARN", "INFO", "ERROR", "RUNNING", "QUEUE", "CRITICAL")
    sources = ("check_for_update", "http", "keyboard", "gacha", "scheduler", "storage", "runner", "queue", "system")
    messages = (
        "Remote version: 1.0.0; update available: False",
        "Status: 200 (245ms)",
        "Bindings resolved: Jump, Crouch, Use",
        "Rate limit approaching. Waiting 1.2s...",
        "Next run in 5 minutes.",
        "Unable to find target inventory",
        "Automation task started",
        "Task queued for execution",
        "Low disk space warning",
    )
    return [f"{16+i//3600:02}:{i // 60 % 60:02}:{i % 60:02} - {levels[i % 9]} - {sources[i % 9]} - Event {i:05}: {messages[i % 9]}\n" for i in range(count)]

