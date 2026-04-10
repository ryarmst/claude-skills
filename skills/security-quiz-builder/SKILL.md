---
name: security-quiz-builder
description: Generate high-quality multiple-choice quiz questions from a folder of structured markdown files covering software security topics, then bundle the output for Microsoft Forms import. Use this skill whenever the user wants to build quizzes, tests, or assessments from security training material, application security course notes, OWASP topic files, or any folder of markdown topic files where each file represents one subject. Trigger this skill even if the user only says things like "make me a quiz from these notes," "turn this folder into questions," or "I need MCQs for my security class" — the skill handles topic ingestion, optional web-resource scraping, question generation with varied difficulty, and MS Forms-compatible export.
---

# Security Quiz Builder

Generates multiple-choice questions from a folder of markdown topic files and bundles them for Microsoft Forms import.

## Inputs

The user provides:
- **Input folder**: directory of `.md` files. Each file is one topic. Files may contain links to external web resources (RFCs, OWASP pages, blog posts, CVE writeups).
- **Output folder** (optional): defaults to `<input>/../questions/`.

## Workflow

Follow these steps in order. Do not skip the research step — question quality depends on it.

### Step 1: Inventory the input folder

List all `.md` files in the input folder. Confirm the count with the user before proceeding if there are more than ~15 files (large jobs are worth confirming scope).

### Step 2: For each topic file, research and generate questions

Process files **one at a time**, not in a single mega-prompt. For each file:

1. **Read the topic file** in full.
2. **Extract URLs** from the markdown (links, bare URLs, reference-style links).
3. **Spawn a research subagent** (via the Task tool if available) with this instruction:
   > "Read the attached markdown topic file and fetch each of the following URLs: [list]. Produce a dense technical summary covering: core concepts, common attack patterns, defenses/mitigations, real-world examples or CVEs, and any subtle/commonly-misunderstood points. Aim for ~600-1000 words. Focus on material that would make good exam questions — specifics, not platitudes."

   If subagents are not available in the current environment, do the fetching inline using `web_fetch` on each URL, then write the summary yourself. Skip URLs that fail to fetch; do not block on them.

3. **Generate 2-4 questions** based on the topic file content + research summary. Apply the quality bar in `references/question_quality.md` — read that file before writing questions for the first topic, and consult it whenever you're unsure whether a question is good enough.

4. **Vary difficulty across the question set for each topic**: at least one easier recall/definition question, at least one harder applied/scenario question, and the rest in between. If generating 4 questions, include one "tricky" question that targets a common misconception.

5. **Write the questions to disk** as `<output_folder>/<topic_filename_stem>_q1.md`, `_q2.md`, etc. — one question per file. Use the format in `references/question_format.md`.

### Step 3: Bundle for MS Forms import

Once all questions are generated, run the bundler script:

```bash
python scripts/bundle_for_forms.py <output_folder> <output_folder>/forms_import.md
```

This produces a single markdown file in the format Microsoft Forms accepts when pasted into a Word doc and imported via Copilot's "Quiz from a document" feature: each question numbered, choices labeled A-D, and the correct answer marked with an asterisk and listed in an answer key at the bottom.

Tell the user the bundled file is ready and remind them they'll need to convert it to .docx or .pdf manually before importing into Forms.

## Key principles

- **Quality over quantity**: 2 excellent questions beat 4 mediocre ones. If a topic file is thin and the linked resources don't add much, generate 2 and say so.
- **One file per question on disk**: keeps the output diff-able and lets the user delete/regenerate individual questions without rerunning the whole pipeline.
- **Research before writing**: never skip Step 2's research subagent. Questions written from the topic file alone tend to be surface-level.
- **Plausible distractors**: see `references/question_quality.md` — bad distractors are the #1 quality killer.

## Reference files

- `references/question_format.md` — exact on-disk format for individual question files
- `references/question_quality.md` — quality bar, distractor guidance, anti-patterns to avoid
- `scripts/bundle_for_forms.py` — combines per-question files into one MS Forms-ready markdown
