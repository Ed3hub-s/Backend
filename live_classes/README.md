# Ed3Hub Live Classes

This app implements the product rules in the Live Classes specification. It owns scheduling, registration, payment/access state, reminders, attendance, recording authorization, and the server-side Cloudflare integration.

## Cloudflare setup

1. Create a Cloudflare RealtimeKit app.
2. Create an API token with Realtime permissions. Keep it on the Django server only.
3. Create or select two presets:
   - a host preset with moderation, screen sharing, chat, recording, and participant controls;
   - a learner preset with participant viewing, chat, hand raise, and the media permissions you want learners to have.
4. Set the `CLOUDFLARE_*` variables documented in `.env.example`.

Interactive classes use `group_call_host` for educators and
`group_call_participant` for learners. Both presets must use `GROUP_CALL`, allow
audio/video production, have `show_participant_list=true`, and keep
`hidden_participant=false`. Hosts can share their screen and moderate participants;
learners can control their own camera/microphone without receiving host permissions.
The shipped webinar preset names are mapped to these group-call presets even when
an older deployment still has webinar values in its environment. Custom preset
names are preserved; configure their permissions in the Cloudflare dashboard.

Saved participants have their preset updated before their next token refresh.
After deploying this change, both teachers and students should leave and rejoin
the class so their existing sessions pick up the updated permissions. No class
needs to be deleted or recreated. The browser starts with devices off and uses the
complete meeting UI (video grid, screen-share stage, participant list, and chat).
On narrow screens, additional controls may be in the UI Kit's More menu.

Verify with a teacher and a registered student in two separate browser profiles:
join the same class, enable each camera/microphone, confirm remote video/audio,
open Participants, then share a teacher browser tab and confirm it on the student
side. End the share and leave/rejoin to check the restored video grid and controls.
Camera/microphone access requires HTTPS (or localhost) and browser permission.

The classroom deliberately pins the browser assets to the v1 line:

- `@cloudflare/realtimekit@1.5.1`
- `@cloudflare/realtimekit-ui@1.2.0`

Cloudflare API credentials are never sent to the browser. Django creates meetings and issues participant tokens only after checking the educator owner or an ACTIVE learner registration.

Recordings are synchronized from Cloudflare when an authorized user requests the class recordings. Playback URLs are refreshed through an authenticated backend endpoint.

## Payments and reminders

See `../PAYMENT_ROLLOUT.md` for paid session bundles, recorded-course checkout,
admin video review, historical enrollment reconciliation and deployment checks.

Configure Paystack to send events to:

`https://<api-host>/api/live-classes/webhooks/paystack/`

The webhook is HMAC-SHA512 verified and reconciles successful payments and refunds. Run Celery worker and beat; `send_due_live_class_reminders` runs every five minutes and sends the 3-day, 1-day, 1-hour, and start-time reminders.

Paid checkout uses the backend `PAYSTACK_SECRET_KEY`; a frontend public key is
not needed for this hosted checkout flow. Set `FRONTEND_URL` to the deployed web
app so Paystack returns students to the right class. Configure the webhook above
in the matching Paystack test/live environment. The key must support the class's
currency; USD/GHS/KES availability depends on the merchant account.

Booking amount, currency, reference and customer email are recorded before
checkout. Repeated checkout requests reuse the saved link. Callback and webhook
verification both check those invoice values against Paystack's server response,
and repeated successful callbacks are idempotent. A later class price change
does not invalidate an already-issued invoice. Students can use **Check payment**
to recover a payment if they close the checkout tab or miss the callback.

Completed full refunds remove access; pending, processing, failed and partial
refunds do not automatically remove access. Partial-refund access decisions need
staff review. Refunded, revoked and cancelled bookings cannot be reactivated by
a delayed success webhook. This integration collects payment into the configured
merchant account; it does not implement teacher payout splits or initiate refunds.

Before accepting live payments, use Paystack test keys and a test checkout to
verify the redirect and webhook on the deployed domains. Local tests mock Paystack
and never charge a card. Review Paystack's dashboard webhook delivery logs after
deployment to confirm successful delivery.

## Local checks

If production database values are present in `.env`, set `USE_SQLITE=True` for local tests:

`python manage.py test live_classes`
