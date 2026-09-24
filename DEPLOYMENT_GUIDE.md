# Deploying SPARKLE CODER 0.6.3

The website is a browser interface for a running local SPARKLE engine. The
computer still stores PROJECTS and APP_DATA, runs commands and holds model keys.
Opening the website on a phone does not connect it to your computer.

## Publish the interface on Vercel

Import `pexxoraa/SPARKLE-CODER` into your own Vercel account. Use the repository
root, framework preset **Other**, build command **npm run build**, and output
directory **web-dist**. These settings and response headers are in `vercel.json`.
No model key or other environment secret is needed by this static website.

The build copies an explicit list: index.html, app.js, app.css, favicon.svg and
robots.txt. It does not publish project files, settings, logs or Python code.
When deploying from a local folder, use a clean checkout or the prepared static
deployment folder. Never upload a working app directory containing user data.

An authenticated Vercel CLI can publish the repository with:

```sh
vercel --prod
```

For the prepared static folder, run that command inside the extracted folder;
its configuration serves the included assets without another build.

A build passing locally is not a live deployment. Confirm Vercel reports READY
and open its returned production URL before sharing it.

## Connect the website to your computer

1. Update the local app while preserving PROJECTS and APP_DATA. Quit the old
   app, reopen it and confirm **0.6.3** in the sidebar.
2. Open **Connect website** in the local app.
3. Paste the exact HTTPS home address returned by Vercel. Select **Connect and
   open website**. If popups are blocked, use **Open connected website**.
4. If your browser asks, allow access to your local network for this website.
5. Run the offline demo and approve its syntax check. Confirm the repaired
   calculator has passing checks and can be downloaded through the website.

Only the approved website origin and its separate random token can use the
engine's API. The connection token travels in a URL fragment, which is not sent
to Vercel in HTTP requests; the interface removes it from the address bar and
keeps it in session storage. Keep the private connection link to yourself.
Re-pairing, disconnecting or restarting the engine invalidates old tokens.

Keep the engine running on the same computer as the browser. Browser policies
may block website-to-loopback requests even when the engine's HTTP checks pass.
If access is blocked, use the local interface. Do not disable browser security
features. This release does not provide an always-on server or remote access.

## Optional Sparkle Cloud gateway

The gateway backend was not included in the supplied update. Publishing the
interface does not deploy a gateway, credit service, billing system, or NVIDIA
proxy. Those capabilities have not been validated against a live backend here.
Use the direct NVIDIA or local Nemotron connection for now.

When you have a working gateway, set `SPARKLE_GATEWAY_URL` in the environment
used to launch the local app, including its `/v1` path. The engine supplies this
one value for the preset and access link. No JavaScript edit is needed. The
existing default hostname is a placeholder, not a verified service.

The optional balance call is limited to three seconds, without retries. A
missing balance does not fail an otherwise successful model-list connection.
NVIDIA and ordinary custom endpoints do not receive balance requests.

## Executables and updates

See [packaging/README.md](packaging/README.md). Distribute only clean program
files or the built executable, never your APP_DATA or PROJECTS directories.
Users updating an existing installation must keep those directories.
Packaged apps need an installed Python interpreter to run Python project code.

See [TEST_REPORT.md](TEST_REPORT.md) for current validation and unverified areas.
