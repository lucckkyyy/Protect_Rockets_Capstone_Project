# 🛡️ Aware Rockets

A browser-based phishing-awareness game for university students, built with **Python + Streamlit**.

You play a cybersecurity analyst in a fictional university inbox. Each round shows a simulated email; you
inspect it, classify it as **Low Risk**, **Suspicious** or **High Risk**, then see how a built-in rule-based
**detector** judged the same email (*Human vs. Detector*), plus the warning signs and an explanation.

## Features

- **5 rounds per game**, difficulty rising easy → medium → hard, picked from **24 fictional emails**
- **Student-focused scams:** fake IT suspension, fake scholarship, loan forgiveness, tuition refund,
  housing deadline, fake job offer, professor gift-card request, QR-code parking ticket ("quishing"),
  parcel notice, look-alike login pages. Plus legitimate emails, so players learn not to cry wolf
- **Email headers panel:** SPF / DKIM / DMARC results, link inspector with the real destinations
- **Human vs. Detector:** your answer, the detector's answer and the correct answer side by side
- **Spotter bonus:** optionally tick the warning signs you see for up to +20 points per round
- **Awareness rank + streak that carry across games:** Rookie → Analyst → Defender → Guardian (saved in `player_stats.json`)
- Results dashboard with a personalised learning tip, missed-email review and a **CSV download**
- Everything is fictional: all domains end in `.example`, and links are shown as plain text, never opened

## Scoring

| What | Points |
|---|---|
| Correct classification | +100 (max 500 per game) |
| Spotter bonus (only on correctly classified emails) | up to +20 per round (max +100) |
| Wrong warning sign ticked | cancels one correct tick |
| Legitimate email: tick nothing | +20 |

XP for your rank = points + bonus from every game (a perfect game = 600 XP).

## 1. Run it (Windows)

**Quickest way:** install Python, then double-click `run_game.bat`. The first run installs what it needs (about a minute), then the game opens in your browser.

Or manually:

Install [Python 3.10+](https://www.python.org/downloads/) (tick **"Add Python to PATH"**) and, optionally,
[VS Code](https://code.visualstudio.com/). Open a terminal in this folder and run:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

macOS / Linux:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The game opens at http://localhost:8501. Stop it with `Ctrl+C`.

## 2. Run the tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## 3. Project structure

| File | What it does |
|---|---|
| `app.py` | The Streamlit interface: home, email challenge, feedback, results |
| `detector.py` | Rule-based detection: sender, language, URL and authentication checks → risk score |
| `game_logic.py` | Rounds, scoring, spotter bonus, progress, learning tips, CSV export (no UI code) |
| `stats.py` | Lifetime profile: XP, rank, streaks, saved to `player_stats.json` |
| `api_client.py` | Optional bridge to an external detection API (see section 6) |
| `questions.json` | The fictional email scenarios |
| `.streamlit/config.toml` | Navy-and-gold theme |
| `tests/` | 50+ pytest tests, including a full headless playthrough of the app |

## 4. Make it your own

- **Rename the game:** edit `APP_NAME` and `APP_TAGLINE` at the top of `app.py`.
- **Change colours:** `.streamlit/config.toml` and the `NAVY`/`GOLD` values in `app.py`.
- **Change the fictional university:** edit `TRUSTED_DOMAINS` in `detector.py`, then update the sender addresses in `questions.json`.
- **Reset your profile:** delete `player_stats.json`.
- **Add emails:** copy any entry in `questions.json`. Required fields: `id`, `level` (easy/medium/hard),
  `answer` (Low Risk/Suspicious/High Risk), `focus` (sender/language/links), `sender_name`, `sender_email`,
  `subject`, `body`, `links`, `auth` (`spf`/`dkim`/`dmarc` each `pass`/`fail`/`none`), `flag_tags`
  (warning signs that really apply, from the list in `game_logic.FLAG_OPTIONS`; empty for legitimate emails),
  `red_flags` and `explanation`. Optional: `reply_to`. Run `pytest`; it checks every question.
  Keep every domain on `.example` so no real site is ever involved.

## 5. How the detector works

Points are added for each warning sign found, then turned into a verdict: **0-2 Low Risk, 3-5 Suspicious, 6+ High Risk**.

| Area | Examples of what it checks |
|---|---|
| Sender | Display name sounds official but domain isn't; look-alike domain (`northfie1d`, `northfeld`); trusted name hidden as a subdomain; free-mail address; Reply-To mismatch |
| Language | Urgency, threats, requests for passwords / ID / bank details, gift cards or fees, generic greeting, too-good-to-be-true offers |
| URLs | Link text ≠ real destination; look-alike or punycode (`xn--`) domains; IP addresses; `@` tricks; URL shorteners; plain `http` |
| Authentication | Failed SPF, DKIM or DMARC checks (a *pass* adds nothing: attackers can pass with their own look-alike domain) |

Design rules: one urgent word or one unfamiliar sender is **not** enough to call something phishing, a
legitimate email that merely mentions the word "password" stays Low Risk, and a message with missing
information is shown as **Check incomplete**, never silently as Low Risk.
The detector is also **not assumed to be correct**: the game compares both you and the detector against the
known answer. (It deliberately misses email `H6`, a shared-document link from a compromised account.)

This is a teaching tool, not a production security product.

## 6. Connect to a real detection service (optional)

Set the environment variable `PHISHGUARD_API_URL` and the game will POST each email to your service
instead of using the built-in detector:

```powershell
$env:PHISHGUARD_API_URL = "http://localhost:5000/api/analyze"
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Request (JSON): `sender_name`, `sender_email`, `reply_to`, `subject`, `body`, `links`, `auth`.
Response (JSON): `{"verdict": "Low Risk" | "Suspicious" | "High Risk", "score": 0, "reasons": ["..."]}`.
If the service is down or replies oddly, the game shows **Check incomplete** instead of guessing.
Any backend language works (C#/ASP.NET Core, Python, Node, ...).

## 7. Ideas for next steps

- Persistent leaderboard in SQLite (the current profile is per computer)
- A before/after quiz to measure whether the game improves accuracy (use consenting students, different but
  equally hard email sets, and don't over-claim from a small trial)
- More levels, a timer mode, a larger question bank
- Deploy free on Streamlit Community Cloud by putting this folder on GitHub
