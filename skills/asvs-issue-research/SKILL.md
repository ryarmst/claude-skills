---
name: asvs-issue-research
description: >
  Researches the GitHub issue and PR history behind a specific OWASP ASVS requirement
  (e.g. "1.2.4", "6.3.1") and produces a teaching-ready briefing: the current text of
  the requirement, the technical considerations that underpin it, recency-weighted
  consensus from past discussion, suggested test cases, and teaching-material angles.
  Use this skill whenever the user asks about an ASVS requirement — its meaning,
  history, debates, rationale, edge cases, how to test it, or how to teach it. Triggers
  on phrases like "explain ASVS X.Y.Z", "what's the rationale for", "research this
  requirement", "what's been discussed about", "how do I test", "prepare a teaching
  brief on", "what changed about", or any mention of an ASVS requirement ID in a
  context where the user is preparing video, training, or teaching material. Always
  use this skill before explaining any ASVS requirement in any teaching context — the
  current text plus the issue history together are the authoritative source.
---

# ASVS Issue Research & Teaching-Brief Skill

Produces a teaching-ready briefing for a single OWASP ASVS requirement by combining:
1. The **current text** of the requirement (from the local repo zip or master branch)
2. **All GitHub issues and PRs** that discuss it (via the GitHub REST API)
3. **Recency-weighted synthesis** of community consensus
4. **Suggested test cases** and **teaching-material angles**

## Environment

- **Platform**: Claude Code (bash + Python available, GitHub API reachable)
- **Rate limit**: 10 search requests/min unauthenticated. The fetch script handles this.
- **HTML pages are useless** — GitHub renders issue content via JS. Always use the API.

## Workflow

The full workflow has four stages. Do not skip stages — the value of the brief comes
from grounding synthesis in current text rather than letting old debates drive the
narrative.

### Stage 1 — Establish the present-day requirement text

Before fetching any issues, identify the current text of the requirement so the rest
of the analysis is anchored to what the requirement *actually says today*, not what
people argued it should say years ago.

In order of preference:

1. **Use the bundled helper script** which fetches the requirement directly from the
   master branch:
   ```bash
   python3 ~/skills/asvs-issue-research/scripts/fetch_requirement_text.py 1.2.4
   ```
   It returns JSON with `text`, `level`, `chapter`, `section`, and `source_url`.

2. **If the user has uploaded an ASVS repo zip** (look in `/mnt/user-data/uploads/`):
   extract the requirement chapter file and grep for the ID. Files live in
   `5.0/en/0xNN-V<chapter>-*.md` and requirements are formatted as
   `| **X.Y.Z** | Verify that... | <level> |`. Prefer this if the user has indicated
   they're working from a specific snapshot.

3. **As a manual fallback**, fetch the chapter file via web_fetch using the URL
   pattern `https://raw.githubusercontent.com/OWASP/ASVS/master/5.0/en/...`

Capture and present:
- The **verbatim current text** of the requirement
- Its **level** (1, 2, or 3)
- The **chapter and section it lives in**

If the requirement ID is not found, it may have been renumbered or removed in a
recent revision. In that case, search the issue history first to find any rename
references, then look up the new ID.

### Stage 2 — Fetch the issue history

Run the fetch script:

```bash
python3 /path/to/asvs-issue-research/scripts/fetch_issues.py <requirement_id>
```

Examples:
```bash
python3 ~/skills/asvs-issue-research/scripts/fetch_issues.py 1.2.4
python3 ~/skills/asvs-issue-research/scripts/fetch_issues.py 6.3.1 V6.3.1
python3 ~/skills/asvs-issue-research/scripts/fetch_issues.py --issue 1182
```

The script searches for the current ID, the `V`-prefixed variant, and an optional
old-version ID, then deduplicates and fetches full body + all comments for each
issue/PR. Output is JSON to stdout, summary table to stderr.

**Each result is tagged with `recency_bucket`** (`high`, `medium`, `low`, `archival`)
matching the weighting table in Stage 3. Use this tag when you sort and group issues
in the final brief — don't recompute it.

### Stage 3 — Apply recency weighting when synthesizing

**This is the most important interpretive rule of the skill.** ASVS requirements
evolve. Old issues capture historical thinking but may have been superseded.
Apply this weighting when forming conclusions:

| Issue activity (updated_at) | Weight | Treat as |
|---|---|---|
| Within the last 6 months | **High** | Current consensus / live debate |
| 6–18 months old | **Medium** | Likely still relevant, but verify against current text |
| 18 months – 3 years | **Low** | Historical context; cite only if it explains the *origin* of current wording |
| Older than 3 years | **Archival** | Mention only if directly traceable to current text or if no newer discussion exists |

**Practical application:**

- If a 4-year-old issue argued for wording X and the requirement now says X, that's
  *strong* signal — old debate, settled outcome. Cite as origin.
- If a 4-year-old issue argued for wording X and the requirement now says Y, that
  debate was *rejected*. Note it briefly but don't lead with it.
