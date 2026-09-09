# PLATO v3.5

One phone app at the existing GitHub Pages root:
Game → Ticket count → Generate v3.5.

The root loads the existing distilled v3.5 engine and Prize Coverage Mode directly.
The former `/v35/` URL only redirects to the root. Legacy controls and original
protocol/checkpoint files are retained under `audit/` and are never loaded by the
phone interface. Earlier version branches are untouched.

Live inference includes all 9,771 supplied records, with raw identities restricted
to their rule era and normalized structural transfer across eras. See
`V35_TRAINING_PROTOCOL.md` for the corrected Oz Lotto era boundary, exact scope
of full-history use, and the limitation on reproducing the absent heavy trainer.
No new training or predictive-edge claim is part of this UI/inference repair.

`sw.js` owns one versioned root cache. It precaches the complete release before
activation, serves root navigations network-first, preserves matching offline
assets, and removes only obsolete PLATO caches belonging to this app path.
The old nested worker unregisters itself. Local draw/portfolio storage is kept.

Tests (Node 20+; no dependency installation):

```sh
node --test tests/*.test.cjs
```

Deployment remains the existing main-branch GitHub Pages workflow. Tests run
before publishing. A passing workflow is followed by actual live-page generation
and reload checks. Prize Coverage diversifies tickets; prospective evidence of
predictive advantage is not established.
