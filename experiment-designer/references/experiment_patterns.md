# Experiment Patterns

Use these patterns when designing experiments.

## Pattern 1: Hypothesis shape

Default structure:

- If we change `<surface or rule>`
- then `<primary metric>` will move by `<target amount>`
- because `<behavioral or product mechanism>`

## Pattern 2: Minimum experiment fields

Every experiment should name:

- control
- treatment
- primary metric
- success threshold
- kill threshold
- sample size target
- kill date
- owner
- status

## Pattern 3: Metric discipline

Prefer one primary metric plus a short set of guardrails such as:

- signup rate
- activation rate
- qualified reply rate
- unsubscribe rate
- error rate

Avoid sprawling scorecards that make every result arguable.

## Pattern 4: Test classes

Common classes:

- CRO page test
- onboarding activation test
- lifecycle email test
- pricing or packaging test
- launch distribution test
- public proof / trust test

Choose the smallest class that can answer the real question.

## Pattern 5: Confounder check

Before greenlighting a test, check:

- traffic source changed mid-run
- launch or press event overlaps the window
- product bugs affect only one variant
- attribution path is broken
- sample size target is unrealistic for the timeframe

## Pattern 6: Readout discipline

Verdicts should resolve to:

- scale
- kill
- rerun with fix
- inconclusive

Do not let "interesting" stand in for an actual decision.
