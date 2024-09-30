import os
import requests
import datetime
from typing import List, Dict
from dotenv import load_dotenv
import sys
load_dotenv()

GITLAB_URL = os.environ.get("GITLAB_URL", "None")
PERSONAL_ACCESS_TOKEN = os.environ.get("PERSONAL_ACCESS_TOKEN", "None")
PROJECT_ID = os.getenv("PROJECT_ID").split(',')
PROJECT_ID = [int(id) for id in PROJECT_ID]
WORKER_USERNAMES = os.environ.get("WORKER_USERNAME", "None")
print(f"WORKER_USERNAME: {WORKER_USERNAMES}")
print(f"PROJECT_ID: {PROJECT_ID}")

def get_user_id(username: str) -> Dict:
    users_url = f"{GITLAB_URL}/api/v4/users"
    params = {
        'username': username,
        'per_page': 1000,
    }
    headers = {'Private-Token': PERSONAL_ACCESS_TOKEN}
    response = requests.get(users_url,params=params, headers=headers)
    response.raise_for_status()
    user = response.json()
    return {'id': user[0]['id'], 'name': user[0]['name']}

def get_issues(project_id: str, start_date: str, end_date: str) -> List[Dict]:
    issues_url = f"{GITLAB_URL}/api/v4/projects/{project_id}/issues"
    headers = {'Private-Token': PERSONAL_ACCESS_TOKEN}
    user_list = [get_user_id(user) for user in WORKER_USERNAMES.split(',')]
    params = {
        'updated_after': start_date,
        'updated_before': end_date,
        'per_page': 1000,
        'assignee_ids': [user['id'] for user in user_list],
    }
    
    issues = []
    page = 1
    while True:
        params['page'] = page
        response = requests.get(issues_url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        if not data:
            break
        issues.extend(data)
        page += 1
    
    return issues

def get_time_spent_on_issue(issue: Dict, worker_username: str) -> int:
    notes_url = f"{GITLAB_URL}/api/v4/projects/{issue['project_id']}/issues/{issue['iid']}/notes?per_page=1000"
    headers = {'Private-Token': PERSONAL_ACCESS_TOKEN}
    response = requests.get(notes_url, headers=headers)
    response.raise_for_status()
    with open('notes.json', 'a') as f:
        f.write(response.text + '\n')
    notes = response.json()
    time_spent = 0
    is_note_from_curr_month = False
    for note in notes:
        updated_at = datetime.datetime.strptime(note["updated_at"], "%Y-%m-%dT%H:%M:%S.%fZ").date()
        start_date = datetime.date(year, month, 1)
        end_date = (start_date + datetime.timedelta(days=31)).replace(day=1)
        if updated_at < start_date or updated_at > end_date:
            continue
        is_add_time = False
        if note['author']['username'] == worker_username and 'spent' in note['body']:
            words = note['body'].split()
            is_note_from_curr_month = True
            for word in words:
                if word == 'added':
                    is_add_time = True
                elif word == 'subtracted':
                    is_add_time = False
                if word.endswith('h'):
                    if is_add_time:
                        time_spent += int(word[:-1]) * 3600
                    else:
                        time_spent -= int(word[:-1]) * 3600
                elif word.endswith('m'):
                    if is_add_time:
                        time_spent += int(word[:-1]) * 60
                    else:
                        time_spent -= int(word[:-1]) * 60

    if is_note_from_curr_month:
        if time_spent == 0:
            print(f"\033[91m    Issue:{issue['title']}  | time spent: {time_spent // 3600} hours {time_spent % 3600 // 60} minutes\033[0m")
            print(f"\033[91m    '-------> {issue['web_url']}\033[0m")
        else:
            print(f"url: {issue['web_url']} | Issue:{issue['title']}  | time spent: {time_spent // 3600} hours {time_spent % 3600 // 60} minutes")
    return time_spent


def get_project_id_name(project_id) -> Dict:
    project_url = f"{GITLAB_URL}/api/v4/projects/{project_id}"
    headers = {'Private-Token': PERSONAL_ACCESS_TOKEN}
    response = requests.get(project_url, headers=headers)
    response.raise_for_status()
    
    project = response.json()
    return project['name']

def get_worker_time_spent_in_month(project_id: str, worker_username: str, year: int, month: int) -> int:
    start_date = datetime.date(year, month, 1)
    end_date = (start_date + datetime.timedelta(days=31)).replace(day=1)
    
    total_time_spent = 0
    for project_id in PROJECT_ID:
        print("-------------------------------------------------")
        print(f"Project: {get_project_id_name(project_id)}")
        issues = get_issues(project_id, start_date.isoformat(), end_date.isoformat())
        
        for issue in issues:
            total_time_spent += get_time_spent_on_issue(issue, worker_username)
    
    return total_time_spent

if __name__ == '__main__':
    # Get argument input
    if len(sys.argv) != 4:
        print("Usage: python gitlab_project_report.py <year> <month> <business_days>")
        sys.exit(1)

    # Check if the arguments are int
    try:
        int(sys.argv[1])
        int(sys.argv[2])
        int(sys.argv[3])
    except ValueError:
        print("Arguments must be integers")
        sys.exit(1)
    
    year = int(sys.argv[1])
    month = int(sys.argv[2])
    business_days = int(sys.argv[3])
    # year = 2024
    # month = 8
    # business_days = 21
    # IMPORTANT Change for the correct business days | 8 hours per day
    GOAL=business_days*8
    primary_user = WORKER_USERNAMES.split(",")[0]
    # IMPORTANT Change for the correct business days
    total_time_spent = get_worker_time_spent_in_month(PROJECT_ID, primary_user, year, month)
    hours_spent = total_time_spent // 3600
    print("-------------------------------------------------")
    print(f"Total time spent by {primary_user} on all tickets in {year}-{month}: {total_time_spent // 3600} hours {total_time_spent % 3600 // 60} minutes")
    ratio = f"{(hours_spent/GOAL) * 100:.2f}%"
    print(f"Ratio: {ratio}")
    print("-------------------------------------------------")
