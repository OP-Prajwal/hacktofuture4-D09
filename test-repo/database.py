# database.py
import time

class DatabaseManager:
    def __init__(self):
        self.connected = False
        
    def connect(self):
        print("Connecting to DB...")
        time.sleep(0.1)
        self.connected = True
        
    def query(self, sql: str):
        if not self.connected:
            raise Exception("Not connected!")
        print(f"Executing: {sql}")
        return []
