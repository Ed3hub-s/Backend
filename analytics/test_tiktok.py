from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase, override_settings

from .tasks import send_tiktok_event
from .tiktok import queue_tiktok_event, request_match_data


@override_settings(
    TIKTOK_PIXEL_ID='pixel-test',
    TIKTOK_EVENTS_ACCESS_TOKEN='token-test',
    TIKTOK_EVENTS_API_URL='https://business-api.tiktok.com/open_api/v1.3/event/track/',
)
class TikTokEventsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('learner', ' Learner@Example.com ')

    @patch('analytics.tasks.requests.post')
    def test_task_sends_required_v13_shape_with_hashed_identifiers(self, post):
        response = Mock()
        response.json.return_value = {'code': 0, 'message': 'OK', 'request_id': 'request-1'}
        post.return_value = response

        result = send_tiktok_event.run({
            'event': 'Purchase',
            'event_id': 'purchase-1',
            'email': 'hashed-email',
            'external_id': 'hashed-user',
            'url': 'https://ed3hub.com/courses/example',
            'properties': {'currency': 'NGN', 'value': 1000.0},
            'match_data': {'user_agent': 'Browser'},
        })

        self.assertTrue(result['sent'])
        body = post.call_args.kwargs['json']
        self.assertEqual(body['event_source'], 'web')
        self.assertEqual(body['event_source_id'], 'pixel-test')
        event = body['data'][0]
        self.assertEqual(event['event_id'], 'purchase-1')
        self.assertEqual(event['page']['url'], 'https://ed3hub.com/courses/example')
        self.assertEqual(event['user']['email'], 'hashed-email')
        self.assertNotIn('ip', event['user'])
        self.assertEqual(post.call_args.kwargs['headers']['Access-Token'], 'token-test')

    @patch('analytics.tasks.send_tiktok_event.delay')
    def test_queue_hashes_user_data_and_enqueues_after_commit(self, delay):
        with self.captureOnCommitCallbacks(execute=True):
            queued = queue_tiktok_event(
                event='CompleteRegistration', event_id='registration-1', user=self.user,
                url='https://ed3hub.com/sign-in',
            )
        self.assertTrue(queued)
        payload = delay.call_args.args[0]
        self.assertEqual(len(payload['email']), 64)
        self.assertEqual(len(payload['external_id']), 64)
        self.assertNotEqual(payload['email'], self.user.email)

    def test_request_match_data_reads_tiktok_and_proxy_values(self):
        request = RequestFactory().get(
            '/?ttclid=click-id',
            HTTP_X_FORWARDED_FOR='203.0.113.4, 10.0.0.2',
            HTTP_USER_AGENT='Browser',
            HTTP_COOKIE='_ttp=cookie-id',
        )
        match = request_match_data(request)
        self.assertEqual(match['ip'], '203.0.113.4')
        self.assertEqual(match['ttclid'], 'click-id')
        self.assertEqual(match['ttp'], 'cookie-id')
