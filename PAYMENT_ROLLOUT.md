# Payments, live bundles and video review rollout

## Gateway audit

The local backend environment contains a live-mode `PAYSTACK_SECRET_KEY`; the
frontend environment also has a live public key. A read-only Paystack integration
request accepted the backend credential (HTTP 200). No charge was initiated.
This does not prove the deployed server uses the same environment or that its
webhook is configured. Never commit either environment file or log secret keys.

Both course and live-class checkout now use backend-initialized hosted checkout.
The frontend public key and inline Paystack script are no longer needed for these
flows. Price, currency, customer email and reference come from a database invoice,
not browser input. Successful verification is idempotent and binds all four values.

## Educator workflow

1. Create two or more paid live classes using **Create class**. Each session has
   its own title, schedule, duration, cover, capacity and classroom.
2. Open **Class bundles** in live-class navigation.
3. Enter a bundle title, description, currency and total price. Select the sessions.
4. Publish the bundle. The learner sees the complete session list and pays the
   bundle total once, even when checkout starts from an individual session page.
   Each session's detail page also lists the other included sessions before checkout.

Only your published, future, unbundled paid sessions in the same currency can be
selected. No session may already have registrations, including pending payments.
The educator picker uses server-provided eligibility to exclude booked sessions.
Bundle composition and price are fixed after creation; individual session pricing
cannot be edited and bundled sessions cannot be deleted through the educator API.
Sessions can still be rescheduled or cancelled. Refunds remain an operator action
in Paystack; cancelling a class does not initiate a financial refund automatically.
New bundle purchases close once any session has ended or is cancelled.

All seats are checked and reserved in one database transaction. One payment is
linked to all included registrations. Verification activates all pending sessions,
allocates the invoice across sessions without changing its total, and does not
restore revoked, cancelled or refunded registrations. Joining or
requesting a recording always reads registration and payment state from the DB.
Educators retain access to their own rooms without buying a learner registration.
Revocation prevents subsequent joins/token requests; it does not forcibly eject
someone already connected to Cloudflare. Existing active connections need provider
moderation when immediate removal is required.

## Recorded courses

`POST /api/courses/<id>/enroll/` enrolls free courses immediately. Paid courses
return HTTP 202 with `checkout.authorization_url` and `checkout.reference`.
No enrollment, educator credit or affiliate purchase commission is issued while
payment is pending. The return page `/courses/payment-return` submits the saved
reference to the same endpoint and supports retrying verification without paying
again. A signed webhook can fulfill payment if the browser never returns.

Paid content, individual lessons, course resources and progress updates require
an enrollment linked to a successful payment belonging to that course and learner.
Public catalogue responses keep lesson outlines but withhold paid content, video
URLs, transcripts, resources and quizzes. Published free-preview lessons remain
visible. Staff and the owning educator can review lesson videos without purchase.

Historical paid enrollments without a verified payment are NOT automatically
grandfathered in. Audit them before deployment and reconcile genuine receipts via
a reviewed operational process. Do not invent payment records or mark historical
payments successful without gateway evidence. The old endpoint also credited
wallets without verification, so historical balances need a separate reconciliation.

Full processed refunds revoke payment-backed access and reverse the educator
credit once. Partial refunds do not automatically remove access. Affiliate refund
clawbacks, chargeback/dispute processing and historical wallet adjustments still
require an operator reconciliation process; this change does not initiate payouts.

## Admin video review

In Django admin, open **Courses > Lessons > a lesson** to use the embedded video
player. Players also appear in a module's lesson inline list. Course module inlines
provide change links to the module editor. The **Open video** link is a fallback
for direct playback. Staff with the lesson view permission can also watch without
permission to edit a lesson. The browser must support the uploaded video's codec,
and the storage origin must be reachable and permit retrieving the file.

Local verification on 2026-10-05: admin lesson and module pages render players,
including for staff with view-only lesson permission. The existing `hi_720p.mp4`
upload played in Chrome (46.231 seconds). Local lesson ID 1 references
`courses/videos/WhatsApp_Video_2026-04-17_at_11.08.40_AM.mp4`, which is missing
from local storage and must be restored or re-uploaded. Production media was not
inspected; a player cannot recover a missing upload.

Existing R2 configuration exposes media via a public custom domain. API permission
checks prevent discovering paid links through course endpoints, but do not revoke
previously copied public storage URLs. A private video bucket/origin with expiring
playback links is a separate production hardening requirement. Do not describe
public bucket URLs as protected or DRM-controlled by these database checks.

## Deployment checklist

1. Back up the database and audit historical paid enrollments and wallet credits.
2. Deploy backend and frontend changes together, then apply the migrations:
   `python manage.py migrate`. The new migrations are courses `0004` and live_classes
   `0003`; they preserve existing records and do not fabricate historical payments.
3. Set backend `PAYSTACK_SECRET_KEY` and `FRONTEND_URL` for the intended environment.
   Recorded course prices use NGN. Live-class currencies must be enabled on the
   merchant account. Do not use live keys in automated tests.
4. In the matching Paystack environment, configure the one shared webhook URL:
   `https://<api-host>/api/live-classes/webhooks/paystack/`.
   It handles standalone classes, bundles and recorded courses. Preserve the raw
   request body and `x-paystack-signature` header through the reverse proxy.
5. Test with Paystack test credentials on staging: successful/cancelled checkout,
   reload/retry, duplicate callback plus webhook, wrong reference/user/amount,
   full refund, delayed success after refund, and provider outage.
6. Confirm a bundle purchaser sees all sessions in **My schedule**, can enter each
   during its join window, and cannot enter any after payment is refunded. Verify
   Cloudflare camera, audio and recording playback with separate browser accounts.
7. Confirm a recorded-course purchaser can play uploaded videos; a non-purchaser
   and a refunded purchaser cannot retrieve paid lesson data through the API.
8. Open a real uploaded lesson in admin and verify playback/seeking in the target
   browsers. Codec/storage availability is not established by an HTML unit test.
9. Verify webhook delivery logs and confirm the deployed payment return URL works.
   A local key check and mocked regression suite do not prove live end-to-end payment.

## Local checks

Verified on 2026-10-05: 65 backend tests, the TypeScript check, migration drift
check, and five browser scenarios for course payment retry, educator bundle
creation, standalone checkout, live payment retry, and bundle checkout passed.
Gateway responses were mocked; no real payment was submitted.

Set `USE_SQLITE=True` to avoid the production database. Prefer local file storage,
an in-memory channel layer and a local-memory email backend for automated tests.

`python manage.py test courses live_classes`

`python manage.py makemigrations --check --dry-run`

`npx tsc --noEmit --incremental false` in Frontend checks TypeScript independently
of the existing Next configuration, which ignores type errors during builds.

With a local frontend running on port 3100 and Playwright available, run
`node scripts/check-live-class-payments.cjs` and
`node scripts/check-payment-bundles.cjs` from Frontend. Set
`CLASSROOM_TEST_PLAYWRIGHT` to an existing playwright/playwright-core installation
if it is not installed locally. These browser checks mock API/payment responses;
they do not submit real payments.
