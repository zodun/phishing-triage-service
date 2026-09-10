# Phishing Triage Service — production-grade LLM feature with evaluation & guardrails

An LLM feature wrapped in the engineering rigor that separates a shipped service
from a demo: a versioned eval set with a scoring rubric, input/output guardrails,
containerization, a CI/CD pipeline that gates on eval results, and structured
logging + metrics.

The feature: **`POST /v1/classify`** takes raw email text and returns a validated
JSON verdict — `label` (`phishing` / `legit` / `suspicious`), `confidence`,
`reason`, `indicators`. The model call is ~20% of the project; the other 80% is
everything around it.

> LLM provider: **DeepSeek** via its OpenAI-compatible API (`openai` SDK pointed at
> `https://api.deepseek.com`). Swappable — `app/llm.py` is the only integration point.

## Local Gmail and PDF app

The repository also includes [a local Gmail invoice workflow](local_invoice/README.md).
It finds emails with validated PDF attachments or direct PDF links, checks for
phishing indicators, and prepares editable reminders for eligible overdue invoices.
Run it locally with read-only Gmail access; it does not send email.

```sh
cd local_invoice
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-invoice.txt
.venv/bin/python invoice_app.py
```

---

## What each piece is

| Concern | Where it lives |
| --- | --- |
| Evaluation framework (accuracy, false-positive rate, injection-bypass rate, latency) | [evals/](evals/) — `dataset.jsonl`, `rubric.py`, `run_eval.py`, `thresholds.yaml` |
| Structured output enforcement | [app/schemas.py](app/schemas.py) `Classification` + [app/classifier.py](app/classifier.py) `_parse` (Pydantic validation, fallback on invalid JSON) |
| Input guardrails | [app/guardrails/input_guards.py](app/guardrails/input_guards.py) — size cap, prompt-injection detection (flag + isolate, not block) |
| Output guardrails | [app/guardrails/output_guards.py](app/guardrails/output_guards.py) — drop invented indicators, scrub secret-like strings |
| Containerization | [Dockerfile](Dockerfile) — non-root, healthcheck |
| CI/CD (GitHub Actions) | [.github/workflows/ci.yml](.github/workflows/ci.yml), [.github/workflows/deploy.yml](.github/workflows/deploy.yml) |
| Deploy to AWS | [infra/apprunner.yaml](infra/apprunner.yaml) — ECR + App Runner via GitHub OIDC |
| Logging & monitoring | [app/observability.py](app/observability.py) — structlog JSON logs, Prometheus metrics at `/metrics` |

---

## Architecture

```
                  ┌─────────────── FastAPI (app/main.py) ────────────────┐
  POST /v1/classify│  request-id middleware → latency + structured logs  │
 ────────────────▶ │                                                     │
                  │   Classifier.classify()   (app/classifier.py)        │
                  │     1. input guardrails    input_guards.check_email  │
                  │     2. wrap email as untrusted data in the prompt    │
                  │     3. model call          llm.LLMClient.generate    │──▶ DeepSeek API
                  │     4. parse + validate    Classification (Pydantic) │
                  │     5. output guardrails   output_guards.check_...    │
                  │     6. ClassifyResponse (+ guardrail trips, usage)   │
                  └─────────────────────────────────────────────────────┘
   GET /            HTML demo page
   GET /healthz     liveness
   GET /metrics     Prometheus: answer_requests_total{outcome},
                    answer_latency_seconds, guardrail_trips_total{stage,code},
                    model_tokens_total{model,kind}
```

Every response lists which guardrails fired; the same trips aggregate in
`guardrail_trips_total`.

---

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate   # needs Python 3.12+
pip install -e ".[dev]"
printf 'DEEPSEEK_API_KEY=sk-...\n' > .env

uvicorn app.main:app --reload --port 8080           # open http://localhost:8080/

curl -s localhost:8080/v1/classify -H 'content-type: application/json' \
  -d '{"text":"From: security@paypa1-support.com\nSubject: locked\n\nVerify your account at http://paypa1-secure-login.com/verify and enter your password."}' | jq
```

Offline mode: `LLM_FAKE=true` runs the whole pipeline with a canned classifier
(used by the tests; eval numbers are meaningless in this mode).

---

## Tests, types, lint

```bash
node --test tests/ui.test.cjs  # Node 22+: browser interaction regression tests
LLM_FAKE=true pytest --cov=app
mypy app evals
ruff check . && ruff format --check .
```

---

## Evaluation

```bash
python -m evals.run_eval --fail-under-thresholds
```

- **Dataset** — [evals/dataset.jsonl](evals/dataset.jsonl): labelled emails
  (phishing / legit / suspicious), including prompt-injection emails marked
  `"injection": true`.
- **Metrics** — accuracy, **false-positive rate** (legit flagged as phishing),
  **invalid-JSON rate**, **injection-bypass rate** (injection email not caught as
  phishing), p50 / p95 latency.
- **Gate** — [evals/thresholds.yaml](evals/thresholds.yaml); `run_eval` exits
  non-zero on any breach, failing the CI `eval-gate` job.
- **Report** — `reports/eval_report.md` and `.json` (CI artifact).

---

## Guardrail catalogue

| Stage  | Code                 | Trigger | Action |
| ------ | -------------------- | ------- | ------ |
| input  | `empty`              | blank email | reject (fallback verdict) |
| input  | `too_long`           | over `MAX_INPUT_CHARS` | reject (fallback verdict) |
| input  | `injection_attempt`  | email body tries to steer the classifier | flag, isolate email in prompt, continue |
| output | `invalid_json`       | model output not valid `Classification` | one retry, then safe `suspicious` fallback |
| output | `invented_indicator` | an `indicators` entry not quoted from the email | drop it |
| output | `secret_leak`        | secret-like string in the output | scrub it |

---

## Deployment

`push to main` → **CI** (lint, types, unit tests, then `eval-gate` against the
live model) → on success **Deploy** builds the image, pushes to ECR, triggers an
App Runner deployment.

Required GitHub repo config: secrets `AWS_DEPLOY_ROLE_ARN` (OIDC role),
`APPRUNNER_SERVICE_ARN`, `DEEPSEEK_API_KEY` (CI eval-gate only); variables
`AWS_REGION`, `ECR_REPOSITORY`. Store the model key in AWS Secrets Manager and
point [infra/apprunner.yaml](infra/apprunner.yaml) at its ARN.

---

## Layout

```
app/
  main.py            FastAPI app, middleware, routes
  classifier.py      classify pipeline
  llm.py             DeepSeek (OpenAI-compatible) client + test fake
  schemas.py         ClassifyRequest / Classification / ClassifyResponse
  guardrails/        input_guards.py, output_guards.py
  observability.py   structlog + Prometheus
  web/index.html     demo page
evals/               dataset.jsonl, rubric.py, run_eval.py, thresholds.yaml
tests/               guardrail, classifier, and API tests (LLM_FAKE)
infra/               apprunner.yaml
.github/workflows/   ci.yml, deploy.yml
```

## Roadmap / known cuts

- Dataset is ~12 seed emails — grow to 100–200 real samples for meaningful numbers.
- Injection detection is heuristic; pair with a dedicated classifier for production.
- `indicators`-in-email check is substring-based; normalise URLs/whitespace harder.
- Metrics are exposed but not scraped here — add a Prometheus/CloudWatch scrape
  config in the target environment.
- v2: swap the classifier for a CVE threat-intel RAG (retrieval + citations),
  reusing the same eval / guardrail / CI shell.
