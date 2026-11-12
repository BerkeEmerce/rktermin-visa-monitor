This copy is based on rashidisayev/visa-termin-master commit
6d5b967badc20d6d1f7e091deb8139b380044c41 (PolyForm Noncommercial 1.0.0).

Deployment: BerkeEmerce/rktermin-visa-monitor, vendor/visa-termin-master.
Workflow: .github/workflows/nicosia-upstream.yml.

Target: North Nicosia, locationCode=niko, realmId=926, categoryId=1860.
Schedule: every 30 minutes, at :27 and :57 UTC (GitHub may delay runs).
Mode: notifications only. No applicant data is configured. The cloud entry
point never invokes a booking method. All future dates are accepted.
Coverage: only the current portal month, as implemented by the upstream tool.

Existing CAPTCHA_API_KEY, TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID repository
secrets are used without copying or exposing their values. Hosting uses free
public-repository Linux runners. CAPTCHA solves consume your paid balance.

The abandoned monitor.yml remains disabled. The old dashboard is not used by
this new workflow. Open GitHub Actions for the latest check and result.json.
Use workflow_dispatch with verify_setup=true to check Telegram delivery too.
Successful empty scheduled checks send no Telegram message. Available dates
and check failures send alerts. A date still available may alert again on the
next check.

To stop: gh workflow disable nicosia-upstream.yml --repo BerkeEmerce/rktermin-visa-monitor
To start: gh workflow enable nicosia-upstream.yml --repo BerkeEmerce/rktermin-visa-monitor
Manual check: gh workflow run nicosia-upstream.yml --repo BerkeEmerce/rktermin-visa-monitor

GitHub scheduling is best effort, and public-repository schedules are disabled
after 60 days without repository activity. Check Actions if alerts stop.
