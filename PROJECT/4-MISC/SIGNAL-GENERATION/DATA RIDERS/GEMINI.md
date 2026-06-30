Based on a deep dive into academic repositories, mining challenges, and public data hubs, the short answer is that **a perfect, modern, cross-source dataset (Slack + Calendar + GitHub + Jira) does not exist publicly.** The primary barrier is privacy; companies do not open-source their internal Slack and Calendar data.

However, the Mining Software Repositories (MSR) community has produced a few rigorous datasets that can serve as partial offline evaluation harnesses. Here is the evaluation of the viable candidates:

### 1. SmartSHARK (MSR Dataset)

* **Name & URL:** SmartSHARK ([https://github.com/smartshark](https://github.com/smartshark)) / MSR publications.


* **Hosting Venue:** MongoDB dumps via academic hosting / GitHub tools.


* **License / Usage Terms:** Publicly available for research (Open/Academic).


* **Signals Contained:** Version control (Git commits), Issue tracking (Apache Jira and GitHub issues), Pull requests (including reviews/comments), Continuous Integration (Travis CI), and Mailing list emails.


* **Time Span & Size:** 77 projects, 366k commits, 163k issues, 47k PRs, and 2.9M emails totaling ~1.2 TB of data.


* **Single or Multi-source:** Multi-source and explicitly linked. The dataset establishes verified relational links between Jira issues, Git commits, GitHub PRs, and mailing list discussions.


* **Evaluation Support:**
* *(a) Ranker:* Excellent. Because the data spans email, issue trackers, and code, you can replay the timeline to evaluate if the ranker successfully predicts the next actual commit or email reply based on the preceding context.
* *(b) Dropped-ball:* Very strong. You can easily find cross-system stalls (e.g., an email thread discussing a bug that generates a Jira ticket, which is then abandoned for 6 months before being closed as "Won't Fix").


* **Fit Score:** **4.5 / 5**. This is the single best public dataset for cross-source engineering activity, though it lacks modern chat (Slack) and Calendar data.

### 2. The Public Jira Dataset (MSR 2022)

* **Name & URL:** The Public Jira Dataset ([https://zenodo.org/records/15719919](https://zenodo.org/records/15719919)).


* **Hosting Venue:** Zenodo (MSR 2022 Data Showcase).


* **License / Usage Terms:** Open Access.


* **Signals Contained:** Jira issues, 32 million state changes, 9 million comments, and 1 million issue links. Actor attribution is maintained consistently via UUID4 masking (anonymized but linkable).


* **Time Span & Size:** Extracted from 16 public Jira repositories covering 1,822 projects and 2.7 million issues.


* **Single or Multi-source:** Single-source (Jira only).


* **Evaluation Support:**
* *(a) Ranker:* Poor (lacks the actual execution data like commits).
* *(b) Dropped-ball:* Exceptional. The 32 million state changes allow you to mathematically construct a "stalled" proxy label. You can query for issues that transitioned to "Waiting on User" or "In Progress," experienced a comment gap of >30 days, and were eventually bulk-closed.


* **Fit Score:** **3.5 / 5**.

### 3. GHTorrent / GH Archive

* **Name & URL:** GHTorrent ([http://ghtorrent.org/](http://ghtorrent.org/)) & GH Archive ([https://www.gharchive.org/](https://www.gharchive.org/)).


* **Hosting Venue:** Self-hosted downloads, Zenodo snapshots, and Google BigQuery.


* **License / Usage Terms:** Dual (GitHub API terms + Open Database).


* **Signals Contained:** Commits, PRs, issues, comments, lifecycle events, actor IDs, timestamps.


* **Time Span & Size:** Massive. GHTorrent covers data heavily up to ~2020; GH Archive is ongoing.


* **Single or Multi-source:** Single-source (GitHub only).


* **Evaluation Support:**
* *(a) Ranker:* Moderate. You can rank next actions strictly within the GitHub ecosystem (e.g., predicting who should review a PR or what issue will be addressed next).
* *(b) Dropped-ball:* Good. You can identify PRs that had active review comments (requested changes) but the author never pushed a follow-up commit, resulting in the PR decaying and being closed months later.




* **Fit Score:** **3 / 5**.

### 4. Enron Email Corpus

* **Name & URL:** Enron Email Dataset ([https://www.kaggle.com/datasets/wcukierski/enron-email-dataset](https://www.kaggle.com/datasets/wcukierski/enron-email-dataset)).


* **Hosting Venue:** CMU, Kaggle, Zenodo.


* **License / Usage Terms:** Public Domain (released by FERC).


* **Signals Contained:** Raw email text, timestamps, sender/receiver emails.


* **Time Span & Size:** ~1998-2002, ~500k emails, ~150 users.


* **Single or Multi-source:** Single-source (Email only).


* **Evaluation Support:**
* *(a) Ranker:* Poor. Lacks modern software development context.
* *(b) Dropped-ball:* Moderate. Can be used strictly to test NLP parsing of "delegation" (e.g., "Can you have this to me by Friday?") and measuring if a reply was ever sent in the thread.




* **Fit Score:** **2 / 5**.

### Excluded Datasets

* **ActivityWatch Exports:** While ActivityWatch is a stellar local time-tracker, there is no public, aggregated dataset of user exports available due to the highly sensitive nature of the telemetry.


* **Public Slack/Chat Logs:** Real workplace chat data does not exist in the public domain outside of open-source community support channels (e.g., Ubuntu IRC logs), which lack the explicit task/delegation dynamics of an internal engineering team.



### Final Verdict

**There is no genuinely complete public dataset for this specific system.**

While the **SmartSHARK** dataset is a fantastic academic resource for cross-linking code, tickets, and legacy communication (mailing lists), it critically lacks the real-time synchronous chat (Slack) and time-blocking (Calendar) signals that make your proposed architecture unique.

To rigorously test your system, you will have to **synthesize your own offline evaluation harness**. The most realistic path forward is to build a synthetic generator using an LLM to simulate a week in the life of a mock engineering team, generating intertwined JSON logs for Slack webhook events, GitHub API payloads, and Google Calendar blocks. Alternatively, you will have to dogfood the system yourself and rely on your own SQLite database of logged confirmations as the ultimate oracle.