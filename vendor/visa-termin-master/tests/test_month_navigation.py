import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from monitor_nicosia import check_months, displayed_month, next_arrow, calendar_arrow


def page(month, year, next_month=None, dates=(), previous_month=None):
    html = f'<h2>{month}/{year}</h2>'
    if dates:
        for day in dates:
            html += f'<a href="extern/appointment_showDay.do?locationCode=niko&amp;realmId=926&amp;categoryId=1860&amp;dateStr={day}">Book</a>'
    else:
        html += '<p>Unfortunately, there are no appointments available at this time.</p>'
    if next_month:
        html += f'<a href="extern/appointment_showMonth.do;jsessionid=fixture?locationCode=niko&amp;realmId=926&amp;categoryId=1860&amp;dateStr={next_month}"><img src="images/go-next.gif"></a>'
    if previous_month:
        html += f'<a href="extern/appointment_showMonth.do;jsessionid=fixture?locationCode=niko&amp;realmId=926&amp;categoryId=1860&amp;dateStr={previous_month}"><img src="images/go-previous.gif"></a>'
    return html


def scan(tmp_path, pages, current='2026-11'):
    target = tmp_path / 'response.html'
    target.write_text(pages[0], encoding='utf-8')
    pending = iter(pages[1:])
    def move(url, output):
        Path(output).write_text(next(pending), encoding='utf-8')
        return True
    handler = Mock()
    handler._curl.side_effect = move
    result = {}
    with patch('monitor_nicosia.current_month', return_value=current):
        check_months(handler, result, target)
    return result, handler


def test_checks_beyond_three_months_until_arrow_stays(tmp_path):
    result, handler = scan(tmp_path, [page(11, 2026, '01.12.2026'),
                                     page(12, 2026, '01.01.2027'), page(1, 2027, '01.02.2027'),
                                     page(2, 2027, '01.03.2027'), page(2, 2027, '01.03.2027')])
    assert [m['month'] for m in result['months']] == ['2026-11', '2026-12', '2027-01', '2027-02']
    assert handler._curl.call_count == 4
    assert result['navigation'][-1]['status'] == 'stayed'
    assert '2027-03 was not checked' in result['navigation_note']


def test_third_month_stays_on_second_reports_it_without_retry(tmp_path):
    december = page(12, 2026, '01.01.2027')
    result, handler = scan(tmp_path, [page(11, 2026, '01.12.2026'), december, december])
    assert [m['month'] for m in result['months']] == ['2026-11', '2026-12']
    assert handler._curl.call_count == 2
    assert result['navigation'][-1]['status'] == 'stayed'
    assert '2027-01 was not checked' in result['navigation_note']
    assert len(result['snapshots']) == 3
    assert result['snapshots'][-1]['requested'] == '2027-01'
    assert result['snapshots'][1]['render_sha256'] == result['snapshots'][2]['render_sha256']


def test_first_arrow_stays_stops_after_one_request(tmp_path):
    november = page(11, 2026, '01.12.2026')
    result, handler = scan(tmp_path, [november, november])
    assert len(result['months']) == 1
    assert handler._curl.call_count == 1


def test_no_arrow_reports_normal_stop(tmp_path):
    result, handler = scan(tmp_path, [page(11, 2026)])
    assert handler._curl.call_count == 0
    assert result['navigation'][-1]['status'] == 'no_arrow'


def test_collects_available_dates_from_next_month_and_year_rollover(tmp_path):
    result, handler = scan(tmp_path, [page(12, 2098, '01.01.2099'),
                                     page(1, 2099, dates=['15.01.2099', '03.01.2099'])], current='2098-12')
    assert result['dates'] == ['03.01.2099', '15.01.2099']
    assert handler._curl.call_count == 1


def test_captcha_after_arrow_is_a_failure_not_a_normal_stop(tmp_path):
    with pytest.raises(RuntimeError):
        scan(tmp_path, [page(11, 2026, '01.12.2026'), '<h2>12/2026</h2><input name="captchaText">'])


def test_wrong_month_is_a_failure(tmp_path):
    with pytest.raises(RuntimeError, match='unexpected calendar month'):
        scan(tmp_path, [page(11, 2026, '01.12.2026'), page(1, 2027)])


def test_ignores_language_links_and_rejects_foreign_arrow():
    assert next_arrow('<a href="?request_locale=en"><img src="gb.png"></a>') is None
    with pytest.raises(RuntimeError):
        next_arrow('<a href="https://example.com/"><img src="go-next.gif"></a>')


@pytest.mark.parametrize('heading', ['<h2>November 2026</h2>', '<h2>11/2026</h2>'])
def test_reads_actual_displayed_heading(heading):
    assert displayed_month(heading) == '2026-11'


def test_starting_december_returns_to_november_then_scans_forward(tmp_path):
    december = page(12, 2026, '01.01.2027', previous_month='01.11.2026')
    november = page(11, 2026, '01.12.2026', dates=['25.11.2026'])
    january = page(1, 2027, '01.02.2027')
    result, handler = scan(tmp_path, [december, november, december, january, january])
    assert [m['month'] for m in result['months']] == ['2026-11', '2026-12', '2027-01']
    assert result['dates'] == ['25.11.2026']
    assert handler._curl.call_count == 4
    assert 'dateStr=01.11.2026' in handler._curl.call_args_list[0].args[0]
    assert result['navigation'][0]['direction'] == 'back'
    assert result['navigation'][0]['status'] == 'advanced'
    assert '2027-02 was not checked' in result['navigation_note']
    assert len(result['snapshots']) == 5
    assert result['snapshots'][1]['stage'] == 'After back arrow'
    assert result['snapshots'][-1]['requested'] == '2027-02'


