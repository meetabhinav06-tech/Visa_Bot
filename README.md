# Austria visa availability alerts

The deployed `Schengen live email leads` workflow checks every four hours at minute 23 UTC. It queries Parse's independent Atlys wrapper for UK residents and filters provider-reported actual earliest dates for Austria only, exactly one applicant, tourist visas, London / Manchester / Edinburgh, before 14 November 2026. Only destinations returned by the provider are covered; missing countries do not prove no appointments exist.

These are third-party leads, not confirmed appointments. Source freshness is unavailable, detailed date lists may be empty, and reported capacity must be verified on the official booking portal. No booking or payment is performed. GitHub schedules may be delayed.

## Telegram setup

1. In Telegram, open the official @BotFather, send `/newbot`, and create your bot.
2. Save its token as repository Actions secret `TELEGRAM_BOT_TOKEN`.
3. Open your new bot and press Start. Set your private numeric chat ID as Actions secret `TELEGRAM_CHAT_ID`.
4. Run `Schengen live email leads` manually. Telegram sends currently matching leads even if they were already emailed. Check your phone for receipt.

Both Telegram secrets are required. When absent, email monitoring continues and Telegram reports pending. Telegram uses plain text and tracks accepted leads individually; failed sends retry on a later run. Never commit credentials or paste tokens into issues or logs.

## Existing configuration

Repository variable `LIVE_SCHENGEN_ENABLED=true` enables the workflow; false stops it. Required email/feed secrets: `PARSE_API_KEY`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_TO`. Gmail uses an app password over encrypted SMTP. The provider costs one credit per successful request; about 180 scheduled checks in 30 days plus manual runs. Check quota before increasing frequency.

WhatsApp is optional and pending an approved dynamic template (`WHATSAPP_LIVE_CONTENT_SID`) and Twilio sender secrets. Its fixed trial reminder is never used for live leads. Telegram does not require Twilio.

State is cached per notification channel. Cache eviction, crashes between sending and saving, and ambiguous network timeouts can produce duplicates. API acceptance is not proof the user read the message. Check Actions failures. The older Austria-only connector remains disabled.

Local validation: `python -m unittest -q` (Python 3.11+, no pip dependencies).
