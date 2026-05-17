# DeskMind — Hackathon Demo Script (~9 minutes)

> **How to use this script:** Don't read it word-for-word. Read each section a few times before recording so the ideas are in your head. The fillers like "so...", "right?", "basically" are there to remind you to speak naturally. The `[pause]` markers mean take a 1-2 second breath.

---

## BEFORE YOU RECORD

- Set screen to **1920x1080** or **1440x900**
- Switch to **light theme** (looks cleaner on video)
- Make sure **Docker containers are running** (`docker compose up`)
- Pre-seed **1-2 tickets** so dashboard isn't empty when you first show it
- Keep this file open on a **second screen** or printed out
- Have the **ticket texts below copied** in a notepad to paste during demo
- Move your **cursor slowly** to what you're explaining

---

## SECTION 1 — INTRO (0:00 - 1:00)

> *[Show the login page on screen]*

Hey everyone... so, my name is Arif, and today I'm going to show you **DeskMind**.

[pause]

So basically... what DeskMind does is — it takes IT support tickets, right? And it automatically figures out which team should handle them. [pause] Like... in most companies, when someone submits a ticket, a human has to read it... understand the problem... and then manually assign it to the right team. That takes time, and honestly... people make mistakes.

[pause]

So what we built is... an **AI-powered system** that does this automatically. And the cool thing is — it doesn't just use one AI model. It uses **four different classifiers** that all vote together. Like... an ensemble. So even if one model is confused, the others can correct it.

[pause]

And everything runs **locally**. No OpenAI, no cloud APIs. Everything is on-premise. So your data stays with you. [pause] Let me show you how it works.

---

## SECTION 2 — LOGIN PAGE (1:00 - 1:30)

> *[Point to the login page]*

So this is the login screen. You can see the three steps here — **Submit**, **Classify**, **Route**. That's basically the whole flow.

[pause]

And these little pills on the side — they show the **system status**. Like... is the AI engine running, is the database connected, is the knowledge graph healthy. So you get a quick health check right here.

[pause]

Let me log in...

> *[Type credentials]*
> - Email: `arif.asadullah@schwettmann.in`
> - Password: `DeskMind@2026`

Okay, I'm logging in as an admin so I can show you everything.

---

## SECTION 3 — DASHBOARD (1:30 - 2:30)

> *[Dashboard loads]*

Alright, so this is the main dashboard. [pause]

You can see we have **six domains** here — Infrastructure, Application Support, Database, Network, Security, and Access Management. Each card shows how many tickets are in that category.

[pause]

And up here... you have the stats bar — total tickets, how many are auto-routed, how many got escalated, average confidence score. [pause]

If I click on a domain card... like Infrastructure... it filters to show only those tickets. And you can switch between **card view** and **list view** — whatever you prefer.

[pause]

Now see these confidence scores on each ticket? The **green ones** — those are high confidence, like 85% or above. The system auto-routed them. The **orange or red ones** — those had lower confidence, so they got **escalated** for human review. [pause] The system knows when it's not sure. That's important.

[pause]

Okay, let me create some tickets live... so you can see the whole classification process happening in real time.

---

## SECTION 4 — CREATE TICKETS (2:30 - 5:30)

---

### TICKET 1 — Infrastructure (Panicked Sysadmin)

> *[Click "Create Ticket" button]*

So let's say... a sysadmin wakes up in the morning and the production server is completely down. Right? That's a bad day.

[pause]

I'm going to fill this in...

> **Copy-paste this:**
> - **Title:** `prod-app-01 server is completely unresponsive since morning`
> - **Description:** `Hi team, this is urgent. Our main production application server prod-app-01 has been completely unresponsive since 6 AM. No SSH access, ping is timing out, and the monitoring dashboard shows the server as offline. Multiple services are affected and customers are reporting errors. We need someone to check the physical server or VMware console immediately. This is impacting production traffic.`
> - **Priority:** Critical

[pause]

Okay, submitting now...

> *[Click Submit]*

So right now... the system is doing a lot of things in the background. [pause]

Let me explain what's happening. So we have **four classifiers** running at the same time — in parallel. [pause]

The first one is the **LLM classifier**. This uses a local Qwen 2.5 model running on Ollama. So it's reading the ticket... understanding the context... and making a prediction. No cloud, no API calls — everything is local.

[pause]

Then we have the **Centroid classifier** — this one takes the ticket text, converts it into a vector using MiniLM embeddings, and compares it against the average vector of each category. So... basically, which category is this ticket closest to in vector space.

[pause]

Then there's **KNN** — K-Nearest Neighbors. This looks at the most similar past tickets and says "hey, those were Infrastructure tickets, so this one probably is too."

And finally... **Keyword matching**. Simple pattern matching — if it sees words like "server", "unresponsive", "VMware", it knows it's probably Infrastructure.

[pause]

All four vote... and the system combines them with weighted scores. LLM gets 40% weight because it understands context best. Centroid gets 30%. KNN and Keywords get 15% each.

> *[Result should appear — check the screen]*

Oh, there we go! [pause] So it classified this as **Infrastructure Operations**... and look at that confidence score. That's a strong classification.

---

### TICKET 2 — Database (Developer)

> *[Click "Create Ticket" again]*

Alright, next one. This time... let's say a developer notices something weird with the database.

> **Copy-paste this:**
> - **Title:** `PostgreSQL replication lag on prod-db-02 keeps growing`
> - **Description:** `Hey, I've been monitoring our PostgreSQL cluster and noticed that the replication lag on prod-db-02 has been steadily increasing over the past 3 hours. It started at a few seconds and now it's over 2 minutes behind the primary. The WAL sender process seems to be struggling. I checked and there's no unusual load on the replica, but the network throughput between primary and replica looks lower than normal. We might need to investigate the replication slot and potentially rebuild if it gets worse.`
> - **Priority:** High

[pause]

Submitting...

> *[Click Submit]*

So while that's classifying... let me talk about something interesting. [pause]

One of the hard problems in ticket routing is — **root cause versus symptom**. Right? Like... this ticket mentions "network throughput" and "replication lag." A simpler system might get confused — is this a Network issue or a Database issue?

[pause]

But DeskMind's ensemble approach handles this well because... the LLM actually understands that replication lag is fundamentally a **database problem**, even though network is mentioned. And the centroid classifier has seen similar tickets before — it knows the vector is closer to Database Admin than to Network Engineering.

[pause]

So even though the ticket mentions networking stuff... the system looks at the **root cause**, not just the keywords. That's the power of combining multiple classifiers.

> *[Result should appear]*

And there it is — **Database Admin**. With a solid confidence score. [pause] Exactly what we expected.

---

### TICKET 3 — Security (IT Manager)

> *[Click "Create Ticket"]*

Okay, this one's a security scenario. An IT manager notices something suspicious.

> **Copy-paste this:**
> - **Title:** `Multiple failed login attempts detected on API Gateway`
> - **Description:** `Our SIEM dashboard is showing an unusual spike in failed authentication attempts against the main API Gateway over the last hour. We're seeing roughly 500 failed attempts from about 15 different IP addresses, mostly from regions where we don't have any users. The pattern looks like a credential stuffing attack. The API Gateway is still functional but I'm concerned about a potential breach. We need to review the access logs, potentially block the suspicious IPs at the WAF level, and check if any accounts were actually compromised.`
> - **Priority:** Critical

[pause]

Submitting this one...

> *[Click Submit]*

So while this runs... let me tell you about something called **graceful degradation** in DeskMind. [pause]

So what happens if... the LLM goes down? Like, Ollama crashes or the model runs out of memory. Right? In most AI systems, that's a problem — the whole thing breaks.

[pause]

But DeskMind has **four levels of fallback**. [pause] Level one is the full pipeline — all four classifiers working. Level two is... if the LLM is down, the remaining three classifiers automatically rebalance their weights and still give you a classification. Level three is... if even the embedding model is down, it falls back to just keyword matching plus whatever is available. And level four — worst case — just keyword matching alone.

[pause]

So the system **never completely breaks**. It just... gracefully degrades. The confidence score might be lower, but you still get a classification. And the system tells you — "hey, I'm running in degraded mode."

> *[Result should appear]*

There we go — **Security Operations**. [pause] That's right. And notice the confidence... it's quite high for this one because all the signals are very clear — SIEM, credential stuffing, WAF, breach... all security terms.

---

### TICKET 4 — Network (Remote Worker) *(if time allows)*

> *[Click "Create Ticket"]*

One more quick one. A remote worker having VPN issues.