def test_starting_current_month_never_requests_previous_month(tmp_path):
    november = page(11, 2026, '01.12.2026', previous_month='01.10.2026')
    december = page(12, 2026, '01.01.2027')
    result, handler = scan(tmp_path, [november, december, december])
    assert [m['month'] for m in result['months']] == ['2026-11', '2026-12']
    assert handler._curl.call_count == 2
    assert all(n['direction'] == 'next' for n in result['navigation'])
    assert '2027-01 was not checked' in result['navigation_note']


def test_back_across_new_year_then_reaches_all_forward_months(tmp_path):
    result, handler = scan(tmp_path, [page(1, 2099, '01.02.2099', previous_month='01.12.2098'),
                                     page(12, 2098, '01.01.2099'), page(1, 2099, '01.02.2099'),
                                     page(2, 2099, '01.03.2099'), page(3, 2099, dates=['15.03.2099'])], current='2098-12')
    assert [m['month'] for m in result['months']] == ['2098-12', '2099-01', '2099-02', '2099-03']
    assert result['dates'] == ['15.03.2099']
    assert handler._curl.call_count == 4


@pytest.mark.parametrize('response', [page(10, 2026), '<h2>11/2026</h2><input name="captchaText">'])
def test_invalid_back_response_fails_instead_of_claiming_checked(tmp_path, response):
    with pytest.raises(RuntimeError):
        scan(tmp_path, [page(12, 2026, previous_month='01.11.2026'), response])


def test_back_request_failure_is_reported(tmp_path):
    target = tmp_path / 'response.html'
    target.write_text(page(12, 2026, previous_month='01.11.2026'), encoding='utf-8')
    handler = Mock()
    handler._curl.return_value = False
    with patch('monitor_nicosia.current_month', return_value='2026-11'):
        with pytest.raises(RuntimeError, match='Calendar-arrow request failed'):
            check_months(handler, {}, target)
    handler._curl.assert_called_once()


def test_back_arrow_rejects_wrong_category():
    with pytest.raises(RuntimeError):
        calendar_arrow('<a href="extern/appointment_showMonth.do?locationCode=niko&amp;realmId=926&amp;categoryId=999"><img src="go-previous.gif"></a>', 'previous')


@pytest.mark.parametrize('has_arrow', [True, False])
def test_cannot_reach_current_month_is_a_failure(tmp_path, has_arrow):
    december = page(12, 2026, previous_month='01.11.2026' if has_arrow else None)
    with pytest.raises(RuntimeError, match='Could not reach current month 2026-11'):
        scan(tmp_path, [december, december] if has_arrow else [december])


def test_moves_back_multiple_times_to_current_month(tmp_path):
    result, handler = scan(tmp_path, [page(2, 2027, previous_month='01.01.2027'),
                                     page(1, 2027, previous_month='01.12.2026'),
                                     page(12, 2026, previous_month='01.11.2026'), page(11, 2026)])
    assert [m['month'] for m in result['months']] == ['2026-11']
    assert handler._curl.call_count == 3
    assert all(n['direction'] == 'back' for n in result['navigation'][:-1])


def test_starting_past_month_moves_forward_to_current_month(tmp_path):
    result, handler = scan(tmp_path, [page(10, 2026, '01.11.2026'), page(11, 2026)])
    assert [m['month'] for m in result['months']] == ['2026-11']
    assert handler._curl.call_count == 1


def test_arrow_limit_stops_without_extra_request(tmp_path, monkeypatch):
    monkeypatch.setattr('monitor_nicosia.MAX_ARROW_REQUESTS', 2)
    result, handler = scan(tmp_path, [page(11, 2026, '01.12.2026'),
                                     page(12, 2026, '01.01.2027'), page(1, 2027, '01.02.2027')])
    assert handler._curl.call_count == 2
    assert len(result['months']) == 3
    assert 'safety limit' in result['navigation_note']
    assert '2027-02 was not checked' in result['navigation_note']


def test_arrow_limit_before_current_month_is_a_failure(tmp_path, monkeypatch):
    monkeypatch.setattr('monitor_nicosia.MAX_ARROW_REQUESTS', 1)
    with pytest.raises(RuntimeError, match='Could not reach current month'):
        scan(tmp_path, [page(1, 2027, previous_month='01.12.2026'),
                        page(12, 2026, previous_month='01.11.2026')])


@pytest.mark.parametrize('utc,expected', [('2026-11-30T21:59:00+00:00', '2026-11'),
                                        ('2026-11-30T22:00:00+00:00', '2026-12'),
                                        ('2026-06-30T21:00:00+00:00', '2026-07')])
def test_current_month_uses_north_nicosia_time(utc, expected, monkeypatch):
    from datetime import datetime
    from monitor_nicosia import current_month
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.fromisoformat(utc).astimezone(tz)
    monkeypatch.setattr('monitor_nicosia.datetime', FixedDateTime)
    assert current_month() == expected
