# Visa monitor dashboard

A buildless, responsive dashboard. It reads non-sensitive run records from the
existing monitor-state branch and uses GitHub Actions metadata to show recent
runs that failed before a record could be saved. No tokens are embedded.

## Publish with Sites
The site must be created owner-private so access requires the owner's OpenAI
account. Copy dashboard/dist into a new Site checkout, register the Site once,
and set its static directory to dist in .openai/hosting.json. Push/package the
source with the Sites workflow helper and deploy privately. This dashboard is
not yet published; no live chatgpt.site URL is claimed.

## Records and semantics
scripts/publish_run_log.py archives attempts in run-history/YYYY-MM-DD.json and
maintains run-history/index.json on monitor-state. UTC dates select archive
files; the interface displays Europe/Berlin times. Every new attempt has a
separate entry. Checked months show Yes/No; unreachable months show Not checked.
Existing workflow metadata alone never establishes an empty calendar.
Failures and cooldown skips are visible without sending Telegram health alerts.
The app refreshes visible pages every minute; Actions API metadata is fetched
at most once every five minutes to limit unauthenticated API usage.
Screenshots are not captured by the current HTTP monitor, and none are faked.
Historical per-month results before this change are not reconstructed from guesses.
