# Current setup

The monitor already has initialized state and working 2Captcha/Telegram access.
Do not repeat initialization or recreate the bot.

1. Keep Actions variable MONITOR_ENABLED set to true for hourly runs.
2. Review Actions > Visa appointment monitor. Scheduled runs show event schedule.
3. Manual runs default to monitor. Leave initialize_state unchecked.
4. Telegram now sends appointment alerts only. All other information is recorded
   in Actions and the new durable run-history files.
5. For optional email to berkeemerce@gmail.com, follow [EMAIL_SETUP.md](EMAIL_SETUP.md).
6. Dashboard source is in [dashboard/](dashboard/). Publication to a private
   chatgpt.site Site is pending an available execution workspace. No website
   has been published by this change yet.

Successful checks only describe months actually inspected. November/December
were inspected in the verified 12 November check; January was not exposed by
the portal. Failed checks and unreached months never mean no appointments.

See [README.md](README.md) for current behavior.
