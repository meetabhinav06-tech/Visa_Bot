# Austria visa appointment alerts

Prepared for two tourist / Schengen C applicants travelling on 14 November 2026.
Targets: London, Manchester and Edinburgh. These are requested filters, not confirmation
that each centre currently serves this visa category or has appointments.

## Current status

Code and cloud workflow are supplied. Nothing is deployed. No real messages have
been sent and no real appointment availability has been checked. No permitted live
availability feed has been verified. Live monitoring is disabled by default.

Uses Python 3.11+ with no pip dependencies. Gmail SMTP for email and Twilio for
WhatsApp. Provider charges and GitHub usage limits may apply; check your accounts.

## 1. Create your private GitHub repository

1. Sign in at https://github.com/new and create a **private** repository named
   `austria-visa-alert`. Add a README when creating it so the repository has a branch.
2. Extract the supplied ZIP. Upload `bot.py`, `test_bot.py`, `sample-feed.json`,
   `.gitignore` and this README to the repository root (not inside an extra folder).
3. Create `.github/workflows/alerts.yml` using GitHub's **Add file > Create new file**.
   Copy the contents from that exact file in the ZIP. This avoids hidden folders
   being missed during browser upload. Commit it to the default branch.
4. Open **Actions > Austria visa alerts > Run workflow**, select `simulate` and run.
5. The output must say **SIMULATION ONLY**. With the current example dates before
   28 October, London and Edinburgh match; Manchester is excluded (capacity one).
   Simulation prints results only and never sends notifications. Example slots
   expire naturally as their dates pass.

## 2. Test email

For Gmail, enable 2-Step Verification and create an app password:
https://support.google.com/accounts/answer/185833
An app password may be unavailable for some accounts. Do not use your normal
Google password. The bot uses encrypted SMTP on smtp.gmail.com:465.

In the repository, open **Settings > Secrets and variables > Actions > Secrets**.
Add these repository secrets:

| Secret | Value |
|---|---|
| SMTP_USER | Your complete Gmail address |
| SMTP_PASSWORD | Gmail app password, without formatting spaces |
| EMAIL_TO | Your own recipient email address |

Run the workflow with mode `test-email`. This explicitly sends one test email.
Check your inbox and spam folder. Server acceptance is not proof of final delivery.
Keep account credentials in GitHub Secrets; do not paste them into chat or commit them.

## 3. Test WhatsApp

Configured console trial template: the test mode sends the selected template
without ContentVariables. Its appointment wording is sample text, not actual
VFS availability. A queued response means acceptance, not confirmed delivery.
When TWILIO_CONTENT_SID is set, test mode expects a no-variable template;
live mode expects a separate approved template with one variable for the alert.
Replace the trial Content SID with that production template before enabling live.

Follow https://www.twilio.com/docs/whatsapp/quickstart to create your account,
activate its WhatsApp trial/Sandbox, and join it from your own WhatsApp phone.
Use the actual sender shown in your Twilio console.

Add these GitHub repository secrets:

| Secret | Value |
|---|---|
| TWILIO_ACCOUNT_SID | Account SID beginning AC |
| TWILIO_AUTH_TOKEN | Account auth token |
| WHATSAPP_FROM | whatsapp:+ followed by the Twilio sender number |
| WHATSAPP_TO | whatsapp:+ followed by your phone's country code and number |

For the first custom-text test, send a message from your phone to the Sandbox
to open the 24-hour customer service window. Under **Actions > Variables**, add
`WHATSAPP_TEST_SESSION_OPEN` with value `true`. Leave `TWILIO_CONTENT_SID` unset.
Run mode `test-whatsapp` within that window, then check your phone and Twilio logs.
Set the variable back to `false` after testing. A queued message is not confirmed delivery.

For ongoing proactive alerts, register a production WhatsApp sender and obtain
approval for a notification template with exactly one text variable `{{1}}`.
Suggested template body: `Austria visa notification: {{1}}` (approval is not guaranteed).
Set secret `TWILIO_CONTENT_SID` to that template's HX Content SID. The bot supplies
the complete notification text as variable 1. Get the recipient's opt-in. Sandbox
pre-approved appointment templates generally use a different variable layout and
are not interchangeable with this custom template.

Official template instructions:
https://www.twilio.com/docs/whatsapp/tutorial/send-whatsapp-notification-messages-templates

## 4. Establish a permitted availability source

Official starting page: https://visa.vfsglobal.com/gbr/en/aut/

No official public slot API has been verified for this project. Ask VFS or its
authorised provider whether they offer a documented feed and permit this use.
Get permission covering the endpoint, checking frequency and capacity meaning.
Do not assume that an endpoint found in browser traffic is authorised for automation.
This project contains no VFS login automation, scraping or protection bypass.

Once obtained, an authorised feed must return the schema in sample-feed.json,
with `simulated: false` and a genuine timezone-aware `checked_at` no more than
30 minutes old. Refreshing a timestamp on stale source data is not valid.
`capacity` must mean applicants who can actually be booked together for that slot;
two unrelated single-person slots are not a two-person slot. The feed must report
GBR -> AUT, category tourist-schengen-c. Dates require ISO 8601 timezone offsets.
The adapter allows HTTPS, an optional Bearer token, no redirects, and max 1 MB.
If a permitted source uses another schema, change the adapter before enabling it.

Add secrets `FEED_URL` and optional `FEED_TOKEN`. Add repository variables:

| Variable | Value |
|---|---|
| SOURCE_PERMISSION_REFERENCE | Permission/documentation reference, without secrets |
| SOURCE_AUTHORISED | true, only after permission is established |
| LIVE_ENABLED | true, only after feed and both notification channels work |

Run `live` manually first. The schedule then runs at minutes 17 and 47 each hour
(UTC). Adjust only within the source's permitted frequency. GitHub schedules can
be delayed or dropped and are not suitable for guaranteed instant alerts. Scheduled
workflows use the default branch. While LIVE_ENABLED is unset/false, scheduled jobs skip.

Set LIVE_ENABLED=false to stop. Code also excludes appointments on/after departure.
The departure cutoff is a filter, not advice on visa processing time.

## Reliability and limits

State records successful provider acceptance separately per channel, so failed
channels can retry. State is cached across GitHub runs. Cache eviction/deletion,
a crash between sending and saving, or an ambiguous provider timeout can cause
duplicate messages. Exactly-once delivery is not guaranteed. For long-term operation,
replace the cache with a durable database. Monitor Actions failures and provider
delivery logs; a source outage does not produce a no-slots result. No availability
means no notification. The bot sends no automatic bookings or payments.

## Local commands (optional)

Install Python 3.11+ if you want to run locally. From the extracted project folder:

```
python -m unittest -v
python bot.py simulate
python bot.py test-email
python bot.py test-whatsapp
python bot.py live
```

Set credentials as environment variables first. `.env` files are not loaded by the
program. Cloud use does not require installing Python on your own computer.

GitHub references:
https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets
https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule
