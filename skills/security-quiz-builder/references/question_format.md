# Question File Format

Each question lives in its own markdown file. Use this exact structure so the bundler script can parse it.

```markdown
---
topic: <source-filename-stem>
number: <n>
difficulty: easy | medium | hard
tags: [optional, comma, separated]
---

**Question:** <full question text, one or more sentences>

- [ ] A. <distractor>
- [x] B. <correct answer>
- [ ] C. <distractor>
- [ ] D. <distractor>

**Explanation:** <1-3 sentences explaining why the correct answer is right and, when useful, why a tempting distractor is wrong. This is for the author's review and is stripped from the MS Forms bundle.>
```

## Rules

- Always exactly 4 options (A-D). Never 3, never 5. MS Forms handles other counts but consistency makes review easier.
- Mark the correct answer with `- [x]`; all others `- [ ]`. Exactly one correct answer per question (no multi-select in this skill).
- Randomize the position of the correct answer across questions in a topic. Do not always put it in B.
- Keep the question stem self-contained — a reader should not need the source file open to understand what's being asked.
- Use code blocks (`` ` `` or fenced) for code, payloads, headers, or commands.
