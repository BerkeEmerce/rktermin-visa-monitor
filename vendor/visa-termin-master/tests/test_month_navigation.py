import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from monitor_nicosia import check_months, displayed_month, next_arrow


def page(month, year, next_month=None, dates=()):
    html = f'<h2>{month}/{year}</h2>'
    if dates:
        for day in dates:
            html += f'<a href="extern/appointment_showDay.do?locationCode=niko&amp;realmId=926&amp;categoryId=1860&amp;dateStr={day}">Book</a>'
    else:
        html += '<p>Unfortunately, there are no appointments available at this time.</p>'
    if next_month:
        html += f'<a href="extern/appointment_showMonth.do;jsessionid=fixture?locationCode=niko&amp;realmId=926&amp;categoryId=1860&amp;dateStr={next_month}"><img src="images/go-next.gif"></a>'
    return html


def scan(tmp_path, pages):
    target = tmp_path / 'response.html'
    target.write_text(pages[0], encoding='utf-8')
    pending = iter(pages[1:])
    def move(url, output):
        Path(output).write_text(next(pending), encoding='utf-8')
        return True
    handler = Mock()
    handler._curl.side_effect = move
    result = {}
    check_months(handler, result, target)
    return result, handler


def test_checks_three_months_with_exactly_two_arrow_requests(tmp_path):
    result, handler = scan(tmp_path, [page(11, 2026, '01.12.2026'),
                                     page(12, 2026, '01.01.2027'), page(1, 2027, '01.02.2027')])
    assert [m['month'] for m in result['months']] == ['2026-11', '2026-12', '2027-01']
    assert handler._curl.call_count == 2
    assert all(n['status'] == 'advanced' for n in result['navigation'])


def test_third_month_stays_on_second_reports_it_without_retry(tmp_path):
    december = page(12, 2026, '01.01.2027')
    result, handler = scan(tmp_path, [page(11, 2026, '01.12.2026'), december, december])
    assert [m['month'] for m in result['months']] == ['2026-11', '2026-12']
    assert handler._curl.call_count == 2
    assert result['navigation'][-1]['status'] == 'stayed'
    assert '2027-01 was not checked' in result['navigation_note']


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
                                     page(1, 2099, dates=['15.01.2099', '03.01.2099'])])
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