- If a 3-month-old issue is still open and contests current wording, that's the
  *live frontier*. Lead with it.
- When recent and old discussion conflict, **the recent view wins** unless the
  recent view is from a single commenter and the older view was a working-group
  consensus.

**When ranking what to discuss first**, sort by `updated_at` descending — but also
flag closed-and-resolved issues separately from open issues, because a closed issue
with recent activity often reflects a *just-decided* outcome.

### Stage 4 — Produce the teaching brief

Output the brief in the structure below. Keep individual issue summaries terse;
spend the depth in the synthesis and teaching-material sections.

```
# ASVS <X.Y.Z> — Teaching Brief

## Current Requirement (as of <today's date>)

**Chapter**: V<N> <Chapter title>
**Section**: <X.Y> <Section title>
**Level**: L<1|2|3>

> <verbatim requirement text>

## Technical Considerations Underpinning the Requirement

<2–4 paragraphs explaining what threat model this requirement addresses, what
attack(s) it prevents, what makes it technically nuanced, and what the most
common implementation mistakes are. This section should be authoritative and
reflect *current* consensus — informed by Stage 3's recency weighting, not a
literal recap of every issue. Cite specific issues only when they materially
shaped the present wording.>

## Issue & PR History (recency-weighted)

### Recent / live discussion (last 18 months)
<For each: #num — title — state — 1-sentence summary — link>

### Historical / origin-of-wording (older, but still informative)
<For each: #num — title — 1-sentence why-it-still-matters — link>

### Superseded / rejected proposals
<Brief mention — these inform what the requirement deliberately does NOT say>

## Suggested Test Cases

<3–6 concrete test cases an assessor could run to verify the requirement is met.
Each should specify: (1) what to attempt, (2) what a passing implementation looks
like, (3) what a failing implementation looks like. Pull from issue discussion
where reviewers raised specific attack scenarios; supplement with standard
practitioner knowledge where issues didn't cover an obvious case.>

## Teaching Material Angles

<3–5 angles for explaining this requirement on video. Each angle should give:
- A hook (why a developer/security person should care)
- The minimum mental model needed to understand it
- A concrete worst-case example or war-story prompt
- One common misconception to debunk explicitly

Where the issue history surfaced a recurring confusion (e.g., "developers often
think X means Y but it actually means Z"), feature that prominently — these are
gold for teaching content.>

## Open Questions / Caveats for Presenter

<Anything still genuinely unresolved that a teacher should flag honestly rather
than paper over: open issues, internal contradictions with related requirements,
known edge cases the standard doesn't cover. Better to acknowledge in a video
than to be corrected in comments.>

## Cross-References

<Other ASVS requirements explicitly related (often surfaced in issues as
"see also X.Y.Z" or "merged from"). Useful for showing the requirement in
context.>
```

## Interpretation Heuristics

**Reading [MODIFIED], [MOVED FROM], [MERGED FROM] tags in issue text.** ASVS
maintainers track requirement evolution with bracketed tags. When you see e.g.
`[MODIFIED, MOVED FROM 5.1.3, SPLIT FROM 5.1.4, MERGED FROM 11.1.5]`, the
current requirement was assembled from multiple older requirements. Search any
referenced old IDs to capture full context.

**Distinguish issue authors.** A handful of names recur as ASVS working group
members (e.g. `tghosth`, `jmanico`, `elarlang`, `randomstuff`). Their proposals
in closed/merged issues are usually authoritative — they own the standard.
Single-commenter outside proposals carry less weight unless the working group
engaged with them substantively.

**Watch for "Discussion #NNNN" links.** ASVS uses GitHub Discussions for some
proposal threads. The fetch script does not search Discussions (different API
endpoint). If issue comments reference a Discussion number, mention it as a
follow-up the user may want to read manually.

**Comments with code snippets or attack examples** are the highest-value
material for the test-case and teaching-angles sections. Surface them.

## Single-Issue Mode

If the user just wants deep analysis of one specific issue:

```bash
python3 ~/skills/asvs-issue-research/scripts/fetch_issues.py --issue <number>
```

In this case, skip Stage 3's cross-comparison and produce a focused single-issue
deep-dive: what was proposed, who argued what, what was the resolution,
implications for current text.

## Label Reference (ASVS-specific)

| Label | Meaning |
|---|---|
| `1) Discussion ongoing` | Open, no clear proposal yet |
| `2) Awaiting response` | Waiting on original poster |
| `3) Awaiting proposal` | Discussion converging, needs write-up |
| `4) Proposal for review` | Clear change proposed, needs approval |
| `5) PR raised` | Pull request exists |
| `6) PR awaiting review` | PR open, needs reviewer |
| `_5.0 - prep` | Was flagged as blocking 5.0 release |
| `_5.0 - Not blocker` | Nice to have for 5.0 |
| `V<N> (prev V<M>)` | Chapter assignment, with old chapter for traceability |

Closed issues with `5) PR raised` or `6) PR awaiting review` labels are the most
important historical evidence — they tell you what change actually shipped into
the current requirement text.
