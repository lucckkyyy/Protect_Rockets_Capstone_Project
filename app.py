"""Aware Rockets - a phishing-awareness training game.

Run with:   streamlit run app.py
"""

from __future__ import annotations

import html

import streamlit as st

import api_client
import detector
import game_logic as gl
import stats as pstats

# ---- Branding: change these two lines to rename the game --------------------
APP_NAME = "Aware Rockets"
APP_TAGLINE = "Phishing Awareness Training"
# -----------------------------------------------------------------------------

st.set_page_config(page_title=APP_NAME, page_icon="🛡️", layout="wide")

NAVY, GOLD = "#0B1530", "#F5B700"
VERDICT_COLORS = {
    "Low Risk": "#2EA043", "Suspicious": "#E3A008", "High Risk": "#E5484D",
    "Check incomplete": "#8A94A6",
}
AUTH_COLORS = {"pass": "#2EA043", "fail": "#E5484D", "none": "#8A94A6"}

CSS = f"""
<style>
  .block-container {{ padding-top: 2rem; max-width: 1100px; }}
  .brand {{ font-size: 1.3rem; white-space: nowrap; font-weight: 800; color: {GOLD}; letter-spacing: .5px; }}
  .brand-sub {{ color: #9FB0D6; margin-top: -6px; margin-bottom: 8px; }}
  .hero {{ background: linear-gradient(135deg,#142252,#0B1530); border: 1px solid #243566;
          border-radius: 18px; padding: 42px 28px; text-align: center; margin-bottom: 18px; }}
  .hero h1 {{ margin: 0 0 8px 0; font-size: 2.2rem; }}
  .hero p {{ color: #B9C6E6; margin: 0; }}
  .stat {{ text-align: center; background:#111E42; border:1px solid #243566; border-radius:14px; padding:16px; }}
  .stat b {{ display:block; font-size:1.8rem; color:{GOLD}; }}
  .stat span {{ color:#9FB0D6; font-size:.85rem; }}
  .email {{ background:#fff; color:#1b2433; border-radius:12px; padding:0; overflow:hidden;
           box-shadow:0 6px 24px rgba(0,0,0,.35); margin: 8px 0 14px 0; }}
  .email-head {{ background:#EEF1F7; padding:14px 20px; border-bottom:1px solid #d9deea; }}
  .email-head .subj {{ font-size:1.15rem; font-weight:700; margin-bottom:6px; }}
  .email-head .from {{ font-size:.92rem; color:#4a566d; }}
  .email-body {{ padding:20px; white-space:pre-wrap; line-height:1.55; }}
  .email-link {{ padding:0 20px 18px 20px; }}
  .email-link span {{ color:#1a56db; text-decoration:underline; }}
  .pill {{ display:inline-block; padding:3px 12px; border-radius:999px; font-weight:700; font-size:.85rem; }}
  .vs {{ text-align:center; background:#111E42; border:1px solid #243566; border-radius:14px; padding:16px; }}
  .vs small {{ color:#9FB0D6; display:block; margin-top:6px; }}
  .level-tag {{ color:#9FB0D6; font-size:.85rem; text-transform:uppercase; letter-spacing:1px; }}
  .rank {{ background:#111E42; border:1px solid {GOLD}55; border-radius:14px; padding:14px 18px; margin-top:14px; }}
  .rank b {{ color:{GOLD}; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
def init_state() -> None:
    st.session_state.setdefault("screen", "home")
    st.session_state.setdefault("game", None)
    st.session_state.setdefault("detections", {})    # question id -> DetectionResult
    st.session_state.setdefault("recorded", False)   # has this game been added to the profile?
    st.session_state.setdefault("stats_before", None)
    st.session_state.setdefault("stats_after", None)


def start_game() -> None:
    st.session_state.game = gl.new_game()
    st.session_state.detections = {}
    st.session_state.recorded = False
    st.session_state.screen = "play"


def go_home() -> None:
    st.session_state.screen = "home"


def pill(verdict: str) -> str:
    color = VERDICT_COLORS.get(verdict, "#8A94A6")
    return (f'<span class="pill" style="background:{color}22;color:{color};'
            f'border:1px solid {color}">{html.escape(verdict)}</span>')


def auth_chip(name: str, value: str) -> str:
    color = AUTH_COLORS.get(value, "#8A94A6")
    return (f'<span class="pill" style="background:{color}22;color:{color};border:1px solid {color};'
            f'margin-right:8px">{name}: {html.escape(value.upper())}</span>')


def answer(choice: str) -> None:
    game: gl.GameState = st.session_state.game
    q = game.current
    flags = st.session_state.get(f"flags_{game.index}", [])
    det = api_client.detect(q)
    st.session_state.detections[q["id"]] = det
    game.submit(choice, det.verdict, flags)    # ignored automatically if already answered


def next_round() -> None:
    game: gl.GameState = st.session_state.game
    game.next_round()
    if game.finished:
        st.session_state.screen = "results"


# ---------------------------------------------------------------------------
# Screens
# ---------------------------------------------------------------------------
def sidebar() -> None:
    with st.sidebar:
        st.markdown(f'<div class="brand">🛡️ {html.escape(APP_NAME)}</div>'
                    f'<div class="brand-sub">{html.escape(APP_TAGLINE)}</div>', unsafe_allow_html=True)
        st.button("🏠 Home", on_click=go_home, use_container_width=True)
        profile = pstats.load_stats()
        st.caption(f"🎖️ Rank: **{pstats.rank_for(profile['xp'])}** · {profile['xp']} XP")
        game = st.session_state.game
        if game and st.session_state.screen != "home":
            st.divider()
            st.metric("Score", f"{game.score} / {game.max_points}")
            st.caption(f"Spotter bonus: +{game.bonus} · 🔥 Streak: {game.streak}")
            shown = min(game.index + 1, game.total_rounds)
            st.progress(len(game.results) / game.total_rounds,
                        text=f"Round {shown} of {game.total_rounds}")
        st.divider()
        if api_client.remote_url():
            st.caption("Detector: remote service")
        else:
            st.caption("Detector: built-in rule engine")
        st.caption("All emails are fictional. No real links are ever opened.")


def profile_panel() -> None:
    profile = pstats.load_stats()
    xp = profile["xp"]
    nxt = pstats.next_rank(xp)
    extra = f" · {nxt[1]} XP to <b>{nxt[0]}</b>" if nxt else " · top rank reached!"
    st.markdown(f'<div class="rank">🎖️ Your rank: <b>{pstats.rank_for(xp)}</b> · {xp} XP{extra}</div>',
                unsafe_allow_html=True)
    if profile["games_played"]:
        a, b, c, d = st.columns(4)
        a.metric("Games played", profile["games_played"])
        b.metric("Best score", profile["best_score"])
        c.metric("Lifetime accuracy", f"{pstats.lifetime_accuracy(profile):.0%}")
        d.metric("🔥 Streak (best)", f"{profile['current_streak']} ({profile['best_streak']})")


def home_screen() -> None:
    st.markdown(
        """<div class="hero"><div style="font-size:2.4rem">🎮</div>
        <h1>Can You Spot a Phishing Email?</h1>
        <p>Test your cybersecurity knowledge and defend your university inbox.</p></div>""",
        unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 1, 1])
    with mid:
        st.button("▶ Start Challenge", type="primary", on_click=start_game, use_container_width=True)

    c1, c2, c3 = st.columns(3)
    for col, big, small in ((c1, len(gl.ROUND_PLAN), "Rounds"),
                            (c2, len(gl.ROUND_PLAN) * gl.POINTS_PER_CORRECT, "Max points"),
                            (c3, 3, "Risk levels")):
        col.markdown(f'<div class="stat"><b>{big}</b><span>{small}</span></div>', unsafe_allow_html=True)

    profile_panel()

    st.subheader("How to play")
    st.markdown(
        "1. Read each email like a cybersecurity analyst: check the **sender**, the **wording**, the **links**, "
        "and the **email headers** (SPF / DKIM / DMARC) under *View email headers*.\n"
        "2. Optional: tick the **warning signs** you spot for up to "
        f"**+{gl.BONUS_MAX_PER_ROUND} bonus points** per round.\n"
        "3. Classify it as **Low Risk**, **Suspicious** or **High Risk**.\n"
        "4. See how the built-in **detector** judged it, and learn why.\n"
        f"5. Each correct answer earns **{gl.POINTS_PER_CORRECT} points**. Your XP builds your rank "
        "(Rookie → Analyst → Defender → Guardian) and your streak carries across games.")


def email_card(q: dict) -> None:
    esc = html.escape
    links_html = "".join(
        f'<div class="email-link"><span>{esc(l["text"])}</span></div>' for l in q["links"])
    st.markdown(
        f"""<div class="email">
        <div class="email-head">
          <div class="subj">{esc(q["subject"])}</div>
          <div class="from"><b>From:</b> {esc(q["sender_name"])} &lt;{esc(q["sender_email"])}&gt;</div>
        </div>
        <div class="email-body">{esc(q["body"])}</div>
        {links_html}
        </div>""", unsafe_allow_html=True)

    with st.expander("📨 View email headers (technical details)"):
        st.markdown(f"**From:** `{q['sender_email']}`")
        st.markdown(f"**Reply-To:** `{q.get('reply_to') or q['sender_email']}`")
        auth = q.get("auth", {})
        st.markdown("**Authentication:** " + "".join(
            auth_chip(k.upper(), auth.get(k, "none")) for k in ("spf", "dkim", "dmarc")),
            unsafe_allow_html=True)
        st.caption("SPF, DKIM and DMARC test whether the sending server is allowed to send for that domain. "
                   "A FAIL is a strong warning sign. A PASS only proves the email came from that domain, "
                   "so an attacker's own look-alike domain can pass too.")

    if q["links"]:
        with st.expander("🔍 Inspect links (real destinations)"):
            for l in q["links"]:
                st.write(f"Shown as: **{l['text']}**")
                st.code(l["url"], language=None)   # plain text, never a clickable link


def flags_summary(result: gl.RoundResult) -> None:
    if not result.correct:
        return
    label = gl.FLAG_OPTIONS
    if not result.flags_true:
        if result.flags_selected:
            st.warning("🚩 This email is legitimate, so there were no warning signs to find. "
                       "No spotter bonus this time.")
        else:
            st.success(f"🔎 Spotter bonus +{result.bonus}: you correctly saw no warning signs.")
        return
    parts = []
    if result.flags_hit:
        parts.append("✅ Spotted: " + ", ".join(label[f] for f in result.flags_hit))
    if result.flags_missed:
        parts.append("⚠️ Missed: " + ", ".join(label[f] for f in result.flags_missed))
    if result.flags_wrong:
        parts.append("❌ Not actually present: " + ", ".join(label[f] for f in result.flags_wrong))
    st.markdown(f"**🔎 Spotter bonus: +{result.bonus} / {gl.BONUS_MAX_PER_ROUND}**  \n" + "  \n".join(parts))


def feedback(q: dict, game: gl.GameState) -> None:
    result = game.results[game.index]
    det: detector.DetectionResult = st.session_state.detections[q["id"]]

    if result.correct:
        st.success(f"✅ Correct! +{result.points} points")
    else:
        st.error(f"❌ Not quite. The correct answer was **{q['answer']}**.")

    a, b, c = st.columns(3)
    a.markdown(f'<div class="vs">{pill(result.player)}<small>Your decision</small></div>', unsafe_allow_html=True)
    b.markdown(f'<div class="vs">{pill(det.verdict)}<small>Detector decision</small></div>', unsafe_allow_html=True)
    c.markdown(f'<div class="vs">{pill(q["answer"])}<small>Correct answer</small></div>', unsafe_allow_html=True)

    if not det.complete:
        st.warning(f"Detector check incomplete: {det.message}")
    elif det.verdict == q["answer"] and not result.correct:
        st.info("The detector got this one right.")
    elif det.verdict != q["answer"] and result.correct:
        st.info("You beat the detector on this one. Rule-based tools can miss subtle cases.")
    elif det.verdict != q["answer"]:
        st.info("Both you and the detector missed this one.")

    st.write("")
    flags_summary(result)

    st.markdown("**Why?**")
    st.write(q["explanation"])
    if q["red_flags"]:
        st.markdown("**Warning signs in this email:**")
        for flag in q["red_flags"]:
            st.markdown(f"- {flag}")
    else:
        st.markdown("**Warning signs:** none, this one is legitimate.")

    if det.findings:
        with st.expander(f"🛡️ What the detector noticed (score {det.score})"):
            for f in det.findings:
                pts = f" (+{f.points})" if f.points else ""
                st.markdown(f"- **{f.label}**{pts}: {f.detail}" if f.detail else f"- **{f.label}**{pts}")

    last = game.index == game.total_rounds - 1
    st.button("🏁 See results" if last else "Next email ➜", type="primary", on_click=next_round)


def play_screen() -> None:
    game: gl.GameState | None = st.session_state.game
    if game is None or game.finished:
        st.session_state.screen = "home" if game is None else "results"
        st.rerun()
    q = game.current
    st.markdown(f'<div class="level-tag">Round {game.index + 1} of {game.total_rounds} · '
                f'{q["level"].title()}</div>', unsafe_allow_html=True)
    st.subheader("Examine this email")
    email_card(q)

    if not game.answered_current:
        st.multiselect(
            f"🔎 Optional: which warning signs do you see? (up to +{gl.BONUS_MAX_PER_ROUND} bonus points)",
            options=list(gl.FLAG_OPTIONS), format_func=gl.FLAG_OPTIONS.get,
            key=f"flags_{game.index}", placeholder="Pick any that apply, or leave empty")
        st.write("**How risky is this email?**")
        cols = st.columns(3)
        for col, choice, icon in zip(cols, gl.CHOICES, ("🟢", "🟠", "🔴")):
            col.button(f"{icon} {choice}", key=f"choice_{game.index}_{choice}",
                       on_click=answer, args=(choice,), use_container_width=True)
    else:
        feedback(q, game)


def record_profile(game: gl.GameState) -> None:
    """Add the finished game to the lifetime profile - exactly once per game."""
    if st.session_state.recorded:
        return
    before = pstats.load_stats()
    after = pstats.record_game(before, game)
    pstats.save_stats(after)
    st.session_state.stats_before, st.session_state.stats_after = before, after
    st.session_state.recorded = True


def results_screen() -> None:
    game: gl.GameState | None = st.session_state.game
    if game is None:
        st.session_state.screen = "home"
        st.rerun()
    record_profile(game)
    st.header("🏆 Mission Complete!")
    a, b, c, d = st.columns(4)
    for col, big, small in ((a, game.score, "Points"), (b, f"+{game.bonus}", "Spotter bonus"),
                            (c, f"{game.accuracy:.0%}", "Accuracy"),
                            (d, f"{game.correct_count}/{game.total_rounds}", "Correct")):
        col.markdown(f'<div class="stat"><b>{big}</b><span>{small}</span></div>', unsafe_allow_html=True)
    st.write("")
    st.progress(game.accuracy, text="Email classification accuracy")

    det_correct = sum(r.detector_correct for r in game.results)
    st.caption(f"You: {game.correct_count}/{game.total_rounds} correct · "
               f"Detector: {det_correct}/{game.total_rounds} correct")

    before, after = st.session_state.stats_before, st.session_state.stats_after
    if before and after:
        old_rank, new_rank = pstats.rank_for(before["xp"]), pstats.rank_for(after["xp"])
        msg = f"🎖️ +{game.total_points} XP · Rank: **{new_rank}** ({after['xp']} XP) · " \
              f"🔥 Streak: {after['current_streak']} (best {after['best_streak']})"
        if new_rank != old_rank:
            msg = f"🎉 **Rank up! {old_rank} → {new_rank}**  \n" + msg
        st.success(msg)

    st.info(f"💡 **Learning recommendation:** {game.learning_tip()}")

    missed = [r for r in game.results if not r.correct]
    if missed:
        st.subheader("Threats and emails you missed")
        bank = {q["id"]: q for q in game.rounds}
        for r in missed:
            q = bank[r.question_id]
            with st.expander(f"{q['subject']}  (you said {r.player}, correct: {r.correct_answer})"):
                st.write(q["explanation"])

    d1, d2 = st.columns(2)
    d1.download_button("⬇ Download results (CSV)", game.to_csv(), "aware_rockets_results.csv",
                       "text/csv", use_container_width=True)
    d2.button("🔁 Play again", type="primary", on_click=start_game, use_container_width=True)
    if game.accuracy == 1.0:
        st.balloons()


def main() -> None:
    init_state()
    screen = st.session_state.screen
    if screen == "results" and st.session_state.game is not None:
        record_profile(st.session_state.game)    # before the sidebar so its rank is up to date
    sidebar()
    if screen == "play":
        play_screen()
    elif screen == "results":
        results_screen()
    else:
        home_screen()


main()
