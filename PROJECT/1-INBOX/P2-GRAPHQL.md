Vector vs. "GraphQLite"
Quick disambiguation — by GraphQLite I'm assuming you mean graph-style queries / graph DB (relationship traversal). If you meant GraphQL (the API layer on top of SQLite), say so and I'll re-answer — that's a different axis.

Assuming graph:

Vector (what you have)	Graph
Answers	"What is this about?"	"How is this connected?"
Strength	Fuzzy/semantic discovery; handles synonyms, typos, paraphrase. Works across sources without shared vocabulary.	Multi-hop traversal; precise and explainable; fast on known edges.
Weakness	Ranked approximations — hard to explain why result #3 ranked there. Bad at structured filters ("events last Tuesday").	Needs explicit edges. Misses implicit/semantic links. Rigid schema.
Storage cost	Big — 1024 floats × ~every document.	Small — just (src, dst) pairs.
Example query	"find mentions of OAuth failures" → hits Sleuth + GitHub + vault by meaning	"PRs that closed P1 issues in repos I touched this week"
Already in your DB	embeddings, github_embeddings	links (vault wikilinks), github_links (issue↔PR refs) — underused
They're complementary, not competing. Vector finds the entry point; graph expands from it. Most useful queries combine both: "find notes semantically about auth → follow their wikilinks → find the GitHub issues those notes reference → find the PRs that closed them." That's a 4-hop query where vector does step 1 and graph does steps 2–4.

My recommendation: unify the vector side first (the half-day refactor above). That unlocks "query everything in one shot" immediately. Then add a unified relations table — (source_type, source_id) ↔ (target_type, target_id) — that absorbs links, github_links, and any future mention-edges (Calendar event mentions a project, Sleuth reminder mentions a PR). Once both exist, your ask() in querier.py becomes: vector search → graph expand → rank.

Skip graph entirely if: your queries are "find stuff about X" (pure discovery). Skip vector if: you only ever traverse known relationships. Your project's flavor of questions ("what's going on with project Y, across everywhere?") genuinely wants both.

Want me to sketch the unified documents schema + the migration as a separate pass, after the GitHub embed finishes?