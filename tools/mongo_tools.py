from tools.db import users, group_subs, projects
from tools.db import raids

def get_project_by_name(name: str) -> str:
    project = projects.find_one({"name": name})
    return str(project) if project else "Project not found."

def get_project_by_group_id(group_id: int) -> str:
    project = projects.find_one({"groupId": group_id})
    return str(project) if project else "No project found for that group ID."

def query_users():
    return list(users.find().limit(100))

def query_projects():
    return list(projects.find().limit(100))

def query_raids():
    return list(raids.find().limit(100))

def query_group_subs():
    return list(group_subs.find().limit(100))