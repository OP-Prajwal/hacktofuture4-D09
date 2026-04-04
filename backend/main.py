from fastapi import FastAPI
from db.mongo import mongo
from db.neo4j_db import neo4j_db

app = FastAPI()


@app.get("/test-mongo")
def test_mongo():
    logs = mongo.get_collection("logs")
    logs.insert_one({"msg": "mongo connected"})
    return {"status": "mongo ok"}


@app.get("/test-neo4j")
def test_neo4j():
    result = neo4j_db.run_query("RETURN 'neo4j connected' AS msg")
    return result
