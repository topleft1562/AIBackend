from tools.db import users, group_subs, projects, raids

def query_mongo(
    collection: str,
    filter: dict = {},
    sort: dict = None,
    page: int = 1,
    limit: int = 100
):
    skip = (page - 1) * limit
    db_map = {
        "users": users,
        "projects": projects,
        "raids": raids,
        "group_subs": group_subs,

    }

    if collection not in db_map:
        return f"❌ Unknown collection: `{collection}`"

    try:
        cursor = db_map[collection].find(filter)
        if sort:
            cursor = cursor.sort(list(sort.items()))
        results = list(cursor.skip(skip).limit(limit))
        return results
    except Exception as e:
        return f"❌ Mongo query failed: {str(e)}"

def find_one_mongo(collection: str, filter: dict):
    db_map = {
        "users": users,
        "projects": projects,
        "raids": raids,
        "group_subs": group_subs
    }

    if collection not in db_map:
        return f"❌ Unknown collection: `{collection}`"

    try:
        result = db_map[collection].find_one(filter)
        return result or f"❌ No result found with filter: {filter}"
    except Exception as e:
        return f"❌ Mongo find_one failed: {str(e)}"
