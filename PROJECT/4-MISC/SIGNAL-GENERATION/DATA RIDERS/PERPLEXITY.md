There are several reasonably close public fits (especially around GitHub/Jira/Bugzilla and Enron-style email), but nothing that cleanly covers *all* of the modalities you want (code, tickets, calendar, chat, email, time-tracking) in one joined corpus with gold labels for “dropped ball.” You can, however, get quite far on offline evaluation for (1) next-action ranking and (2) stalled/delegated detection using a small set of software-repository and email datasets, plus some light synthesis and labeling logic on top. [gharchive](https://www.gharchive.org)

Below I’ll walk through the most relevant datasets by your requested venues, then give an overall verdict.

***

## GH Archive (GitHub public events)

**Name / URL / venue / license**

- GH Archive – GitHub public timeline  
  - Site: https://www.gharchive.org [gharchive](https://www.gharchive.org)
  - BigQuery mirror (githubarchive dataset) and other mirrors (e.g., Kaggle, Alibaba MaxCompute). [kaggle](https://www.kaggle.com/datasets/programmerrdai/gh-archive-github-public-timeline-data)
  - License: The archive itself is open for analysis; underlying events are public GitHub data governed by GitHub’s terms of service (research / analysis generally allowed, re-publication of full content more sensitive). GH Archive itself does not impose a restrictive license beyond that. [github](https://github.com/igrigorik/gharchive.org)

**Signals**

- Event types: GitHub “public events” stream, e.g. PushEvent, IssuesEvent, IssueCommentEvent, PullRequestEvent, PullRequestReviewEvent, PullRequestReviewCommentEvent, CreateEvent, ForkEvent, WatchEvent, etc. [cs.uwaterloo](https://cs.uwaterloo.ca/~m2nagapp/courses/CS846/1171/papers/gousios_msr12.pdf)
- Fields per event (in the BigQuery schema or raw JSON):  
  - Timestamps to second resolution (created_at). [github](https://github.com/igrigorik/gharchive.org/blob/master/bigquery/README.md)
  - Actor: actor.login (user), plus actor id in BigQuery. [github](https://github.com/igrigorik/gharchive.org/blob/master/bigquery/README.md)
  - Repo: repo.name, repo.id. [github](https://github.com/igrigorik/gharchive.org/blob/master/bigquery/README.md)
  - Payload with issue/PR numbers, action (“opened”, “closed”, “reopened”, “synchronize”), comment bodies, etc. [cs.uwaterloo](https://cs.uwaterloo.ca/~m2nagapp/courses/CS846/1171/papers/gousios_msr12.pdf)
- Granularity: Hourly archives, covering all public GitHub activity since 2011. [firebolt](https://www.firebolt.io/blog/analyzing-the-github-events-dataset-using-firebolt-querying-with-streamlit)

**Time span / size**

- Continuous from 2011 onward; since 2015 the dataset has more than 5 billion events and keeps growing. [firebolt](https://www.firebolt.io/blog/analyzing-the-github-events-dataset-using-firebolt-querying-with-streamlit)

**Single vs multi-source / linkability**

- Single source (GitHub), but internally multi-entity: repos, issues, PRs, comments, pushes, stars are all linkable via repo + issue/PR numbers and IDs. [cs.uwaterloo](https://cs.uwaterloo.ca/~m2nagapp/courses/CS846/1171/papers/gousios_msr12.pdf)
- You can reconstruct per-issue/PR timelines and per-user activity streams.

**Usefulness for your tasks**

- (a) **Next-action ranker**:  
  - For a given actor and time, you can build their set of open issues/PRs and recently touched entities and derive a “next action they actually took” as a weak label (e.g., which PR they commented on or pushed to next). [gharchive](https://www.gharchive.org)
  - Per-issue event sequences let you define candidate states like “review needed”, “tests failing”, “awaiting maintainer reply” and see which issue/PR got activity next.  
- (b) **Dropped-ball / stalled-delegation detection**:  
  - Issues and PRs have open/close events plus comments; you can compute idle intervals (no comments, no commits referencing the issue, no status changes) and define “stalled” heuristics (e.g., open > N days with no activity after an assignment/change of assignee). [cs.uwaterloo](https://cs.uwaterloo.ca/~m2nagapp/courses/CS846/1171/papers/gousios_msr12.pdf)
  - Delegation proxy: issues/PRs often have assignees or requested reviewers; for each assignee, track whether they respond (comment, review, push) within some SLA window. [cs.uwaterloo](https://cs.uwaterloo.ca/~m2nagapp/courses/CS846/1171/papers/gousios_msr12.pdf)
- Signals that stand in for “went stale”:  
  - Long gaps between any events on a still-open issue/PR.  
  - Event sequences where a reviewer is requested but no review event occurs within X days.  
  - Issues closed by someone else or after very long delay following assignment.

**Fit score**

- **4/5** – Extremely rich timestamped event stream with actors and clear task entities; excellent for code/issue/PR oriented ranking and stall detection, but missing non-GitHub modalities (email, calendar, chat, etc.). [firebolt](https://www.firebolt.io/blog/analyzing-the-github-events-dataset-using-firebolt-querying-with-streamlit)

***

## GHTorrent (GitHub offline mirror)

**Name / URL / venue / license**

- GHTorrent – “GitHub’s Data from a Firehose” project. [gousios](https://gousios.org/bibliography/G13.html)
- Info: https://gousios.org/bibliography/G13.html [gousios](https://gousios.org/bibliography/G13.html)
- Data: downloadable dumps / services from GHTorrent project sites (relational DB and Mongo snapshots). [gousios](https://gousios.org/bibliography/G13.html)
- License: Offered to the research community for analysis; underlying data subject to GitHub terms; Gousios’ paper presents it as an open research dataset. [gousios](https://gousios.org/bibliography/G13.html)

**Signals**

- Mirrors GitHub REST API objects: users, repos, commits, issues, issue comments, pull requests, pull request comments, etc. [cs.uwaterloo](https://cs.uwaterloo.ca/~m2nagapp/courses/CS846/1171/papers/gousios_msr12.pdf)
- Rich relational schema with foreign keys connecting events to issues/PRs and users. [cs.uwaterloo](https://cs.uwaterloo.ca/~m2nagapp/courses/CS846/1171/papers/gousios_msr12.pdf)
- Timestamps on issues, comments, PRs, commits, etc., plus actor IDs. [cs.uwaterloo](https://cs.uwaterloo.ca/~m2nagapp/courses/CS846/1171/papers/gousios_msr12.pdf)

**Time span / size**

- Large multi-year coverage across millions of repos and users; the paper describes it as a scalable offline mirror, not limited to a small sample. [gousios](https://gousios.org/bibliography/G13.html)

**Single vs multi-source / linkability**

- Single platform (GitHub); but better normalized than GH Archive for cross-linking issues, PRs, comments, and commits. [cs.uwaterloo](https://cs.uwaterloo.ca/~m2nagapp/courses/CS846/1171/papers/gousios_msr12.pdf)
- Easier to reconstruct per-project and per-user timelines and state transitions using SQL.

**Usefulness**

- (a) **Next-action ranker**:  
  - Same story as GH Archive, but easier to do structured joins (e.g., listing all open PRs assigned to a user and seeing which they actually touched next) because of the relational schema. [cs.uwaterloo](https://cs.uwaterloo.ca/~m2nagapp/courses/CS846/1171/papers/gousios_msr12.pdf)
- (b) **Dropped-ball / delegation**:  
  - Use assignee fields and pull-request review requests; compute time to first response and identify items that exceed thresholds or get re-assigned/closed by others. [cs.uwaterloo](https://cs.uwaterloo.ca/~m2nagapp/courses/CS846/1171/papers/gousios_msr12.pdf)
  - Issue state changes (open/closed/reopened) plus comments give a solid basis for idle-period detection.  
- “Went stale” proxies:  
  - Issues/PRs with long idle periods after an assignment or reviewer request.  
  - PRs abandoned and eventually closed without merge or only after a very long time.

**Fit score**

- **4/5** – Similar capabilities to GH Archive but arguably better structured for relational analysis; same limitation around single modality (code/issue/PR only). [gousios](https://gousios.org/bibliography/G13.html)

***

## Jira issue-tracking datasets (Apache & multi-project)

### Apache Jira Issue Tracking Dataset (Zenodo)

**Name / URL / venue / license**

- “Apache Jira Issue Tracking Dataset” on Zenodo. [zenodo](https://zenodo.org/records/14253918)
- URL: https://zenodo.org/records/14253918 [zenodo](https://zenodo.org/records/14253918)
- Venue: Zenodo.  
- License: Not fully quoted in the snippet, but Zenodo datasets typically specify an explicit license (often CC BY or similar); this record is published as a dataset for research use. [zenodo](https://zenodo.org/records/14253918)

**Signals**

- Contains Jira issue tracking data for Apache Software Foundation projects. [zenodo](https://zenodo.org/records/14253918)
- Stored as MongoDB dump; includes issues, their metadata and comments, enriched with BERTopic topics. [zenodo](https://zenodo.org/records/14253918)
- Jira issues typically include:  
  - Timestamps for creation, updates, status changes, resolution.  
  - Reporter, assignee, commenters, and possibly watchers.  
  - Status field (Open, In Progress, Resolved, Closed, etc.) representing state transitions over time.  

**Time span / size**

- Coverage across Apache projects; the Zenodo record describes it as issue tracking data for Apache’s Jira instance, with large scale (millions of issues implied). [zenodo](https://zenodo.org/records/14253918)
- Exact span not in the snippet, but Apache Jira has been running for many years, so expect a long time range.

**Single vs multi-source / linkability**

- Single-source issue-tracker data, but within Jira you can trace issues over time and across participants (reporter, assignee, commenters). [zenodo](https://zenodo.org/records/14253918)
- Potential to join with GitHub (for projects that sync Jira issue IDs into commit messages or PR titles), though this requires your own linkage logic.

**Usefulness**

- (a) **Next-action ranker**:  
  - Construct snapshots of all open issues for a given assignee at time t using status and assignee fields.  
  - Use the next issue that assignee updates or transitions (comment, status change) as the “chosen next task” label. [zenodo](https://zenodo.org/records/14253918)
- (b) **Dropped-ball / delegation**:  
  - Use status field transitions plus timestamps to find issues that sit in “In Progress” or “Assigned” with no updates for long periods. [zenodo](https://zenodo.org/records/14253918)
  - Delegation proxy: issues reassigned multiple times or closed by someone other than the assignee after a long idle period.  
- “Went stale” proxies:  
  - No status or comment changes for N days while issue remains open/assigned.  
  - Issues escalated or reassigned after inactivity.

**Fit score**

- **4/5** – Very strong single-modality task-tracking dataset with good actor and timeline signals; no commits/chat/email, but ideal to stress-test rankers on ticket workflows. [zenodo](https://zenodo.org/records/14253918)

### Alternative public Jira dataset (multi-instances)

**Name / URL / venue / license**

- “An alternative issue tracking dataset of public Jira repositories” (paper + dataset). [dl.acm](https://dl.acm.org/doi/10.1145/3524842.3528486)
- The paper states they release a dataset of 16 public Jira instances with 2.7M issues. [dl.acm](https://dl.acm.org/doi/10.1145/3524842.3528486)
- Venue: ACM / downloadable dataset referenced by the paper. [dl.acm](https://dl.acm.org/doi/10.1145/3524842.3528486)
- License: Provided as a research dataset; details in the paper’s dataset site (usually research use with attribution). [dl.acm](https://dl.acm.org/doi/10.1145/3524842.3528486)

**Signals**

- Coverage: 2.7 million issues, 32 million changes, 9 million comments, 1 million attachments across 1822 projects in 16 public Jira instances. [dl.acm](https://dl.acm.org/doi/10.1145/3524842.3528486)
- Contains change history, so you get status transitions, assignments, comments with timestamps and actors. [dl.acm](https://dl.acm.org/doi/10.1145/3524842.3528486)

**Time span / size**

- Large multi-year coverage; 2.7M+ issues and 32M changes indicates significant scale. [dl.acm](https://dl.acm.org/doi/10.1145/3524842.3528486)

**Single vs multi-source / linkability**

- Multiple Jira servers, but still all “Jira-style” issue-tracking data. [dl.acm](https://dl.acm.org/doi/10.1145/3524842.3528486)
- Within each project you can reconstruct per-issue and per-user event streams across statuses and comments.

**Usefulness**

- (a) **Next-action ranker**:  
  - Same strategy as Apache Jira dataset, but more diverse projects and workflows; good for generalization testing. [dl.acm](https://dl.acm.org/doi/10.1145/3524842.3528486)
- (b) **Dropped-ball / delegation**:  
  - Rich history of changes and comments allows you to derive bespoke “stalled” labels at both issue and assignee level.  
- “Went stale” proxies:  
  - Issues with long gaps between any changes while in an “active” state.  
  - Issues covered by escalations or reassignments.

**Fit score**

- **4/5** – Excellent coverage and change histories; again, pure issue tracking, not multi-modality, but highly suitable for offline evaluation of ranking and stall-detection heuristics. [dl.acm](https://dl.acm.org/doi/10.1145/3524842.3528486)

***

## Bugzilla / Eclipse bug datasets

### Eclipse Bugzilla bug report dataset

**Name / URL / venue / license**

- “Software bug report dataset from Eclipse projects” described in a 2025 paper. [pmc.ncbi.nlm.nih](https://pmc.ncbi.nlm.nih.gov/articles/PMC12545829/)
- Hosted via an associated dataset (referenced in the paper) and via Zenodo as “Eclipse issue report dataset.” [zenodo](https://zenodo.org/records/15348468)
- Zenodo record: “Eclipse issue report dataset” [zenodo](https://zenodo.org/records/15348468)
- License: Published on Zenodo for software engineering research; typically a permissive research license (exact license on record). [zenodo](https://zenodo.org/records/15348468)

**Signals**

- 301,378 bug reports from Eclipse Bugzilla with all related information. [pmc.ncbi.nlm.nih](https://pmc.ncbi.nlm.nih.gov/articles/PMC12545829/)
- Fields: bug creation and update timestamps, statuses, resolutions, components, comments, etc. [pmc.ncbi.nlm.nih](https://pmc.ncbi.nlm.nih.gov/articles/PMC12545829/)
- Actor info: reporter, assignee, commenters. [pmc.ncbi.nlm.nih](https://pmc.ncbi.nlm.nih.gov/articles/PMC12545829/)

**Time span / size**

- Covers “the earliest Bugzilla records up to November 2024,” with 301,378 bug reports across multiple Eclipse projects. [pmc.ncbi.nlm.nih](https://pmc.ncbi.nlm.nih.gov/articles/PMC12545829/)

**Single vs multi-source / linkability**

- Single-source bug-tracking but across many Eclipse projects. [pmc.ncbi.nlm.nih](https://pmc.ncbi.nlm.nih.gov/articles/PMC12545829/)
- Full histories enable detailed state-transition reconstruction.

**Usefulness**

- (a) **Next-action ranker**:  
  - Similar to Jira: snapshot open bugs for an assignee; use next update they perform as the positive label. [pmc.ncbi.nlm.nih](https://pmc.ncbi.nlm.nih.gov/articles/PMC12545829/)
- (b) **Dropped-ball / delegation**:  
  - Identify bugs with long intervals without comments or status changes while assigned to someone. [pmc.ncbi.nlm.nih](https://pmc.ncbi.nlm.nih.gov/articles/PMC12545829/)
- “Went stale” proxies:  
  - Bugs remaining open in certain states (e.g., “NEW”, “ASSIGNED”) for long durations.  
  - Reassignment after inactivity.

**Fit score**

- **3.5/5** – Very good for single-modality bug workflows; slightly weaker than the massive Jira datasets for scale, but more than enough to stress-test ranking and stall heuristics. [zenodo](https://zenodo.org/records/15348468)

***

## Enron email and email-thread datasets

### Enron Email Corpus (multiple variants)

**Name / URL / venue / license**

- Enron Email Dataset / Enron Corpus.  
  - Overview: WAC Clearinghouse description. [wacclearinghouse](https://wacclearinghouse.org/jwa/corpora/enron/)
  - Structured versions on Hugging Face (e.g., `corbt/enron-emails`). [wacclearinghouse](https://wacclearinghouse.org/jwa/corpora/enron/)
- Also: Cornell “email-Enron” temporal network dataset with timestamps in milliseconds. [cs.cornell](https://www.cs.cornell.edu/~arb/data/email-Enron/)
- License: Publicly available for non-commercial research use; distributed as TXT and CSV. [wacclearinghouse](https://wacclearinghouse.org/jwa/corpora/enron/)

**Signals**

- Approximately 500,000 email messages sent/received by about 150 Enron employees between 1998 and 2002. [wacclearinghouse](https://wacclearinghouse.org/jwa/corpora/enron/)
- Each message:  
  - Timestamp (date header; some processed versions give epoch or millisecond timestamps). [cs.cornell](https://www.cs.cornell.edu/~arb/data/email-Enron/)
  - Sender, recipients (To, Cc, Bcc).  
  - Subject, body.  
- Actor attribution: sender and receiver addresses. [cs.cornell](https://www.cs.cornell.edu/~arb/data/email-Enron/)
- Threading:  
  - Some variants include conversation/thread IDs or can be reconstructed via subject/“In-Reply-To” heuristics; separate research datasets explicitly annotate threading for Enron (“Enron-Meetings,” etc.). [cs.cmu](https://www.cs.cmu.edu/~einat/datasets.html)

**Time span / size**

- About 1998–2002; ~500k messages across ~150 users. [wacclearinghouse](https://wacclearinghouse.org/jwa/corpora/enron/)

**Single vs multi-source / linkability**

- Single modality (email), but with rich interpersonal network and (in some variants) thread annotations between messages. [cs.cmu](https://www.cs.cmu.edu/~einat/datasets.html)
- No direct linkage to code/issue trackers.

**Usefulness**

- (a) **Next-action ranker**:  
  - For each user, you can reconstruct their email queue (all unresolved threads / unanswered messages) and see which thread they respond to next in time. [cs.cornell](https://www.cs.cornell.edu/~arb/data/email-Enron/)
  - Build “task-like” entities as email threads or subject groups and track user’s next reply as the chosen action.  
- (b) **Dropped-ball / delegation**:  
  - Delegation proxies: emails that request something (you’d detect likely requests via heuristics or manual labeling) and never get a reply from the addressee, or get a very delayed response. [wacclearinghouse](https://wacclearinghouse.org/jwa/corpora/enron/)
  - Stalled conversation threads that never get follow-up from the person expected to respond.  
- “Went stale” proxies:  
  - Threads where a user is addressed but never sends a reply in that thread.  
  - Long time gaps between messages in a thread, especially if the last one is a request.  

**Fit score**

- **3.5/5** – Strong for email-only ranking and dropped-ball proxies; lacks direct artifact or task identifiers (tickets, PRs), but good to test whether your heuristics generalize beyond code/ticket systems. [cs.cmu](https://www.cs.cmu.edu/~einat/datasets.html)

### Enron-Meetings / threaded variants

**Name / URL / venue / license**

- CMU “Email Datasets: person name disambiguation and threading” page includes Enron-Meetings (messages from folders named “meetings” or “calendar”). [cs.cmu](https://www.cs.cmu.edu/~einat/datasets.html)
- Venue: CMU course/dataset page. [cs.cmu](https://www.cs.cmu.edu/~einat/datasets.html)
- License: Distributed for research; derived from Enron corpus and subject to similar non-commercial constraints. [cs.cmu](https://www.cs.cmu.edu/~einat/datasets.html)

**Signals**

- Focused subset of Enron messages related to meetings and calendar content, with annotations for personal name disambiguation and threading. [cs.cmu](https://www.cs.cmu.edu/~einat/datasets.html)
- Timestamps, sender, recipients, subject, etc., plus thread-structure information. [cs.cmu](https://www.cs.cmu.edu/~einat/datasets.html)

**Usefulness**

- More specific to meeting coordination; useful for modeling delegation and follow-up around scheduling tasks.  
- You can treat each meeting thread as a task and model who responds, who fails to, and delays.

**Fit score**

- **3/5** – Narrower than full Enron but more task-like for meetings; useful as a focused testbed for scheduling-related next-action and dropped-ball detection. [cs.cmu](https://www.cs.cmu.edu/~einat/datasets.html)

***

## Mixed / semantically enriched Jira dataset (Jira-social-repository)

**Name / URL / venue / license**

- `jira-social-repository` GitHub project. [github](https://github.com/marcoortu/jira-social-repository)
- URL: https://github.com/marcoortu/jira-social-repository [github](https://github.com/marcoortu/jira-social-repository)
- Contains datasets from Jira issue trackers of several open source ecosystems (Apache, Spring, JBoss, CodeHaus). [github](https://github.com/marcoortu/jira-social-repository)
- License: Provided in a public GitHub repo for research; check repo for exact license (likely MIT/CC for the derived dataset).  

**Signals**

- Data extracted from Jira issue tracking systems for four open source ecosystems. [github](https://github.com/marcoortu/jira-social-repository)
- Includes issues, comments, and social network relationships derived from the interactions. [github](https://github.com/marcoortu/jira-social-repository)
- Timestamps for issue creation and updates, commenter identities, etc. [github](https://github.com/marcoortu/jira-social-repository)

**Time span / size**

- Not detailed in the snippet, but includes many projects; enough scale for research. [github](https://github.com/marcoortu/jira-social-repository)

**Single vs multi-source / linkability**

- Single-source (Jira), but enriched with social network edges between participants. [github](https://github.com/marcoortu/jira-social-repository)

**Usefulness**

- (a) **Next-action ranker**:  
  - Similar approach to other Jira datasets; you also get social signals (e.g., who tends to respond to whom). [github](https://github.com/marcoortu/jira-social-repository)
- (b) **Dropped-ball / delegation**:  
  - Social network features can help model responsibilities and typical responders, improving detection of unusual non-response.  

**Fit score**

- **3.5/5** – Good but somewhat overlapping with the other, larger Jira datasets; main additional value is the social graph. [github](https://github.com/marcoortu/jira-social-repository)

***

## Kaggle datasets (relevant ones only)

Kaggle has many GitHub-related datasets, but the one most aligned with your needs is essentially a repackaged slice of GH Archive.

**Name / URL / venue / license**

- “GH Archive: GitHub Public Timeline Data” on Kaggle. [kaggle](https://www.kaggle.com/datasets/programmerrdai/gh-archive-github-public-timeline-data)
- Venue: Kaggle Datasets (user `programmerrdai`). [kaggle](https://www.kaggle.com/datasets/programmerrdai/gh-archive-github-public-timeline-data)
- License: Kaggle dataset license (often CC0 or CC BY for the packaging; underlying events still GitHub-governed). [kaggle](https://www.kaggle.com/datasets/programmerrdai/gh-archive-github-public-timeline-data)

**Signals, time span, usefulness**

- Same structure as GH Archive; it’s an easier entry point if you prefer parquet/CSV from Kaggle rather than BigQuery or raw hourly JSON. [kaggle](https://www.kaggle.com/datasets/programmerrdai/gh-archive-github-public-timeline-data)

**Fit score**

- **3.5/5** – Primarily a convenience wrapper; underlying signal identical to GH Archive. [gharchive](https://www.gharchive.org)

***

## MSR Mining Challenge / agent-authored PR dataset (AIDev)

**Name / URL / venue / license**

- MSR 2026 Mining Challenge dataset “AIDev” (agent-authored pull requests) hosted on Hugging Face / Zenodo. [2026.msrconf](https://2026.msrconf.org/track/msr-2026-mining-challenge)
- Info: https://2026.msrconf.org/track/msr-2026-mining-challenge [2026.msrconf](https://2026.msrconf.org/track/msr-2026-mining-challenge)
- License: Released as a large-scale, openly available dataset for research; exact license specified on the HF/Zenodo record. [2026.msrconf](https://2026.msrconf.org/track/msr-2026-mining-challenge)

**Signals**

- Focuses on agent-authored pull requests from real GitHub repositories. [2026.msrconf](https://2026.msrconf.org/track/msr-2026-mining-challenge)
- Includes metadata about PRs, their timelines, and labels about agent involvement. [2026.msrconf](https://2026.msrconf.org/track/msr-2026-mining-challenge)
- Likely derived from GitHub events + PR metadata, with annotations for “agentic” activity. [2026.msrconf](https://2026.msrconf.org/track/msr-2026-mining-challenge)

**Time span / size**

- Described as “large-scale” with many PRs; details in the preprint (not fully visible in the snippet). [2026.msrconf](https://2026.msrconf.org/track/msr-2026-mining-challenge)

**Usefulness**

- More specialized than GH Archive/GHTorrent, but includes rich PR-level interactions and possibly fine-grained labels (e.g., whether an agent’s PR was accepted, how long reviews took). [2026.msrconf](https://2026.msrconf.org/track/msr-2026-mining-challenge)
- You could build next-action and stall models specifically for AI teammate workflows.

**Fit score**

- **3/5** – Niche and PR-specific; interesting if you care about AI-collab dynamics, but for a general harness GH Archive/GHTorrent + Jiras are stronger. [2026.msrconf](https://2026.msrconf.org/track/msr-2026-mining-challenge)

***

## Hugging Face Datasets

There isn’t an off-the-shelf HF corpus that combines GitHub, Jira, email, and calendar in one aligned timeline; HF is mostly focused on text, code, and some structured corpora. However: [lakefs](https://lakefs.io/blog/hugging-face/)

- You can get Enron emails via HF (`corbt/enron-emails`), which is just a convenient distribution of the Enron corpus. [wacclearinghouse](https://wacclearinghouse.org/jwa/corpora/enron/)
- Some software engineering datasets exist on HF, but they tend to be source-code or commit message corpora without full event timelines or actor-level attribution across multiple tools. [livablesoftware](https://livablesoftware.com/huggingface-hub-empirical-studies-ml/)

**Fit score**

- **2/5** – Useful as packaging for specific corpora (Enron), but not as a ready-made multi-modal work-activity harness. [livablesoftware](https://livablesoftware.com/huggingface-hub-empirical-studies-ml/)

***

## Public time-tracking / ActivityWatch style datasets

Public datasets that look like “ActivityWatch exports” with real user activity logs are rare, mainly due to privacy. Documentation focuses on *how you can export your own data*, but not on public corpora. [docs.activitywatch](https://docs.activitywatch.net/en/latest/features/exporting-data.html)

- ActivityWatch docs explain exporting per-bucket events (window focus, app usage, etc.) as JSON via the local UI or REST API. [wiki.openhumans](https://wiki.openhumans.org/wiki/ActivityWatch)
- The Personal Science Wiki describes exporting your own ActivityWatch data but doesn’t link to public, anonymized multi-user corpora. [wiki.openhumans](https://wiki.openhumans.org/wiki/ActivityWatch)

**Fit score**

- **1/5** – Good format for collecting your own operator data for *online* or semi-offline evaluation, but no substantial public multi-person dataset appears available. [docs.activitywatch](https://docs.activitywatch.net/en/latest/features/exporting-data.html)

***

## Summary table (most relevant candidates)

| Dataset                                 | Venue            | Modalities                       | Actor attribution | Time span / scale                               | Ranker eval? | Stall/dropped-ball proxy? | Fit (1–5) |
|-----------------------------------------|------------------|----------------------------------|-------------------|--------------------------------------------------|-------------|----------------------------|-----------|
| GH Archive / GitHubArchive             | GHArchive, BigQuery, Kaggle | GitHub events (issues, PRs, commits, comments, reviews) | Yes (actor.login)  [gharchive](https://www.gharchive.org) | 2011–present, 5B+ events since 2015  [gharchive](https://www.gharchive.org) | Yes        | Yes, via idle open issues/PRs & reviewer SLAs | 4         |
| GHTorrent                               | Gousios project  | GitHub events + API objects      | Yes  [cs.uwaterloo](https://cs.uwaterloo.ca/~m2nagapp/courses/CS846/1171/papers/gousios_msr12.pdf)      | Multi-year mirror, millions of repos  [cs.uwaterloo](https://cs.uwaterloo.ca/~m2nagapp/courses/CS846/1171/papers/gousios_msr12.pdf) | Yes        | Yes, using statuses, assignees, reviews      | 4         |
| Apache Jira Issue Tracking (Zenodo)     | Zenodo           | Jira issues + comments           | Yes (reporter, assignee, commenters)  [zenodo](https://zenodo.org/records/14253918) | Multi-project Apache Jira instance  [zenodo](https://zenodo.org/records/14253918) | Yes        | Yes, via status/assignee + inactivity       | 4         |
| Multi-Jira dataset (16 instances)       | Dataset from ACM paper | Jira issues (2.7M issues, 32M changes)  [dl.acm](https://dl.acm.org/doi/10.1145/3524842.3528486) | Yes              | 1822 projects, 2.7M issues  [dl.acm](https://dl.acm.org/doi/10.1145/3524842.3528486)             | Yes        | Yes, via change history                    | 4         |
| Eclipse Bugzilla / Eclipse issue dataset| Zenodo + paper   | Bugzilla bugs + comments         | Yes  [pmc.ncbi.nlm.nih](https://pmc.ncbi.nlm.nih.gov/articles/PMC12545829/) | 301,378 bug reports up to Nov 2024  [pmc.ncbi.nlm.nih](https://pmc.ncbi.nlm.nih.gov/articles/PMC12545829/)     | Yes        | Yes, via bug status and idle periods        | 3.5       |
| Enron Email (incl. Enron-Meetings variants) | HF / CMU / WAC | Email threads                    | Yes (sender/recipients)  [cs.cornell](https://www.cs.cornell.edu/~arb/data/email-Enron/) | ~500k emails, 150 employees, 1998–2002  [wacclearinghouse](https://wacclearinghouse.org/jwa/corpora/enron/) | Yes        | Partial, via unanswered/late replies       | 3.5       |
| Jira Social Repository                  | GitHub           | Jira issues + social graph       | Yes  [github](https://github.com/marcoortu/jira-social-repository)      | Multiple ecosystems (Apache, Spring, etc.)  [github](https://github.com/marcoortu/jira-social-repository) | Yes        | Yes, similar to other Jira datasets        | 3.5       |
| MSR AIDev (agent PRs)                  | HF / Zenodo      | PRs with agent annotations       | Yes  [2026.msrconf](https://2026.msrconf.org/track/msr-2026-mining-challenge)      | Large-scale agent-authored PRs  [2026.msrconf](https://2026.msrconf.org/track/msr-2026-mining-challenge)          | Yes, PR-specific | Limited, PR lifecycle only                  | 3         |
| Kaggle GH Archive slices                | Kaggle           | GitHub events                    | Yes  [kaggle](https://www.kaggle.com/datasets/programmerrdai/gh-archive-github-public-timeline-data)      | Same as GH Archive re-packaged  [kaggle](https://www.kaggle.com/datasets/programmerrdai/gh-archive-github-public-timeline-data)         | Yes        | Yes, similar to GH Archive                 | 3.5       |
| ActivityWatch-style public data         | –                | Time-tracking                    | –                 | None widely public  [docs.activitywatch](https://docs.activitywatch.net/en/latest/features/exporting-data.html)             | No         | No                             | 1         |

***

## Can any of these serve as a “genuinely usable” offline harness?

If you define “genuinely usable” as:

- Enough scale to stress-test rankers.  
- Dense, timestamped event streams with actor attribution.  
- Ability to reconstruct tasks and state transitions to define “stalled” proxies.  

Then **yes**, you can get a *usable* harness by combining:

1. **GitHub events (GH Archive or GHTorrent) for code/PR/issue workflows.** [firebolt](https://www.firebolt.io/blog/analyzing-the-github-events-dataset-using-firebolt-querying-with-streamlit)
   - Build a per-user, per-repo timeline of tasks: open issues, open PRs, requested reviews.  
   - Derive labels for “what they actually touched next” from subsequent events, giving you ranking targets.  
   - Derive “stalled” labels from long no-activity windows on assigned/awaiting-review items.

2. **Jira/Bugzilla datasets for issue-tracker workflows.**  
   - Multi-Jira dataset (2.7M issues, 32M changes) and Apache Jira dataset give excellent coverage for ticket workflows with status and assignee histories. [zenodo](https://zenodo.org/records/14253918)
   - Eclipse Bugzilla dataset adds another ecosystem with precise bug lifecycle data. [zenodo](https://zenodo.org/records/15348468)
   - These can be used to evaluate ranking strategies over “which ticket do we work on next” and to detect tickets that sat idle in “Assigned/In Progress” states.

3. **Enron email corpora for communication-based heuristics.**  
   - Use threads as tasks and replies as actions to test ranking over “which thread/email to answer next” and detection of “never answered / extremely delayed” requests as dropped balls. [cs.cornell](https://www.cs.cornell.edu/~arb/data/email-Enron/)

What you **cannot** get from public datasets today:

- A single, cohesive, *multi-tool* corpus where the same tasks appear in GitHub, Jira, email, calendar, and chat with clean cross-links and labeled “dropped ball” ground truth.  
- Real calendar data or internal chat logs at scale, for obvious privacy reasons; public corpora like Enron don’t include calendar invites as structured events, only email text referring to meetings. [wacclearinghouse](https://wacclearinghouse.org/jwa/corpora/enron/)
- Time-tracking / personal activity logs across multiple users with open licensing; ActivityWatch docs are about self-export, not shared corpora. [docs.activitywatch](https://docs.activitywatch.net/en/latest/features/exporting-data.html)

So, for *your* specific research goal:

- **Cross-source next-action ranker.**  
  - You can approximate “cross-source” by *combining multiple datasets* (e.g., GitHub + Jira + Enron) and training a model that treats different event streams as separate views of “work,” but you won’t have them aligned for the *same* users/tasks across systems.  
  - You will, however, be able to:  
    - Test how well a ranker chooses the next issue/PR/email thread to work on given realistic candidate sets and histories.  
    - Evaluate generalization across domains (code issues vs tickets vs email).

- **Dropped-ball / stalled-delegation detection.**  
  - You can construct proxy labels reliably in Jira/Bugzilla and GitHub contexts from statuses, assignment, and idle periods.  
  - You can construct weaker proxies in Enron: unanswered requests, very delayed replies, etc.  

Given your bar and the explicit exclusions:

- The **best candidates** overall are:  
  - GH Archive or GHTorrent for GitHub. [gharchive](https://www.gharchive.org)
  - The **multi-Jira dataset** (2.7M issues, 32M changes) plus the **Apache Jira dataset** on Zenodo. [dl.acm](https://dl.acm.org/doi/10.1145/3524842.3528486)
  - Enron email (optionally Enron-Meetings) as an additional communication modality. [cs.cornell](https://www.cs.cornell.edu/~arb/data/email-Enron/)

- None of these are survey/aggregate; they’re all raw event/timeline data with actor attribution and timestamps.  

**Honest verdict:**  

- If you want a *single*, multi-modal dataset with rich cross-tool linkages and explicit “dropped ball” labels, you will need to **instrument and log your own system** or synthesize one; nothing public matches that spec. [gharchive](https://www.gharchive.org)
- If you are willing to:  
  - Use *separate* datasets for different modalities,  
  - Derive proxy labels (e.g., idle intervals, no reply), and  
  - Accept that “ground truth” will be heuristic rather than user-confirmed,  
  then GH Archive/GHTorrent + Jira/Bugzilla + Enron give you a **perfectly viable offline evaluation harness** for both next-action ranking and stalled/delegation detection at realistic scale. [gharchive](https://www.gharchive.org)

***

## Secondary question: offline dataset for both mechanisms

From an evaluation-design perspective:

- You can think of each dataset as a separate “environment”:  
  - GitHub environment (GH Archive / GHTorrent) for engineering artifact work.  
  - Jira/Bugzilla environment for ticket workflows.  
  - Enron for communication workflows.  

- For each environment, you can define:

  - **State**:  
    - All open items/tasks at time t (issues, PRs, bugs, email threads) plus local history (recent events).  
  - **Action candidates**:  
    - Interactions the user *could* take next (comment on issue X, commit to PR Y, reply to thread Z).  
  - **Chosen action** (for training / evaluation):  
    - The event that actually happens next in the logs for that user and time window.  

- You can then implement an *offline evaluation harness* where:

  - A candidate ranker is given a historical snapshot and must rank candidate tasks.  
  - You test how high the actual next action ranks (e.g., MRR, NDCG) on held-out slices.  
  - For dropped-ball detection, you can frame it as scoring each task with a “risk of going stale” and compare against your proxy labels derived from idle intervals.

That gives you a robust, realistic stress-test without needing a monolithic cross-tool corpus.

To tune this to your needs: would you rather prioritize (a) code/issue workflows (GitHub + Jira/Bugzilla) or (b) communication workflows (email) first?  