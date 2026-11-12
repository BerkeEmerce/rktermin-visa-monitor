import sys
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from response_snapshots import capture, sanitized_html


def test_removes_active_content_credentials_and_external_resources():
    html = '''<div id="content"><h2>12/2026</h2><p>No appointments.</p>
    <script>secret()</script><style>@import 'https://example.com/a.css';</style>
    <input type="hidden" name="token" value="private-token"><iframe src="https://example.com"></iframe>
    <a href="/month;jsessionid=PRIVATE"><img src="images/go-next.gif" onerror="secret()"></a></div>'''
    saved = sanitized_html(html)
    assert '12/2026' in saved and 'No appointments.' in saved
    assert '→' in saved
    assert 'PRIVATE' not in saved and 'private-token' not in saved
    assert 'example.com' not in saved and 'secret()' not in saved
    assert '<script' not in saved and '<iframe' not in saved and '<input' not in saved


def test_session_attribute_changes_produce_identical_rendered_content():
    assert sanitized_html('<h2 id="session1">11/2026</h2>') == sanitized_html('<h2 id="session2">11/2026</h2>')


def test_capture_records_exact_response_digest_and_sanitized_file(tmp_path):
    import hashlib
    html = '<h2>11/2026</h2><p>No appointments.</p>'
    result = {}
    capture(html, result, 'Current month', directory=tmp_path)
    entry = result['snapshots'][0]
    assert entry['response_sha256'] == hashlib.sha256(html.encode()).hexdigest()
    assert (tmp_path / entry['file']).exists()


def test_capture_failure_never_changes_check_status():
    result = {'status': 'ok', 'dates': []}
    directory = Mock()
    directory.mkdir.side_effect = OSError('Disk failure')
    capture('<h2>11/2026</h2>', result, 'Current month', directory=directory)
    assert result['status'] == 'ok'
    assert 'snapshot_capture_error' in result
