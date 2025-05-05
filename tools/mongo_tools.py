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


# ✅ Paginated queries
def query_users(limit: int = 100, skip: int = 0):
    return list(users.find().skip(skip).limit(limit))

def query_projects(limit: int = 100, skip: int = 0):
    return list(projects.find().skip(skip).limit(limit))

def query_raids(limit: int = 100, skip: int = 0):
    return list(raids.find().skip(skip).limit(limit))

def query_group_subs(limit: int = 100, skip: int = 0):
    return list(group_subs.find().skip(skip).limit(limit))
