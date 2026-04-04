from neo4j import GraphDatabase

class Neo4jDB:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            "bolt://127.0.0.1:7687",
            auth=("neo4j", "meowmeow")
        )

    def run_query(self, query, params=None):
        with self.driver.session(database="nexus") as session:
            result = session.run(query, params or {})
            return [record.data() for record in result]

neo4j_db = Neo4jDB()
