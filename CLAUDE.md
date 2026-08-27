## Active constraints
- 2026-08-21: Leave NODE_OPTIONS / disable-process-title.js workaround alone — user is still evaluating it (dot_zshrc:15-16, dot_config/node/disable-process-title.js).

## Symptoms
- 2026-08-21: "history | grep -i radar" in an open interactive shell only returned 1 line ("1455 history | grep Radar-Triage-Agent-Skill") — "there must be many more entries - this looks very sparse".
- 2026-08-21: ran `create-dmg --volname "rTerm" ... "rTerm-beta1.dmg" rTerm\ 2026-08-18\ 09-00-35` in ~/rdev/rTerm/dist recently; "history | grep -i dmg" in the live shell doesn't surface it.
