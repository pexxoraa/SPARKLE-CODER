# Validation report — SPARKLE CODER 0.7.0

Validated locally on Linux and through native GitHub runners on 2026-09-25. No real NVIDIA key or payment was used.

## Cloudflare deployment handling repair — 2026-09-25

The owner's latest terminal output confirms the initial remote migration
completed, followed by a failed `wrangler deploy`. The previous setup captured
stdout/stderr and discarded them on failure, so the actual Cloudflare cause
was not visible. It also removed stdout's TTY, which makes Wrangler decline
interactive first-account subdomain registration. That is a possible cause,
not a confirmed diagnosis of the owner's deployment.

Deployment now inherits the terminal and uses Wrangler's documented
`WRANGLER_OUTPUT_FILE_PATH` ND-JSON output for its address. Setup requires a
successful version and matching Worker URL before asking for the NVIDIA key.
Failed captured commands show their diagnostics; echoed secret-input values
are redacted. Existing database IDs and owner credentials are preserved.

- **195 Python tests passed**, including 15 owner-setup tests. New cases cover
  deployment failure before key entry, stdout/stderr from a real child process,
  secret-input redaction, cancelled deployment, and wrong/stale URL rejection.
- The actual pinned **Wrangler 4.138.0 `deploy --dry-run` passed** with the Worker,
  static assets and bindings. This does not perform a remote deployment.
- A real terminal subprocess confirmed both stdin and stdout remain TTYs and
  successfully accepted an interactive prompt through the repaired wrapper.
- The owner subsequently supplied a live URL. Browser inspection confirmed the
  workspace and account-request form load and `/admin` shows its password form.
  Creating a scratch file, saving it and reopening its contents after a reload
  passed. The browser's download wait timed out, so download remains unverified.
  Direct `/api/info` navigation was blocked by the browser client; payment
  configuration could not be confirmed. No admin password, payment approval or
  live NVIDIA inference was exercised.

## Cloudflare migration repair — 2026-09-25

The owner reported `incomplete input: SQLITE_ERROR [code: 7500]` from remote
`d1 migrations apply`. The earlier SQLite tests did not exercise D1's remote
statement parser. The migration now avoids nested `CASE ... END` in triggers,
uses single-line uppercase trigger bodies, and enforces LF SQL line endings.
Setup reuses the saved database, checks migration history before deploying,
and can retry the initial schema through Wrangler file import only after
confirming that there are no application objects or applied migrations.

- **190 Python tests passed**, including 10 owner-setup tests: normalized ZIP
  line endings, invalid SQL before cloud writes, same-database recovery,
  preserved data and owner credentials, refusal to import over existing data
  or migration history, failure/cancellation handling, and secrets via stdin.
- **15 gateway tests passed**, adding direct database regressions for suspended
  payment rollback and over-reservation settlement rollback. Successful credit,
  hold and usage transitions still execute atomically.
- The recovery orchestration tests simulate the Cloudflare CLI responses and
  use local SQLite for import effects. They do not prove remote D1 execution.
- `python scripts/setup_cloud.py --check` passes without cloud authentication.
- **The actual Wrangler/local-D1 migration test passed**: normal migration,
  repeat migration with a retained account, SQL-file import with its completion
  record, and matching table/index/trigger inventories. This test is now a CI
  gate and still does not exercise the remote D1 parser or a live import.

Remote retry remains with the owner's authenticated Cloudflare terminal. No
remote deployment or resolution on the owner's actual database is claimed.

## Automated results

- **180 Python tests passed**, including the previous storage, permissions,
  cancellation, repair and packaged-runtime regressions.
- **13 gateway tests passed** using the real SQL migration, SQLite transactions,
  Web Crypto and the actual Worker request handler with a mocked NVIDIA upstream.
- **Four JavaScript test scripts passed** for browser transport, hosted pairing,
  explanations and project recovery. Application and admin scripts parse.
- A desktop-to-gateway integration test starts a local HTTP server running the
  Worker handler and database. The desktop enrolls, submits a payment reference,
  the admin approves it, the desktop makes an inference call, provider-reported
  usage is debited, and reopening the app retains the account and balance.
- Structural site verification catches a broken linked stylesheet, rechecks after
  repair, and explicitly disclaims browser/JavaScript verification. No shell
  permission is bypassed.
- Retry tests verify a stable request ID for ambiguous transport retries and
  no blind repeat of ambiguous paid requests to a direct provider.

Gateway checks cover exact ₹15 / 1,000,000-token packs, duplicate approval and
UTR rejection, insufficient balances, concurrent reservations, account isolation,
manual device recovery/revocation, admin sessions and same-origin enforcement,
provider-secret redaction, immutable ledger records, response encryption/expiry,
stale request holds, and usage reconciliation. Tests do not establish D1's deployed
latency, Workers CPU consumption, NVIDIA rate limits, or 50-user throughput.

## Efficiency evidence

A synthetic completed write plus diff containing 1,448 repeated CSS lines shrank
from **72,707 to 2,466 serialized characters (96.6%)** in the model-request copy.
The original history was unchanged and tool-call/result IDs stayed paired. This
is a fixture measurement, not the user's original flower-shop run or a model
billing benchmark. Default output is now 4,096 tokens, context target 24,000
characters, and Nemotron reasoning is disabled in Fast mode.

## Executable and deployment limits

The Linux PyInstaller executable was rebuilt for 0.7.0 and passed the actual
executable smoke test with a provided project Python interpreter: startup,
PROJECTS persistence, paired API access, approval, real repair/checks, downloads,
revocation and clean shutdown. This is separate from the new bundled-Python gate.
Portable Python downloads timed out in the local workspace. Native GitHub
runners downloaded and verified the actual bundled runtime successfully on
**Windows, macOS and Linux**. Windows additionally built the Setup EXE, installed
it, ran the installed app's smoke check, reinstalled over existing sample user
data and uninstalled while preserving PROJECTS and APP_DATA.

[Verified build run](https://github.com/pexxoraa/SPARKLE-CODER/actions/runs/36090341200)
for code commit `ee355cbed40dcea79dfb8b66ecdc6f892fe7f6e4` passed all verification
and build jobs. The release job was skipped because this was a branch build.
Artifacts are **personal edition** because SPARKLE_PILOT_URL is not configured;
they are not the connected tester distribution. Configure the server origin and
run the installer workflow with its tester option before distributing.

The first Windows run caught a short-path/long-path mismatch in the smoke-test
assertion. The fixed assertion resolves the actual interpreter path, confirms
that it is inside the copied runtime, and cleans up the disposable app process.
The rerun passed. The Worker also passed a Wrangler deploy dry run (bundle and
bindings validated; this did not deploy a live service).

The minimalist app and admin UI have script/static checks, not a verified browser
visual pass. This environment's cloud browser cannot connect to the local app.
Cloudflare dashboard navigation remained on its security-verification page after
one reload. No live Cloudflare deployment, live admin URL, provider credential,
real UPI confirmation, real-model cost/speed result or 30–50-user load result is
claimed. The owner setup script and tester-build configuration are supplied in
[PILOT_SETUP.md](PILOT_SETUP.md).

Before rollout: deploy with the owner's settings, verify one actual payment,
build the configured tester installer, run a flower-shop task, inspect desktop
and mobile output and record provider usage, calls and elapsed time.