> **Copy-paste this:**
> - **Title:** `VPN keeps disconnecting every 10-15 minutes`
> - **Description:** `Hi, I've been working remotely and for the past two days my VPN connection keeps dropping every 10-15 minutes. I'm using the Cisco AnyConnect client on Windows. When it disconnects I have to manually reconnect and it interrupts all my work. I've tried restarting the client, rebooting my laptop, and even switching from WiFi to a wired connection, but the issue persists. Other people in my team don't seem to have this issue. Could someone from the network team look into my VPN profile or the concentrator logs?`
> - **Priority:** High

[pause]

Submitting... same process running. The four classifiers are doing their thing. Should have a result in a moment.

> *[Wait for result]*

And... **Network Engineering**. [pause] Great. So you can see the system handles different domains really well.

---

## SECTION 5 — TICKET DETAIL VIEW (5:30 - 6:15)

> *[Click on one of the tickets you just created — preferably Ticket 1 or 2]*

Now let me click into a ticket to show you the detail view. [pause]

So here... you can see the full ticket information. But the interesting part is down here — the **classifier breakdown**. [pause]

You can see all **four classifiers** and how each one voted. Like... the LLM said Infrastructure with this score... Centroid said Infrastructure with this score... KNN agreed... Keywords agreed. And then the final weighted score.

[pause]

And here's the **AI reasoning**. The system explains WHY it made this decision. This is really important for enterprise use — you need **explainability**. If someone asks "why did DeskMind route this to Infrastructure?", you have a clear answer. It's not a black box.

[pause]

There's also an **audit trail** — who created it, when it was classified, what the original scores were. Full transparency. Every decision is traceable.

---

## SECTION 6 — ANALYTICS (6:15 - 7:00)

> *[Click on "Analytics" tab]*

Okay, let me show you the analytics page. [pause]

So this gives you a bird's-eye view of everything happening in the system. [pause]

This bar chart shows **tickets by category** — you can see which domains are getting the most tickets. [pause]

These donut charts show **status distribution** and **priority distribution**. So you can quickly see... how many tickets are open, resolved, escalated... and how many are critical versus high versus medium.

[pause]

And this one is my favorite — **confidence by category**. See this line here at **70%**? That's our threshold. Anything above 70% gets auto-routed. Anything below gets escalated for human review. [pause] You can see most categories are well above the line. That means the system is confident in its decisions.

[pause]

And this line chart shows the **daily volume trend** — how many tickets are coming in over time.

---

## SECTION 7 — KNOWLEDGE GRAPH (7:00 - 7:45)

> *[Click on "Graph" tab]*

Now this... this is the knowledge graph. [pause] And this is really the backbone of DeskMind.

So what you see here is a visual representation of our **entire IT organization**. [pause]

The **blue nodes** are teams. The **green nodes** are engineers. **Orange** are servers. **Purple** are services. And so on.

[pause]

If I hover over a node... see how the connections highlight? So you can see which engineers belong to which team... which servers are managed by which team... which services run on which servers.

> *[Click on a team node]*

And if I click on a team... I get this detail panel. It shows the team info, the engineers, their skills, what they're responsible for.

[pause]

Now here's the important thing — this graph is **not just visualization**. The classification engine actually **uses** this graph during routing. It knows that if a ticket is about PostgreSQL, and the Database Admin team has engineers with PostgreSQL expertise... that's where the ticket should go. The knowledge graph provides **real context** to the AI.

> *[Show filter by category, zoom controls]*

You can filter by category, zoom in, zoom out... explore the relationships.

---

## SECTION 8 — MINDY AI CHAT (7:45 - 8:45)

> *[Click the floating "Ask Mindy" button in bottom-right]*

Okay, last feature — this is **Mindy**, our AI assistant. [pause]

So Mindy lets you ask questions about the system in natural language. But here's the thing — Mindy has **zero hallucination**. [pause]

How? Because... it doesn't just send your question to an LLM and hope for the best. It uses a **rule-based intent parser** first — figures out what you're asking. Then it queries the **ArangoDB database** directly to get real data. And then... the LLM only formats the response in a nice way. So every answer is backed by actual data.

[pause]

Let me show you...

> **Type:** `what is the status of ticket #206129`

[pause — wait for response]

See? It gives me the ticket details with these nice **colored chips**. Orange for tickets, green for engineers, blue for teams. And all of these are clickable.

