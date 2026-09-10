# Phishing Triage Service

Check emails for phishing indicators, review the evidence, and keep a person in
control of the next step.

This repository has two applications:

| Application | What it does | Start here |
| --- | --- | --- |
| Email classification API | Accepts email text and returns a verdict with supporting indicators. Includes a browser demo. | [Run the API](#run-the-api) |
| Local Gmail app | Finds PDF invoices, checks emails, and prepares editable payment reminders. | [Gmail app setup](local_invoice/README.md) |

The API uses DeepSeek. The Gmail app supports OpenAI, DeepSeek, and Azure OpenAI.
Both can make mistakes; their output is for review, not proof that an email is safe.

## Run the API

Requires Python 3.12 or later. From the repository root:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

Create a `.env` file with your provider key:

```dotenv
DEEPSEEK_API_KEY=your-key
```

Start the server, then open **http://localhost:8080**:

```sh
uvicorn app.main:app --reload --port 8080
```

To try the app without a provider key, start it with `LLM_FAKE=true`. This uses
canned responses for development; it does not measure real classification accuracy.

### Classify an email

```sh
curl http://localhost:8080/v1/classify \
  -H 'Content-Type: application/json' \
  -d '{"text":"Subject: Account locked. Reply with your password to restore access."}'
```

The response includes a classification with `label` (`phishing`, `legit`, or
`suspicious`), `confidence`, `reason`, and `indicators`, plus any guardrails that
fired. The service limits input size, flags instruction-injection attempts,
validates model output, drops indicators absent from the email, and scrubs
secret-like output. Invalid responses are retried before a fallback verdict.

Other endpoints: `/healthz` for liveness and `/metrics` for Prometheus metrics.

## Run the Gmail app

Requires Python 3.11 or later. It runs locally and uses read-only Gmail access.

```sh
cd local_invoice
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-invoice.txt
.venv/bin/python invoice_app.py
```

Open **http://127.0.0.1:7860** and follow the setup prompts. See the
[setup guide](local_invoice/docs/invoice-email.md) for Google OAuth and model settings.
The app does not send emails; reminders can be copied or downloaded for review.

## Development

For the API, with its virtual environment activated:

```sh
LLM_FAKE=true pytest --cov=app
mypy app evals
ruff check .
ruff format --check .
```

For the Gmail app, from `local_invoice`:

```sh
.venv/bin/python -m unittest discover -s tests -v
```

The tests use synthetic inputs and mocked providers. Local Gmail settings, tokens,
and downloaded email drafts are excluded from version control.

## Evaluation

With a provider key configured, run:

```sh
python -m evals.run_eval --fail-under-thresholds
```

The [dataset](evals/dataset.jsonl) includes labelled emails and injection attempts.
The runner measures accuracy, false positives, invalid JSON, injection bypasses,
and latency against [configured thresholds](evals/thresholds.yaml). Reports are
written to `reports/`. This is a small seed dataset, not a production benchmark.

## Deployment

The existing GitHub Actions workflow runs lint, types, and API tests. Pushes to
`main` also run live evaluations. Successful CI can trigger an AWS App Runner
deployment through ECR; the local Gmail app is excluded from that image.

Deployment requires repository secrets `AWS_DEPLOY_ROLE_ARN`,
`APPRUNNER_SERVICE_ARN`, and `DEEPSEEK_API_KEY`, plus variables `AWS_REGION` and
`ECR_REPOSITORY`. Store the runtime model key in AWS Secrets Manager and configure
its ARN in [infra/apprunner.yaml](infra/apprunner.yaml).

## Project layout

```text
app/             API, classifier, guardrails, and browser demo
evals/           Evaluation dataset, scoring, and thresholds
tests/           API and guardrail tests
local_invoice/   Local Gmail app, setup guide, and tests
infra/           AWS App Runner configuration
.github/         Test and deployment workflows
```

The API's injection checks are heuristic, and matching an indicator to email text
does not establish that the interpretation is correct. Metrics are exposed for
collection but no monitoring backend is configured here. The Gmail app's specific
limits are documented in its [README](local_invoice/README.md#privacy-and-limits).
