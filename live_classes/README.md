# Ed3Hub Live Classes

This app implements the product rules in the Live Classes specification. It owns scheduling, registration, payment/access state, reminders, attendance, recording authorization, and the server-side Cloudflare integration.

## Cloudflare setup

1. Create a Cloudflare RealtimeKit app.
2. Create an API token with Realtime permissions. Keep it on the Django server only.
3. Create or select two presets:
   - a host preset with moderation, screen sharing, chat, recording, and participant controls;
   - a learner preset with participant viewing, chat, hand raise, and the media permissions you want learners to have.
4. Set the `CLOUDFLARE_*` variables documented in `.env.example`.

The classroom deliberately pins the browser assets to the v1 line:

- `@cloudflare/realtimekit@1.5.1`
- `@cloudflare/realtimekit-ui@1.2.0`

Cloudflare API credentials are never sent to the browser. Django creates meetings and issues participant tokens only after checking the educator owner or an ACTIVE learner registration.

Recordings are synchronized from Cloudflare when an authorized user requests the class recordings. Playback URLs are refreshed through an authenticated backend endpoint.

## Payments and reminders

Configure Paystack to send events to:

`https://<api-host>/api/live-classes/webhooks/paystack/`

The webhook is HMAC-SHA512 verified and reconciles successful payments and refunds. Run Celery worker and beat; `send_due_live_class_reminders` runs every five minutes and sends the 3-day, 1-day, 1-hour, and start-time reminders.

## Local checks

If production database values are present in `.env`, set `USE_SQLITE=True` for local tests:

`python manage.py test live_classes`