> **Type:** `which team handles database issues`

[pause — wait for response]

So it pulled the team name and the engineers — **Arjun Nair** and **Meera Patel**. All from the knowledge graph, all real data.

> **Type:** `how many tickets are escalated right now`

[pause — wait for response]

Real-time stats. Not hallucinated. This is actual data from the database. [pause]

That's the key difference with Mindy — every single answer comes from real data. The LLM never makes things up because it never has to. It just formats what the database returns.

---

## SECTION 9 — CLOSING (8:45 - 9:30)

> *[Go back to dashboard]*

Alright, so... let me quickly recap what makes DeskMind different. [pause]

**One** — the **4-classifier ensemble**. Not one AI model, four. They vote together for higher accuracy.

**Two** — the **knowledge graph**. It's not just a visual thing, it actually powers the classification with real organizational context.

**Three** — **zero hallucination** in the AI chat. Rule-based parsing, real database queries, LLM only formats.

**Four** — everything is **on-premise**. Local LLM, local embeddings, no cloud APIs. Your data stays with you.

And **five** — full **explainability**. Every decision has an audit trail. Every classification shows you why.

[pause]

So yeah... that's DeskMind. An intelligent IT ticket routing system that's accurate, transparent, and private.

[pause]

Thank you for watching.

---

---

# QUICK REFERENCE — COPY-PASTE TICKETS

Keep these in a notepad file so you can quickly copy-paste during recording.

## Ticket 1 — Infrastructure
```
Title: prod-app-01 server is completely unresponsive since morning

Description: Hi team, this is urgent. Our main production application server prod-app-01 has been completely unresponsive since 6 AM. No SSH access, ping is timing out, and the monitoring dashboard shows the server as offline. Multiple services are affected and customers are reporting errors. We need someone to check the physical server or VMware console immediately. This is impacting production traffic.

Priority: Critical
```

## Ticket 2 — Database
```
Title: PostgreSQL replication lag on prod-db-02 keeps growing

Description: Hey, I've been monitoring our PostgreSQL cluster and noticed that the replication lag on prod-db-02 has been steadily increasing over the past 3 hours. It started at a few seconds and now it's over 2 minutes behind the primary. The WAL sender process seems to be struggling. I checked and there's no unusual load on the replica, but the network throughput between primary and replica looks lower than normal. We might need to investigate the replication slot and potentially rebuild if it gets worse.

Priority: High
```

## Ticket 3 — Security
```
Title: Multiple failed login attempts detected on API Gateway

Description: Our SIEM dashboard is showing an unusual spike in failed authentication attempts against the main API Gateway over the last hour. We're seeing roughly 500 failed attempts from about 15 different IP addresses, mostly from regions where we don't have any users. The pattern looks like a credential stuffing attack. The API Gateway is still functional but I'm concerned about a potential breach. We need to review the access logs, potentially block the suspicious IPs at the WAF level, and check if any accounts were actually compromised.

Priority: Critical
```

## Ticket 4 — Network
```
Title: VPN keeps disconnecting every 10-15 minutes

Description: Hi, I've been working remotely and for the past two days my VPN connection keeps dropping every 10-15 minutes. I'm using the Cisco AnyConnect client on Windows. When it disconnects I have to manually reconnect and it interrupts all my work. I've tried restarting the client, rebooting my laptop, and even switching from WiFi to a wired connection, but the issue persists. Other people in my team don't seem to have this issue. Could someone from the network team look into my VPN profile or the concentrator logs?

Priority: High
```

## Ticket 5 — Access Management (optional)
```
Title: Can't access Jira and Confluence after department transfer

Description: Hi, I recently transferred from the Marketing department to Engineering last week. My manager submitted the department transfer form but I still can't access any of the Engineering team's Jira projects or Confluence spaces. I can see my old Marketing projects but when I try to access Engineering boards I get "You don't have permission." I need access to the sprint board and the technical documentation space urgently as I'm starting a new project on Monday.

Priority: Medium
```

---

# MINDY CHAT QUESTIONS

```
what is the status of ticket #206129
```
```
which team handles database issues
```
```
how many tickets are escalated right now
```
```
show me all infrastructure tickets
```

---

# LOGIN CREDENTIALS

- **Email:** `arif.asadullah@schwettmann.in`
- **Password:** `DeskMind@2026`
