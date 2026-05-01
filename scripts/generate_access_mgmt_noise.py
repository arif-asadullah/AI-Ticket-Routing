#!/usr/bin/env python3
"""Generate 24 noisy Access Management tickets with realistic human imperfections."""

import json
import random

random.seed(42)

TEMPLATES = [
    ("cant login to {system}", "tryed logging in to {system} multiple times but keeps saying wrong passwrd. i KNOW my password is right!! pls help asap, i have a {urgency} and cant do anything"),
    ("locked out AGAIN", "my account got locked out AGAIN. this is the {nth} time this week. every time i have to call IT and wait 30 mins. cant u guys just turn off the lockout policy or something??"),
    ("{system} SSO not working", "SSO login to {system} just spins and spins, never loads. tried diff browser, same thing. other ppl on my team having same issue. been like this since {time}"),
    ("new hire {name} cant access anything", "we have a new joiner {name} who started {time} and still doesnt have access to {system}. they cant do any work. this is urgent pls"),
    ("password reset not wrking", "tried to reset my password thru the self service portal but it says 'request failed'. tryed 3 times. my old password expired and now im completely locked out of everythng"),
    ("MFA not sending codes", "the MFA txt messages arent coming thru to my phone. i changed my phone {time} and updated my number in the portal but its still sending to old number. HELP"),
    ("permissions wrong after dept change", "i moved from {dept1} to {dept2} {time} but i still have access to {dept1} stuff and cant see {dept2} stuff. my manager already approved the transfer in the system"),
    ("shared service acct {account} failing", "the shared service account {account} that we use for {purpose} is failing with auth errors since {time}. prob password expired. who can reset it? we dont know who owns this acct"),
    ("cant access {system} from vpn", "when im on vpn i cant get to {system}. it says access denied. but in office it works fine. other ppl on vpn can access it. started {time}"),
    ("who approved access for {name}??", "found that {name} (contractor, left {time}) still has admin access to {system}. who approved this?? they shouldve been deprovisioned when their contract ended. URGENT security issue"),
    ("SSO keeps logging me out every {minutes} min", "every {minutes} minutes {system} SSO logs me out and i have to login again. its driving me crazy, i lose all my unsaved work. this started {time}"),
    ("2FA app showing wrong code", "my authenticator app shows a code but when i enter it it says invalid. i think the time on my phone is off or something? cant login to anything that needs MFA"),
]

SYSTEMS = ["Jira", "Confluence", "Slack", "SharePoint", "ServiceNow", "SAP", "Salesforce", "the HR portal", "email", "Teams", "the finance system", "the CRM"]
NAMES = ["Ravi Kumar", "Sarah Chen", "Ahmed Khan", "Lisa Park", "Deepak Sharma", "Maria Garcia"]
TIMES = ["this morning", "yesterday", "last week", "2 days ago", "after lunch", "since monday"]
URGENCY = ["meeting in 1 hour", "client demo today", "deadline tomorrow", "board presentation", "audit review"]
DEPARTMENTS = ["Finance", "Engineering", "Marketing", "Sales", "HR", "Operations"]
ACCOUNTS = ["svc-reports", "svc-etl-prod", "svc-backup", "svc-monitoring", "svc-deploy", "svc-jenkins"]
PURPOSES = ["nightly reports", "data pipeline", "automated deployments", "monitoring dashboards", "CI/CD builds"]
MINUTES = ["5", "10", "15", "20", "30"]


def add_noise(text):
    """Add realistic typos and abbreviations."""
    replacements = {
        "please": "pls", "because": "cuz", "something": "smthng",
        "application": "app", "environment": "env", "password": "passwrd",
        "cannot": "cant", "does not": "doesnt", "is not": "isnt",
        "do not": "dont", "tried": "tryed", "through": "thru",
    }
    for old, new in replacements.items():
        if random.random() < 0.4:
            text = text.replace(old, new)

    # Random letter swap (5% of words)
    words = text.split()
    for i, w in enumerate(words):
        if len(w) > 3 and random.random() < 0.05:
            pos = random.randint(1, len(w) - 2)
            words[i] = w[:pos] + w[pos + 1] + w[pos] + w[pos + 2:]
    text = " ".join(words)

    # Random truncation (10%)
    if random.random() < 0.1:
        sentences = text.split(".")
        if len(sentences) > 2:
            text = ".".join(sentences[:-1])

    # Random irrelevant detail (15%)
    if random.random() < 0.15:
        extras = [
            " btw im using a Dell laptop",
            " my wifi is fine tho",
            " this never happened before the office move",
            " im on windows 11",
            " my colleague sitting next to me is fine",
        ]
        text += random.choice(extras)

    return text


def generate_tickets(count=24):
    tickets = []
    for i in range(count):
        template = random.choice(TEMPLATES)
        title_template, desc_template = template

        params = {
            "system": random.choice(SYSTEMS),
            "name": random.choice(NAMES),
            "time": random.choice(TIMES),
            "urgency": random.choice(URGENCY),
            "dept1": random.choice(DEPARTMENTS),
            "dept2": random.choice([d for d in DEPARTMENTS if d != "Finance"]),
            "account": random.choice(ACCOUNTS),
            "purpose": random.choice(PURPOSES),
            "nth": random.choice(["3rd", "4th", "5th", "2nd"]),
            "minutes": random.choice(MINUTES),
        }

        title = add_noise(title_template.format(**params))
        description = add_noise(desc_template.format(**params))

        priority = random.choices(
            ["critical", "high", "medium", "low"],
            weights=[10, 35, 40, 15],
        )[0]

        tickets.append({
            "title": title,
            "description": description,
            "category": "Access Management",
            "priority": priority,
            "error_codes": [],
            "server_names": [],
            "service_names": ["active-directory"],
            "_source": "synthetic",
            "_generator": "noise-access-mgmt",
        })

    return tickets


if __name__ == "__main__":
    tickets = generate_tickets(24)
    output = "data/synthetic/access_mgmt_noise.json"
    with open(output, "w") as f:
        json.dump(tickets, f, indent=2)
    print(f"Generated {len(tickets)} noisy Access Management tickets → {output}")

    for t in tickets[:3]:
        print(f"\n  Title: {t['title']}")
        print(f"  Desc: {t['description'][:100]}...")
