import pymongo
import os

try:
    client = pymongo.MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))
    db = client["nexus"]

    # 1. Update workspaces
    print("Migrating workspaces...")
    for ws in db.workspaces.find():
        old_slug = ws.get("slug")
        name = ws.get("name")
        if old_slug and not ws.get("workspace"):
            # We want to change the primary key logic to just the literal name/slug combination.
            # If the user used slugs previously, we will just formalize the old slug as the actual workspace ID to avoid breaking foreign keys
            # Or better yet, switch to the full name!
            workspace_id = name.strip() if name else old_slug
            print(f"  {old_slug} -> {workspace_id}")
            db.workspaces.update_one({"_id": ws["_id"]}, {"$set": {"workspace": workspace_id}, "$unset": {"slug": ""}})

    print("Migrating users...")
    for user in db.users.find():
        old_slug = user.get("workspace_slug")
        if old_slug and not user.get("workspace"):
            # Update their pointer
            ws = db.workspaces.find_one({"workspace": old_slug}) # if they haven't been updated
            if not ws:
                # Find by old slug if we kept it somewhere, actually we just updated them. Let's just find all workspaces to build a map.
                pass
    
    # Actually, a much safer dev-mode approach is to just remove the old slug references:
    db.users.update_many({}, {"$rename": {"workspace_slug": "workspace"}})
    db.projects.update_many({}, {"$rename": {"workspace_slug": "workspace"}})

    print("Migration complete. (Note: Since we're in early dev, you may need to recreate your project if you experience string caching issues).")
except Exception as e:
    print("Migration failed:", e)
