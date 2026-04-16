from backend.db.mongo import mongo
from dotenv import load_dotenv
load_dotenv()

db = mongo.db

print('Migrating workspaces...')
for ws in list(db.workspaces.find()):
    old_slug = ws.get('slug')
    name = ws.get('name')
    if old_slug and not ws.get('workspace'):
        workspace_id = name.strip() if name else old_slug
        db.workspaces.update_one({'_id': ws['_id']}, {'$set': {'workspace': workspace_id}, '$unset': {'slug': ''}})
        # update associated
        db.users.update_many({'workspace_slug': old_slug}, {'$set': {'workspace': workspace_id}})
        db.users.update_many({'workspace': old_slug}, {'$set': {'workspace': workspace_id}})
        db.projects.update_many({'workspace_slug': old_slug}, {'$set': {'workspace': workspace_id}})
        db.projects.update_many({'workspace': old_slug}, {'$set': {'workspace': workspace_id}})

db.users.update_many({}, {'$unset': {'workspace_slug': ''}})
db.projects.update_many({}, {'$unset': {'workspace_slug': ''}})

print('Finished true migration!')
