# logger.py
import datetime

def log_event(event_name: str, message: str):
    """
    Logs an event to the console with a timestamp.
    """
    timestamp = datetime.datetime.now().isoformat()
    print(f"[{timestamp}] {event_name.upper()}: {message}")
