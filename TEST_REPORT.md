# Validation report — SPARKLE CODER 0.7.0

Validated on Linux on 2026-09-24. No real NVIDIA key or payment was used.

## Automated results

- **179 Python tests passed**, including the previous storage, permissions,
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
Downloading the portable Python runtime was blocked by network timeouts in this
workspace. The GitHub matrix is responsible for verifying the exact bundled
runtime and the Windows install/update/uninstall sequence; see its run result.

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
