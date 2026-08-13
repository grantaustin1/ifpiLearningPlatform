"""Backend tests for media_opacity clamping (Iter 60)"""
import os, requests, pytest

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://learning-hub-968.preview.emergentagent.com').rstrip('/')

ADMIN_EMAIL = 'uat-admin@ifpi.org'
ADMIN_PASS = 'UatAdmin!2026'


@pytest.fixture(scope='module')
def admin_session():
    s = requests.Session()
    r = s.post(f'{BASE_URL}/api/auth/login', json={'email': ADMIN_EMAIL, 'password': ADMIN_PASS})
    assert r.status_code == 200, f'login failed: {r.status_code} {r.text}'
    tok = r.json().get('access_token')
    assert tok
    s.headers.update({'Authorization': f'Bearer {tok}', 'Content-Type': 'application/json'})
    return s


@pytest.fixture(scope='module')
def test_course(admin_session):
    r = admin_session.post(f'{BASE_URL}/api/courses', json={
        'title': 'TEST_iter60_opacity_course',
        'description': 'transient',
        'category': 'TEST',
        'duration_minutes': 5,
        'passing_score': 70,
    })
    assert r.status_code in (200, 201), r.text
    cid = r.json()['id']
    yield cid
    # cleanup
    try:
        admin_session.post(f'{BASE_URL}/api/courses/{cid}/unpublish')
    except Exception:
        pass
    admin_session.delete(f'{BASE_URL}/api/courses/{cid}')


def test_add_slide_clamps_low(admin_session, test_course):
    r = admin_session.post(f'{BASE_URL}/api/courses/{test_course}/slides', json={
        'title': 'low', 'slide_type': 'IMAGE', 'content': '',
        'media_url': 'https://example.com/x.png',
        'media_opacity': 5,
    })
    assert r.status_code in (200, 201), r.text
    assert r.json()['media_opacity'] == 20


def test_add_slide_clamps_high(admin_session, test_course):
    r = admin_session.post(f'{BASE_URL}/api/courses/{test_course}/slides', json={
        'title': 'high', 'slide_type': 'IMAGE', 'content': '',
        'media_url': 'https://example.com/y.png',
        'media_opacity': 150,
    })
    assert r.status_code in (200, 201), r.text
    assert r.json()['media_opacity'] == 100


def test_add_slide_valid_40(admin_session, test_course):
    r = admin_session.post(f'{BASE_URL}/api/courses/{test_course}/slides', json={
        'title': 'mid', 'slide_type': 'IMAGE', 'content': '',
        'media_url': 'https://example.com/m.png',
        'media_opacity': 40,
    })
    assert r.status_code in (200, 201), r.text
    sid = r.json()['id']
    assert r.json()['media_opacity'] == 40

    # PATCH to change
    r2 = admin_session.patch(f'{BASE_URL}/api/courses/{test_course}/slides/{sid}', json={'title': 'mid', 'slide_type': 'IMAGE', 'media_opacity': 60})
    assert r2.status_code == 200
    assert r2.json()['media_opacity'] == 60

    # GET course returns per-slide opacity
    g = admin_session.get(f'{BASE_URL}/api/courses/{test_course}')
    assert g.status_code == 200
    slides = g.json()['slides']
    match = [s for s in slides if s['id'] == sid][0]
    assert match['media_opacity'] == 60


def test_patch_clamps(admin_session, test_course):
    # create slide
    r = admin_session.post(f'{BASE_URL}/api/courses/{test_course}/slides', json={
        'title': 'patch', 'slide_type': 'VIDEO', 'content': '',
        'media_url': 'https://example.com/v.mp4',
        'media_opacity': 50,
    })
    sid = r.json()['id']
    # Patch too low
    r2 = admin_session.patch(f'{BASE_URL}/api/courses/{test_course}/slides/{sid}', json={'title': 'p', 'slide_type': 'VIDEO', 'media_opacity': 1})
    assert r2.status_code == 200
    assert r2.json()['media_opacity'] == 20
    # Patch too high
    r3 = admin_session.patch(f'{BASE_URL}/api/courses/{test_course}/slides/{sid}', json={'title': 'p', 'slide_type': 'VIDEO', 'media_opacity': 999})
    assert r3.status_code == 200
    assert r3.json()['media_opacity'] == 100
