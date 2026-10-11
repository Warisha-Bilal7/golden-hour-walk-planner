# DEV challenge submission checklist (M5 #32)

`ghwalk` is entering a **DEV Challenge**, where you enter by publishing a DEV
post. Everything below the generic rules comes from the DevRelay knowledge base
guide *"DEV Challenges: How to Participate"* (verified 2026-09-30, sourced from
`dev.to/challenges`, the Official Rules at
`https://dev.to/page/official-hackathon-rules`, and individual challenge pages).

> The **open** challenge's prompt, required tag, submission template, key dates,
> and judging criteria are *live data*. Pull them from the challenge page or
> `get_challenge_details` (`full_details`) and fill the `TODO` rows before
> publishing. Do not guess a tag or a deadline.

## 1. Eligibility (Official Rules)

- [ ] I am **18+** (or the age of majority where I live) and can form a
      binding contract.
- [ ] I am a **DEV Member** with an active account in good standing, with email
      and internet access throughout the entry period.
- [ ] I am **not** in an excluded jurisdiction (the Official Rules list
      Afghanistan, Belarus, Central African Republic, Cuba, and others).
- [ ] Entering does not violate my **employer's** policies.

## 2. New work and provenance

- [ ] The project was **started during, and not before, the entry period**
      (check the challenge's window; some themes point at existing work).
- [ ] Any commits made after the deadline are **noted in the README**.
- [ ] Non-trivial use of prior/open-source code is **credited** in the post
      (we credit `astral`, `osmnx`, `networkx`, `jinja2`, `langgraph`,
      Open-Meteo, Ollama).
- [ ] No plagiarism: incidental → disqualification, egregious → DEV suspension.

## 3. Repository readiness

- [ ] `LICENSE` present (MIT) — licensing is not required but recommended
      (MIT / Apache-2.0 / BSD-2 / BSD-3).
- [ ] `README.md` complete: what it is, install, run, outputs, model table,
      tests, project layout, license.
- [ ] Public GitHub repo: `https://github.com/Warisha-Bilal7/golden-hour-walk-planner`.
- [ ] Testable for judges: CLI app, no login/credentials needed; the run
      command and expected outputs are in the README. Model comparison and
      field-test logs live under `docs/` and `eval/`.

## 4. Submission post

- [ ] Written in **English** (non-English is completion-badge only, not
      prize-eligible).
- [ ] Published using the challenge's **submission template** (from its page).
- [ ] Carries the **required challenge tag** (e.g. `#weekendchallenge`,
      `#frontendchallenge`, `#sanitychallenge`). → `TODO: required tag = ____`.
- [ ] Shows the work: overview of what was built, why, and a demo/embed
      (`{% embed <url> %}` for a GitHub repo or hosted page; `docs/post.md`).
- [ ] **AI disclosure** set accurately via `ai_disclosure_level` (DevRelay
      defaults to `some_ai`, the honest level for an agent-assisted entry).
- [ ] Teammates' DEV handles listed, if any, so the whole team gets a badge
      (teams up to four; one submission per team). → `TODO: handles = ____`.
- [ ] Special requirements met (test credentials if login-gated, sponsor
      project/product ID if a track requires one) — *missing requirements may be
      judged incomplete*.

## 5. Judging criteria (fill from the challenge page)

Judging criteria are listed **per prompt** on the challenge page. Known
examples: CSS Art → Creativity, Effective Use of CSS, Aesthetic Outcome;
landing page → Accessibility, UX, Creativity, Code quality; Weekend Challenge →
Theme relevance, Creativity, Technical Execution, Writing Quality, optional
Prize-Category tech.

| Criterion | How ghwalk addresses it |
|---|---|
| `TODO: criterion` | `TODO: evidence from ghwalk` |
| ... | ... |

## 6. Publish before the deadline

- [ ] Deadline converted to my timezone (challenge pages give UTC or PDT; the
      sponsor's clock is official). → `TODO: deadline (UTC) = ____`.
- [ ] Post published before the deadline (draft exists: `docs/post.md`).
- [ ] After publishing: confirm the badge appears; the DEV team contacts winners
      by the account email.

## References

- DevRelay knowledge base, *"DEV Challenges: How to Participate"* (verified
  2026-09-30): `https://devrelay.com/knowledge/dev-challenges`.
- Official Rules: `https://dev.to/page/official-hackathon-rules`.
- Challenge index: `https://dev.to/challenges`.
