from pymongo import MongoClient

class MongoDB:
    def __init__(self):
        self.client = MongoClient("mongodb://localhost:27017")
        self.db = self.client["nexus_db"]

    def get_collection(self, name):
        return self.db[name]

mongo = MongoDB()
