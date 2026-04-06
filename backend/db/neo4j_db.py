from neo4j import GraphDatabase, TrustAll
import os
from dotenv import load_dotenv

# Search for .env from current and parent directories
load_dotenv(override=True)
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'), override=True)

class Neo4jDB:
    def __init__(self):
        self._connect()

    def _connect(self):
        uri = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
        self.uri = uri
        self.username = os.getenv("NEO4J_USERNAME", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "meowmeow")
        # NEO4J_DATABASE should be the name of the database (e.g., 'neo4j' or 'bdc4c6d6')
        # If not provided, we use None which tells the driver to use the default database.
        self.database = os.getenv("NEO4J_DATABASE", None)
        if self.database == "":
            self.database = None
            
        print(f"[Neo4j] Initializing driver for {self.uri} (Database: {self.database})")
        
        try:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password)
            )
            # Verify connectivity immediately
            self.driver.verify_connectivity()
            print("[Neo4j] Driver connected and verified.")
        except Exception as e:
            print(f"[Neo4j] Driver initialization or verification failed: {e}")

    def run_query(self, query, params=None):
        try:
            # Try with primary driver and specified database
            with self.driver.session(database=self.database) as session:
                result = session.run(query, params or {})
                return [record.data() for record in result]
        except Exception as e:
            err_str = str(e).lower()
            # If it's a DatabaseNotFound error, and we specified a database, maybe try without specifying it?
            if "databaseNotFound" in str(e) or "database not found" in err_str:
                if self.database is not None:
                    print(f"[Neo4j] Database '{self.database}' not found. Retrying with default database...")
                    try:
                        with self.driver.session(database=None) as session:
                            result = session.run(query, params or {})
                            return [record.data() for record in result]
                    except Exception as e2:
                        print(f"[Neo4j] Retry with default database also failed: {e2}")
            
            # Connection/Routing fallbacks
            if "routing" in err_str or "connection" in err_str or "socket" in err_str or "ssl" in err_str or "operation not permitted" in err_str:
                print(f"[Neo4j] Connection error: {e}. Attempting fallback to direct bolt+ssc://...")
                
                # Fallback: Swap to bolt+ssc:// for Aura stability
                fallback_uri = self.uri.replace("neo4j+s://", "bolt+ssc://").replace("neo4j://", "bolt://")
                if "bolt" not in fallback_uri:
                    fallback_uri = "bolt+ssc://" + fallback_uri.split("://")[-1]

                try:
                    fallback_driver = GraphDatabase.driver(
                        fallback_uri,
                        auth=(self.username, self.password)
                    )
                    # Use the fallback driver for this query
                    with fallback_driver.session(database=self.database) as session:
                        result = session.run(query, params or {})
                        # If successful, we might want to switch the main driver
                        self.driver = fallback_driver
                        self.uri = fallback_uri
                        return [record.data() for record in result]
                except Exception as fallback_err:
                    print(f"[Neo4j] Fallback failed: {fallback_err}")
                    # If fallback with database failed, try fallback without database
                    if self.database is not None:
                         try:
                             with fallback_driver.session(database=None) as session:
                                 result = session.run(query, params or {})
                                 self.driver = fallback_driver
                                 self.uri = fallback_uri
                                 return [record.data() for record in result]
                         except:
                             pass
            
            raise e

neo4j_db = Neo4jDB()
