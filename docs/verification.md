# Verification status and workflow

No passing execution results are claimed by this document. Adding tests does not mean they pass. The committed dependency conflict and runtime defects may cause this workflow to fail; failures are useful evidence and must not be suppressed.

## Run in GitHub

Open the repository Actions tab, select Verify application, and inspect the run for your exact commit. The workflow also runs on pushes to main and pull requests. If Actions is disabled, enable it according to repository policy. Hosted-runner usage may count against your account allowance.

## Checks

- Install the actual committed requirements without silently overriding pins.
- Check installed dependency consistency and run backend tests.
- Install frontend packages and build the frontend.
- Start the actual backend and frontend.
- Use Chromium to start an incident, wait for evidence and the approval gate, approve, and assert resolved status.

Mock mode is explicit. No Gemini key is required or supplied. A passing mock run does not prove live Gemini, rejection safety, restart recovery, cancellation, duplicate-action protection, security, or production readiness. Those require additional tests.

## Evidence

Download backend-results and browser-evidence from the workflow run when available. Browser evidence includes screenshots, trace.zip, a video, request errors, JavaScript errors, result.json, and server logs. Installation failures occur before browser evidence exists; use the failed step log in that case. Do not publish logs containing secrets.

## Local browser execution

With both servers already running in mock mode, from the repository root:

```powershell
python -m pip install playwright==1.49.1
python -m playwright install chromium
python scripts/browser_smoke.py
```

Use the backend virtual environment's Python if needed. The script returns a nonzero exit status on failure. It does not repair the application.
