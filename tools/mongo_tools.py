from tools.db import users, group_subs, projects, raids

def get_user_by_name(name: str) -> str:
    user = users.find_one({
        "$or": [
            {"username": name},
            {"displayName": name}
        ]
    })
    return str(user) if user else "User not found."

def get_user_by_telegram_id(telegram_id: int) -> str:
    user = users.find_one({"telegramId": telegram_id})
    return str(user) if user else "User not found."

def get_project_by_name(name: str) -> str:
    project = projects.find_one({"name": name})
    return str(project) if project else "Project not found."

def get_project_by_group_id(group_id: int) -> str:
    project = projects.find_one({"groupId": group_id})
    return str(project) if project else "No project found for that group ID."


# ✅ Paginated User Query
def query_users(page: int = 1, limit: int = 100):
    skip = (page - 1) * limit
    return list(users.find().skip(skip).limit(limit))

# ✅ Paginated Project Query
def query_projects(page: int = 1, limit: int = 100):
    skip = (page - 1) * limit
    return list(projects.find().skip(skip).limit(limit))

# ✅ Paginated Raid Query
def query_raids(page: int = 1, limit: int = 100):
    skip = (page - 1) * limit
    return list(raids.find().skip(skip).limit(limit))

# ✅ Paginated Group Subscription Query
def query_group_subs(page: int = 1, limit: int = 100):
    skip = (page - 1) * limit
    return list(group_subs.find().skip(skip).limit(limit))

