# Vercel deployment

The complete workspace is deployed at https://phishing-triage-service.vercel.app.
`vercel_app.py` mounts invoice review, Google OAuth routes, and the manual email inspector.
The Python entry point is configured in `pyproject.toml`; temporary Gradio files use `/tmp`.
`.vercelignore` excludes local secrets, Gmail tokens, and email/PDF artifacts.

## Current readiness

The interface can run without credentials. Analysis returns a clear 503 setup error
until a DeepSeek key is configured; it does not substitute simulated results.
Google sign-in remains disabled until its OAuth configuration is present.

This deployment is suitable for reviewing the design. The current Gmail OAuth state,
login sessions, and Gradio workflow state are stored in process memory. They can be
lost on function restarts or requests routed to another instance. Before relying on
live inbox workflows, move these to durable shared storage and replace or externalize
the Gradio queue/session backend. Adding Google credentials alone does not resolve this.

## Environment configuration

Add secrets through Vercel project Settings → Environment Variables (never commit them):

- `DEEPSEEK_API_KEY`: enables email inspection and DeepSeek invoice extraction.
- `INVOICE_MODEL_PROVIDER=deepseek`
- `INVOICE_MODEL=deepseek-chat`
- `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`: a Google Web application OAuth client.
- `GOOGLE_REDIRECT_URI=https://phishing-triage-service.vercel.app/auth/google/callback`

Register that exact redirect URI in Google Cloud and enable the Gmail API. During
Google testing, add the intended Gmail account as a test user. Keep `LLM_FAKE` unset
or false in production. Redeploy after updating environment variables.

## Deploy and check

```sh
vercel login
vercel link --project phishing-triage-service
vercel deploy --prod
vercel curl /healthz --deployment https://phishing-triage-service.vercel.app
```

Keep Vercel's deployment protection enabled. Verify `/invoices/`, `/inspect`, and
`/help` as well as the Google callback, actual PDF extraction, and draft export once
the shared-state work and account configuration are complete.
