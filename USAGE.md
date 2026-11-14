# Using Reviewlens

Open <http://localhost:7860>. The page you land on is the **public overview**: what the
product does, a demo box that scores a review live against the real API (no account
needed, nothing stored) and the seeded sample review sets.

Press **Open the analyzer** to reach the workspace at `/app/` and sign in with
`cenius@cenius.ai` / `cenius`. It opens on the **Analyze** tab; the four tabs across the
top are Analyze, Batch CSV, Samples and History.

## Analyze one review

1. Paste a review into the textarea — the counter under it shows `0 / 5,000 characters`
   and updates as you type. Over 5,000 characters the counter turns into an inline error
   and nothing is scored.
2. Press **Analyze review** (or pick one of the three examples). The button shows a busy
   state while the review is scored — typically a couple of milliseconds.
3. The result card shows:
   - the label chip and the numeric score on a -1 to 1 gauge,
   - **Lexicon words that fired**, e.g. `great +0.80`, `good -0.68 · negated`,
   - the **aspect breakdown** — price / quality / shipping with a verdict, the mention
     count and the exact clause that produced it, or "No aspects detected",
   - the review text and a "Saved to your history · <time>" line.

Empty input shows "Paste a review to analyze" inline and writes nothing.

## Score a CSV export

1. Open **Batch CSV**. Drop a `.csv` with a header row and at least one text column.
   The app reports the columns it found and pre-selects the review column.
2. Adjust the column in the dropdown if needed, then press **Score reviews**.
3. You get the summary card (rows scored, blanks skipped, per-label counts), the
   **Sentiment split** bar chart, the **Aspect breakdown** table, the scored-rows table
   and a **Download scored CSV** link. The download is your original file with
   `sentiment_label`, `sentiment_score`, `price_label`, `quality_label` and
   `shipping_label` appended, in the original row order (skipped rows stay, with empty
   sentiment columns).
4. **Recent batches** at the bottom keeps every batch you have scored with its own
   download link — they survive reloads and restarts.

Bad files fail with a plain message and leave the previous chart untouched: wrong
extension, unreadable CSV, a column name that does not exist (the message lists the
columns that do), an empty file, all-blank review column, or more than 1,000 rows.

## Sample review sets

**Samples** lists the three seeded sets with their description and review count. Expand a
card to read every review in it, then press **Send first review to analyzer** — the
Analyze tab opens with that review loaded, ready to score.

## History

Every single-review analysis is stored for your account. The **History** tab lists them
newest first (timestamp, label, score, excerpt) with a total count and a label split.
Click a row to load that review and its saved result back into the Analyze tab.

**Clear history** needs the confirmation checkbox ticked first: it deletes every stored
analysis for your account, and new analyses keep saving normally afterwards.

## Without an account

Anything on the public page works signed out: the hero stats, the sample sets and the
"Score a review right here" box, which posts to `/demo/analyze` and renders the label,
score, fired words and aspect breakdown live. History and CSV batches need a session,
because they are per-account.

## Scripting it

The same behaviour is available over HTTP — see the API table in `README.md`:

```bash
curl -u cenius@cenius.ai:cenius -H 'Content-Type: application/json' \
  -d '{"text":"Cheap price but the quality is awful"}' \
  http://localhost:7860/api/analyze
```

Without credentials every `/api` route except `/api/health` answers `401` with a Basic
challenge - the sample list and the stateless scoring box use `/demo/*` instead, which is
why the public page works signed out.

## Notes on the scoring

- Scores are deterministic: the same text always gives the same label, score and words.
- Negation is handled within a three-word window, so "not good" reads negative.
- Aspect verdicts come only from clauses that mention the aspect, which is why "cheap
  price but the quality is awful" gives price = positive and quality = negative.
- The lexicon is English only and lives in `app/data/lexicon.json` — edit it and restart
  to tune the scorer for your catalogue.
