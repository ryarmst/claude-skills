# Question Quality Bar

The single biggest determinant of quiz quality is **distractor design**. Most AI-generated MCQs fail not on the question stem but on the wrong answers — they're either obviously wrong (giveaway), nonsensical (giveaway), or accidentally also correct (unfair). Read this file before writing your first batch of questions.

## What makes a good question

1. **Tests understanding, not trivia.** "What year was the OWASP Top 10 first published?" is bad. "Why did 'Cryptographic Failures' replace 'Sensitive Data Exposure' in the OWASP Top 10 2021?" is better — it tests whether the learner understands the conceptual shift.

2. **Stem is self-contained and unambiguous.** A competent reader should be able to predict the answer before seeing the choices. If the stem is so vague that multiple options could plausibly fit, rewrite the stem.

3. **One defensibly correct answer.** No "best of the following" hedging unless the question genuinely requires judgment, and even then make the right answer clearly more correct than the runners-up.

4. **Difficulty comes from the concept, not from trickery.** Hard questions should require deeper understanding, not careful re-reading of weasel words. Avoid "Which of the following is NOT…" unless the negation is in bold and unmissable — and even then, prefer rewriting positively.

## What makes a good distractor

A good distractor is something a learner with **partial understanding** would plausibly choose. Sources of good distractors:

- **Adjacent concepts**: For a question about CSRF, distractors drawn from XSS, SSRF, or clickjacking are tempting because they sound similar but solve different problems.
- **Common misconceptions**: "HTTPS prevents XSS" is a real thing students believe. Use it.
- **Outdated advice**: "Sanitize input by escaping single quotes" — historically common, currently insufficient. A learner who read an old blog will pick this.
- **Right answer to a different question**: "Use parameterized queries" is correct for SQLi but wrong for stored XSS. In an XSS question, it's a great distractor.
- **Partially correct answers**: A defense that helps but isn't the primary mitigation.

## Anti-patterns — do not do these

- **Joke distractors** ("D. Reboot the server and pray"). Wastes a slot.
- **"All of the above" / "None of the above"**. Lazy, and usually correct or usually wrong in predictable ways.
- **Distractors of wildly different lengths than the correct answer.** Test-takers learn to pick the longest. Keep all four options roughly the same length.
- **Grammatical tells.** If the stem ends in "an", don't have three distractors starting with consonants and the correct answer starting with a vowel.
- **Repeating stem keywords in only the correct answer.** Big giveaway.
- **Negation without emphasis.** "Which of the following is not a property of…" buried in lowercase loses half the test-takers to misreading, not lack of knowledge.
- **Trivia about tool versions, dates, author names, or RFC numbers** unless the topic is specifically about standards history.

## Difficulty calibration

- **Easy**: Definition recall or single-step identification. "What does SSRF stand for?" or "Which header enables HSTS?"
- **Medium**: Apply a concept to a short scenario. "A web app reflects the `Referer` header into the page without encoding. What is the most direct risk?"
- **Hard**: Multi-step reasoning, distinguishing between similar concepts, or recognizing a subtle bug. Show a code snippet or HTTP exchange and ask what's wrong, what an attacker would do next, or which mitigation actually addresses the root cause (vs. one that only papers over it).

For each topic, ensure the question set spans at least two difficulty levels. With 4 questions, aim for 1 easy / 2 medium / 1 hard.

## Self-check before saving a question

Before writing a question to disk, ask yourself:

1. Could a learner who skimmed the topic file get this right by pattern-matching keywords? If yes — rewrite.
2. Are all four options the same general shape and length?
3. Is the correct answer in a randomized position (not always B)?
4. Would an expert agree there is exactly one correct answer?
5. Does the explanation actually explain, or does it just restate the answer?

If any answer is "no," fix it before moving on.
