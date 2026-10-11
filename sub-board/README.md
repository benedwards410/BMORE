# Sub Board

A quick substitution board for use on an iPad during a game. One HTML file, no accounts, no network.

It does two things:

1. **Big timers on the players on the field.** Each tile shows the position, number, name, time on this shift in large type, and total minutes today underneath. Tiles warm up in colour as a shift gets long.
2. **Bench sorted by who has sat the longest.** Each bench row shows how long that player has been sitting and their total minutes today.

Also: two halves with a halftime break, pause/resume, one-tap undo of the last sub, and an Out/In toggle for players who are hurt, left early, or arrived late.

## Install on the iPad

1. Open the deployed URL in Safari.
2. Tap Share, then **Add to Home Screen**.
3. Open it from the Home Screen. It works offline after the first load.

## Using it

- **Roster** tab: add numbers and names, pick half length and formation (4-3-3 default).
- **Game** tab: tap a spot, tap a bench player to place them. Tap **Kick off**.
- To sub: tap the player on the field, then the bench player coming on (or the other way round). Tap two spots to switch positions.
- **Halftime** and **End game** need two taps so a bump doesn't end the half.

## Data

Everything lives in the browser's local storage on that device. Nothing is sent anywhere. **Erase all data** on the Roster tab clears it.

## Files

`index.html` is the whole app. `sw.js` and `manifest.webmanifest` make it installable and offline. `_headers` sets no-index and no-cache for the HTML on Netlify-style hosts.
