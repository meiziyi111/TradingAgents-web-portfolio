"""Presentation helpers for the Streamlit research dashboard.

The module deliberately contains no business logic.  It keeps the dashboard's
visual system consistent while the graph, portfolio controls, and report
parsing remain independently testable.
"""

from __future__ import annotations

from html import escape
from typing import Iterable, Mapping, Sequence

import streamlit as st


APP_CSS = r"""
<style>
:root {
  --ta-bg: #07111f;
  --ta-panel: rgba(15, 29, 49, .78);
  --ta-panel-strong: rgba(13, 27, 46, .96);
  --ta-border: rgba(148, 178, 214, .15);
  --ta-border-bright: rgba(103, 232, 249, .30);
  --ta-text: #f2f7ff;
  --ta-muted: #8fa3bd;
  --ta-cyan: #55e6d8;
  --ta-blue: #5ba8ff;
  --ta-violet: #9a7cff;
  --ta-green: #50e3a4;
  --ta-red: #ff6f83;
  --ta-amber: #ffca6b;
  --ta-shadow: 0 20px 60px rgba(0, 0, 0, .28);
}

html { scroll-behavior: smooth; }

[data-testid="stAppViewContainer"] {
  color: var(--ta-text);
  background:
    radial-gradient(circle at 86% -4%, rgba(91, 168, 255, .15), transparent 31rem),
    radial-gradient(circle at 12% 4%, rgba(154, 124, 255, .12), transparent 29rem),
    linear-gradient(145deg, #07111f 0%, #091523 46%, #06101c 100%);
}

[data-testid="stAppViewContainer"]::before {
  content: "";
  position: fixed;
  inset: 0;
  pointer-events: none;
  opacity: .18;
  background-image:
    linear-gradient(rgba(121, 166, 209, .07) 1px, transparent 1px),
    linear-gradient(90deg, rgba(121, 166, 209, .07) 1px, transparent 1px);
  background-size: 42px 42px;
  mask-image: linear-gradient(to bottom, black, transparent 72%);
}

[data-testid="stHeader"] { background: transparent; }
#MainMenu, footer { visibility: hidden; }
[data-testid="stDecoration"] { display: none; }
[data-testid="stAppDeployButton"] { display: none; }

.stMainBlockContainer {
  max-width: 1440px;
  padding: 2.25rem 2.4rem 4rem;
}

[data-testid="stSidebar"] {
  background:
    radial-gradient(circle at 25% 0%, rgba(84, 230, 216, .10), transparent 18rem),
    linear-gradient(180deg, rgba(8, 20, 34, .99), rgba(7, 16, 29, .99));
  border-right: 1px solid var(--ta-border);
}

[data-testid="stSidebar"] > div:first-child { padding-top: 1.15rem; }

p, li, [data-testid="stMarkdownContainer"] { color: #d6e1ef; }
a { color: #72d8ff !important; }
hr { border-color: var(--ta-border) !important; }

/* Brand */
.ta-brand {
  display: flex;
  gap: .85rem;
  align-items: center;
  padding: .55rem .2rem 1.1rem;
}
.ta-logo {
  position: relative;
  display: grid;
  place-items: center;
  width: 2.7rem;
  height: 2.7rem;
  border-radius: .86rem;
  color: #04121a;
  font-weight: 900;
  letter-spacing: -.06em;
  background: linear-gradient(135deg, #72f4dc, #6eb6ff 55%, #b395ff);
  box-shadow: 0 0 30px rgba(84, 230, 216, .24);
  transform: rotate(-3deg);
}
.ta-logo::after {
  content: "";
  position: absolute;
  width: .46rem;
  height: .46rem;
  right: -.12rem;
  top: -.12rem;
  border-radius: 50%;
  background: var(--ta-green);
  border: 3px solid #081523;
  animation: ta-pulse 2.4s ease-in-out infinite;
}
.ta-brand-name { color: #f5f9ff; font-size: 1.04rem; font-weight: 780; letter-spacing: -.02em; }
.ta-brand-sub { color: var(--ta-muted); font-size: .69rem; letter-spacing: .09em; text-transform: uppercase; margin-top: .08rem; }
.ta-side-label {
  margin: 1.15rem 0 .48rem;
  color: #7187a2;
  font-size: .67rem;
  font-weight: 760;
  letter-spacing: .13em;
  text-transform: uppercase;
}
.ta-demo-note {
  padding: .78rem .86rem;
  margin: .25rem 0 .72rem;
  border: 1px solid rgba(255, 202, 107, .18);
  border-radius: .85rem;
  color: #dbc89f;
  font-size: .72rem;
  line-height: 1.55;
  background: rgba(255, 202, 107, .055);
}
.ta-system-note {
  display: flex;
  align-items: center;
  gap: .5rem;
  color: #7187a2;
  font-size: .68rem;
  margin: 1.4rem 0 .5rem;
}
.ta-system-dot { width: .43rem; height: .43rem; border-radius: 50%; background: var(--ta-green); box-shadow: 0 0 12px rgba(80, 227, 164, .75); }

/* Streamlit inputs */
[data-testid="stSidebar"] [data-testid="stForm"] {
  border: 1px solid var(--ta-border);
  border-radius: 1.15rem;
  padding: .95rem .9rem 1rem;
  background: rgba(15, 29, 49, .58);
  box-shadow: inset 0 1px rgba(255, 255, 255, .025);
}
div[data-baseweb="input"] > div,
div[data-baseweb="select"] > div,
[data-testid="stNumberInput"] > div > div,
[data-testid="stDateInput"] > div > div {
  color: var(--ta-text) !important;
  background: rgba(5, 14, 26, .74) !important;
  border-color: var(--ta-border) !important;
  border-radius: .75rem !important;
}
label, [data-testid="stWidgetLabel"] p { color: #aebed1 !important; font-size: .76rem !important; }
[data-testid="stSlider"] [role="slider"] { background: #75eadb !important; }

.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] button {
  min-height: 2.65rem;
  border: 1px solid var(--ta-border-bright);
  border-radius: .82rem;
  color: #ecf7ff;
  font-weight: 720;
  background: linear-gradient(135deg, rgba(41, 97, 129, .88), rgba(71, 72, 138, .84));
  box-shadow: 0 10px 28px rgba(20, 61, 98, .20), inset 0 1px rgba(255, 255, 255, .1);
  transition: transform .2s ease, border-color .2s ease, box-shadow .2s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover, [data-testid="stFormSubmitButton"] button:hover {
  color: white;
  border-color: rgba(110, 239, 222, .58);
  transform: translateY(-2px);
  box-shadow: 0 15px 34px rgba(36, 117, 143, .26), 0 0 0 1px rgba(84, 230, 216, .08);
}

/* Hero */
.ta-hero {
  position: relative;
  overflow: hidden;
  min-height: 15rem;
  padding: 2.25rem 2.35rem;
  margin: .15rem 0 1.2rem;
  border: 1px solid var(--ta-border);
  border-radius: 1.55rem;
  background:
    radial-gradient(circle at 88% 18%, rgba(85, 230, 216, .12), transparent 17rem),
    radial-gradient(circle at 70% 110%, rgba(154, 124, 255, .18), transparent 22rem),
    linear-gradient(135deg, rgba(16, 36, 59, .93), rgba(10, 24, 42, .94));
  box-shadow: var(--ta-shadow), inset 0 1px rgba(255, 255, 255, .035);
}
.ta-hero::before {
  content: "";
  position: absolute;
  width: 24rem;
  height: 24rem;
  right: -6rem;
  top: -10rem;
  border: 1px solid rgba(111, 220, 255, .13);
  border-radius: 50%;
  box-shadow: 0 0 0 3rem rgba(111, 220, 255, .018), 0 0 0 7rem rgba(154, 124, 255, .018);
  animation: ta-float 8s ease-in-out infinite;
}
.ta-hero-grid {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: end;
  gap: 2rem;
}
.ta-eyebrow {
  display: flex;
  align-items: center;
  gap: .55rem;
  margin-bottom: .9rem;
  color: #7fc6d8;
  font-size: .69rem;
  font-weight: 760;
  letter-spacing: .14em;
  text-transform: uppercase;
}
.ta-eyebrow::before { content: ""; width: 1.55rem; height: 1px; background: linear-gradient(90deg, var(--ta-cyan), transparent); }
.ta-hero h1 {
  margin: 0;
  color: #f7fbff;
  font-size: clamp(2.25rem, 5vw, 4.25rem);
  line-height: .98;
  letter-spacing: -.055em;
}
.ta-hero h1 span { color: #8ca3bd; font-weight: 420; }
.ta-hero-copy { max-width: 48rem; margin: 1.05rem 0 0; color: #9eb0c5; font-size: .93rem; line-height: 1.7; }
.ta-meta-row { display: flex; gap: .55rem; flex-wrap: wrap; margin-top: 1.25rem; }
.ta-chip {
  display: inline-flex;
  align-items: center;
  gap: .4rem;
  padding: .38rem .65rem;
  border: 1px solid var(--ta-border);
  border-radius: 99px;
  color: #aebfd2;
  font-size: .69rem;
  background: rgba(3, 12, 22, .34);
}
.ta-signal-wrap { text-align: right; min-width: 12.5rem; }
.ta-signal-label { margin-bottom: .55rem; color: #7187a2; font-size: .64rem; letter-spacing: .13em; text-transform: uppercase; }
.ta-signal {
  display: inline-flex;
  align-items: center;
  gap: .58rem;
  padding: .75rem 1rem;
  border: 1px solid;
  border-radius: 1rem;
  font-size: 1.3rem;
  font-weight: 850;
  letter-spacing: .03em;
  backdrop-filter: blur(12px);
}
.ta-signal::before { content: ""; width: .58rem; height: .58rem; border-radius: 50%; background: currentColor; box-shadow: 0 0 17px currentColor; }
.ta-signal-buy { color: var(--ta-green); border-color: rgba(80,227,164,.30); background: rgba(80,227,164,.09); }
.ta-signal-sell { color: var(--ta-red); border-color: rgba(255,111,131,.30); background: rgba(255,111,131,.09); }
.ta-signal-hold { color: var(--ta-amber); border-color: rgba(255,202,107,.30); background: rgba(255,202,107,.09); }
.ta-signal-neutral { color: #a8bbd1; border-color: rgba(168,187,209,.26); background: rgba(168,187,209,.07); }

/* Metrics */
.ta-metric-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: .8rem;
  margin: 0 0 1.25rem;
}
.ta-metric {
  position: relative;
  overflow: hidden;
  min-height: 7.25rem;
  padding: 1.05rem 1.1rem;
  border: 1px solid var(--ta-border);
  border-radius: 1.05rem;
  background: linear-gradient(145deg, rgba(17, 34, 56, .80), rgba(11, 24, 41, .78));
  box-shadow: 0 12px 34px rgba(0, 0, 0, .15), inset 0 1px rgba(255,255,255,.025);
  transition: transform .22s ease, border-color .22s ease, background .22s ease;
}
.ta-metric:hover { transform: translateY(-4px); border-color: rgba(103,232,249,.27); background: linear-gradient(145deg, rgba(20, 42, 67, .88), rgba(12, 28, 47, .84)); }
.ta-metric::after { content: ""; position: absolute; inset: auto -25% -80% 30%; height: 6rem; border-radius: 50%; background: var(--metric-glow, rgba(91,168,255,.13)); filter: blur(20px); }
.ta-metric-label { color: #7f94ae; font-size: .68rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
.ta-metric-value { position: relative; z-index: 1; margin-top: .7rem; color: #f2f7ff; font-size: clamp(1.08rem, 2vw, 1.55rem); font-weight: 820; letter-spacing: -.025em; overflow-wrap: anywhere; }
.ta-metric-hint { position: relative; z-index: 1; margin-top: .35rem; color: #6f859f; font-size: .64rem; }
.ta-tone-green { --metric-glow: rgba(80,227,164,.20); }
.ta-tone-red { --metric-glow: rgba(255,111,131,.18); }
.ta-tone-amber { --metric-glow: rgba(255,202,107,.17); }
.ta-tone-violet { --metric-glow: rgba(154,124,255,.18); }

/* Workflow */
.ta-section-head { display: flex; justify-content: space-between; align-items: end; gap: 1rem; margin: 1.8rem 0 .82rem; }
.ta-section-kicker { color: #6fd8d0; font-size: .67rem; font-weight: 760; letter-spacing: .13em; text-transform: uppercase; }
.ta-section-title { margin-top: .2rem; color: #f1f6fd; font-size: 1.2rem; font-weight: 760; letter-spacing: -.02em; }
.ta-section-note { max-width: 34rem; color: #7187a2; font-size: .72rem; text-align: right; line-height: 1.5; }
.ta-stage-rail {
  position: relative;
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: .6rem;
  margin-bottom: 1.2rem;
}
.ta-stage {
  position: relative;
  z-index: 1;
  min-height: 7.1rem;
  padding: .88rem .72rem;
  border: 1px solid var(--ta-border);
  border-radius: .95rem;
  background: rgba(12, 27, 46, .68);
  transition: transform .2s ease, border-color .2s ease;
}
.ta-stage:hover { transform: translateY(-3px); border-color: rgba(91,168,255,.28); }
.ta-stage-index { color: #526981; font-size: .61rem; font-weight: 780; letter-spacing: .1em; }
.ta-stage-icon { margin: .55rem 0 .42rem; font-size: 1.18rem; filter: saturate(.9); }
.ta-stage-name { color: #c7d4e3; font-size: .72rem; font-weight: 690; line-height: 1.3; }
.ta-stage-status { position: absolute; right: .65rem; top: .65rem; width: .43rem; height: .43rem; border-radius: 50%; background: #3c526b; }
.ta-stage.done { border-color: rgba(80,227,164,.18); background: linear-gradient(145deg, rgba(80,227,164,.075), rgba(12,27,46,.72)); }
.ta-stage.done .ta-stage-status { background: var(--ta-green); box-shadow: 0 0 11px rgba(80,227,164,.68); }
.ta-stage.active { border-color: rgba(91,168,255,.40); background: linear-gradient(145deg, rgba(91,168,255,.12), rgba(154,124,255,.07)); box-shadow: 0 0 24px rgba(91,168,255,.08); }
.ta-stage.active .ta-stage-status { background: var(--ta-blue); box-shadow: 0 0 12px rgba(91,168,255,.76); animation: ta-pulse 1.55s ease-in-out infinite; }

/* Running state */
.ta-running-card {
  position: relative;
  overflow: hidden;
  padding: 2rem;
  margin: .1rem 0 1rem;
  border: 1px solid rgba(91,168,255,.23);
  border-radius: 1.45rem;
  background: linear-gradient(135deg, rgba(15,36,60,.95), rgba(11,24,43,.94));
  box-shadow: var(--ta-shadow);
}
.ta-running-card::after {
  content: "";
  position: absolute;
  left: -30%; right: -30%; bottom: 0;
  height: 2px;
  background: linear-gradient(90deg, transparent, var(--ta-cyan), var(--ta-violet), transparent);
  animation: ta-scan 2.8s linear infinite;
}
.ta-running-top { display: flex; align-items: center; justify-content: space-between; gap: 1rem; }
.ta-running-kicker { color: #76dcd5; font-size: .68rem; font-weight: 760; letter-spacing: .14em; text-transform: uppercase; }
.ta-running-title { margin-top: .4rem; color: #f5f9ff; font-size: clamp(1.7rem, 4vw, 2.65rem); font-weight: 790; letter-spacing: -.045em; }
.ta-running-copy { max-width: 43rem; margin-top: .55rem; color: #8fa4bd; font-size: .8rem; line-height: 1.65; }
.ta-orbit {
  position: relative;
  flex: 0 0 5.7rem;
  width: 5.7rem;
  height: 5.7rem;
  border: 1px solid rgba(91,168,255,.28);
  border-radius: 50%;
  animation: ta-spin 8s linear infinite;
}
.ta-orbit::before, .ta-orbit::after { content: ""; position: absolute; border-radius: 50%; }
.ta-orbit::before { inset: 1rem; border: 1px solid rgba(154,124,255,.35); }
.ta-orbit::after { width: .65rem; height: .65rem; left: -.2rem; top: 2.4rem; background: var(--ta-cyan); box-shadow: 0 0 18px var(--ta-cyan); }
.ta-progress-track { height: .48rem; margin: 1.25rem 0 .5rem; overflow: hidden; border-radius: 99px; background: rgba(2,9,17,.6); }
.ta-progress-fill { height: 100%; border-radius: 99px; background: linear-gradient(90deg, var(--ta-cyan), var(--ta-blue), var(--ta-violet)); box-shadow: 0 0 16px rgba(91,168,255,.38); transition: width .5s ease; }
.ta-progress-meta { display: flex; justify-content: space-between; color: #7187a2; font-size: .68rem; }
.ta-terminal {
  padding: 1rem 1.1rem;
  border: 1px solid var(--ta-border);
  border-radius: 1rem;
  background: rgba(3, 10, 19, .76);
  box-shadow: inset 0 1px rgba(255,255,255,.02);
}
.ta-terminal-head { display: flex; align-items: center; gap: .36rem; margin-bottom: .75rem; color: #7187a2; font-size: .66rem; letter-spacing: .08em; text-transform: uppercase; }
.ta-terminal-dot { width: .45rem; height: .45rem; border-radius: 50%; background: #31465d; }
.ta-terminal-dot.live { background: var(--ta-green); box-shadow: 0 0 9px rgba(80,227,164,.65); }
.ta-log-line { display: grid; grid-template-columns: 2.3rem 1fr; gap: .4rem; padding: .28rem 0; color: #a9bbce; font: .72rem/1.45 ui-monospace, SFMono-Regular, Consolas, monospace; border-bottom: 1px solid rgba(148,178,214,.055); }
.ta-log-line:last-child { border: 0; }
.ta-log-n { color: #456077; user-select: none; }

/* Content surfaces */
[data-testid="stExpander"] {
  overflow: hidden;
  border: 1px solid var(--ta-border) !important;
  border-radius: 1rem !important;
  background: rgba(12, 27, 46, .65) !important;
  box-shadow: 0 10px 30px rgba(0,0,0,.10);
}
[data-testid="stExpander"] summary { padding: .25rem .35rem; }
[data-testid="stExpander"] summary:hover { color: var(--ta-cyan); }

.stTabs [data-baseweb="tab-list"] {
  gap: .35rem;
  padding: .32rem;
  border: 1px solid var(--ta-border);
  border-radius: .9rem;
  background: rgba(8, 19, 33, .74);
}
.stTabs [data-baseweb="tab"] {
  min-height: 2.5rem;
  padding: .5rem .9rem;
  border-radius: .65rem;
  color: #8499b2;
  font-size: .78rem;
}
.stTabs [aria-selected="true"] { color: #eff8ff !important; background: linear-gradient(135deg, rgba(72,139,175,.25), rgba(91,86,166,.20)); }
.stTabs [data-baseweb="tab-highlight"] { display: none; }
.stTabs [data-baseweb="tab-panel"] { padding-top: 1rem; }

[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3 { color: #edf5ff; letter-spacing: -.02em; }
[data-testid="stMarkdownContainer"] h1 { font-size: 1.65rem; }
[data-testid="stMarkdownContainer"] h2 { margin-top: 1.4rem; font-size: 1.3rem; }
[data-testid="stMarkdownContainer"] h3 { margin-top: 1.2rem; font-size: 1.08rem; }
[data-testid="stMarkdownContainer"] blockquote { border-left-color: var(--ta-cyan); background: rgba(85,230,216,.045); padding: .7rem 1rem; border-radius: 0 .7rem .7rem 0; }
[data-testid="stMarkdownContainer"] code { color: #87eadf; background: rgba(1,10,19,.55); }
[data-testid="stMarkdownContainer"] table { width: 100%; overflow: hidden; border-collapse: separate; border-spacing: 0; border: 1px solid var(--ta-border); border-radius: .85rem; }
[data-testid="stMarkdownContainer"] th { color: #b8cadc; background: rgba(44,69,96,.38); }
[data-testid="stMarkdownContainer"] td, [data-testid="stMarkdownContainer"] th { padding: .55rem .65rem; border-color: rgba(148,178,214,.10); }

.ta-agent-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .62rem; margin: .4rem 0 .8rem; }
.ta-agent {
  padding: .82rem .86rem;
  border: 1px solid var(--ta-border);
  border-radius: .82rem;
  background: rgba(7, 18, 32, .55);
}
.ta-agent-index { color: #617994; font-size: .61rem; font-weight: 760; letter-spacing: .09em; }
.ta-agent-name { margin-top: .3rem; color: #dce8f5; font-size: .76rem; font-weight: 700; }
.ta-agent-role { margin-top: .16rem; color: #7187a2; font-size: .66rem; }

.ta-empty {
  position: relative;
  overflow: hidden;
  display: grid;
  place-items: center;
  min-height: 31rem;
  padding: 3rem;
  border: 1px solid var(--ta-border);
  border-radius: 1.5rem;
  text-align: center;
  background: radial-gradient(circle at 50% 30%, rgba(91,168,255,.13), transparent 17rem), rgba(10,24,42,.68);
  box-shadow: var(--ta-shadow);
}
.ta-empty-mark { display: grid; place-items: center; width: 5rem; height: 5rem; margin: 0 auto 1.2rem; border: 1px solid rgba(84,230,216,.30); border-radius: 1.45rem; color: var(--ta-cyan); font-size: 1.7rem; background: rgba(84,230,216,.07); box-shadow: 0 0 50px rgba(84,230,216,.10); animation: ta-float 5s ease-in-out infinite; }
.ta-empty h2 { margin: 0; color: #f1f7ff; font-size: 1.65rem; letter-spacing: -.035em; }
.ta-empty p { max-width: 31rem; margin: .75rem auto 0; color: #8298b1; line-height: 1.7; }

.ta-state-card { padding: 1.4rem 1.5rem; border: 1px solid var(--ta-border); border-radius: 1.15rem; background: rgba(13,29,49,.75); }
.ta-state-card.success { border-color: rgba(80,227,164,.25); background: linear-gradient(135deg, rgba(80,227,164,.08), rgba(13,29,49,.78)); }
.ta-state-card.error { border-color: rgba(255,111,131,.25); background: linear-gradient(135deg, rgba(255,111,131,.08), rgba(13,29,49,.78)); }
.ta-state-title { color: #f0f7ff; font-size: 1.35rem; font-weight: 780; }
.ta-state-copy { margin-top: .35rem; color: #8298b1; font-size: .78rem; }
.ta-legal { margin: 2rem 0 .5rem; color: #536a83; font-size: .63rem; text-align: center; line-height: 1.6; }

/* V2 — cinematic neural-market command deck */
[data-testid="stAppViewContainer"] {
  background:
    radial-gradient(circle at 82% 8%, rgba(255, 41, 155, .10), transparent 30rem),
    radial-gradient(circle at 22% 22%, rgba(0, 245, 212, .10), transparent 34rem),
    linear-gradient(145deg, #010407 0%, #030a10 45%, #02070d 100%);
}
[data-testid="stAppViewContainer"]::before {
  opacity: .36;
  background-image:
    linear-gradient(rgba(0, 245, 212, .065) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 245, 212, .065) 1px, transparent 1px),
    linear-gradient(rgba(255, 60, 172, .025) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 60, 172, .025) 1px, transparent 1px);
  background-size: 44px 44px, 44px 44px, 176px 176px, 176px 176px;
  mask-image: linear-gradient(to bottom, black 0%, rgba(0,0,0,.65) 56%, transparent 96%);
  animation: ta-gridshift 22s linear infinite;
}
[data-testid="stAppViewContainer"]::after {
  content: "";
  position: fixed;
  z-index: 20;
  inset: 0;
  pointer-events: none;
  opacity: .16;
  background: repeating-linear-gradient(0deg, transparent 0 3px, rgba(183, 239, 255, .025) 3px 4px);
}

[data-testid="stSidebar"] {
  background:
    linear-gradient(180deg, rgba(2, 10, 16, .99), rgba(2, 7, 12, .99)),
    repeating-linear-gradient(0deg, transparent 0 24px, rgba(0,245,212,.04) 24px 25px);
  border-right-color: rgba(0, 245, 212, .22);
  box-shadow: 14px 0 60px rgba(0,0,0,.34);
}
.ta-logo {
  width: 3rem;
  height: 3rem;
  border-radius: .18rem;
  clip-path: polygon(20% 0, 100% 0, 100% 80%, 80% 100%, 0 100%, 0 20%);
  color: #00120f;
  background: linear-gradient(135deg, #00f5d4, #52a8ff 58%, #ff3cac);
  box-shadow: 0 0 18px rgba(0,245,212,.35), 0 0 44px rgba(255,60,172,.14);
}
.ta-brand-name { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; letter-spacing: -.04em; }
.ta-brand-sub, .ta-side-label { color: #5b8290; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }
[data-testid="stSidebar"] [data-testid="stForm"] {
  border-color: rgba(0,245,212,.16);
  border-radius: .22rem;
  background: linear-gradient(145deg, rgba(4,17,25,.88), rgba(3,10,17,.92));
  box-shadow: inset 3px 0 rgba(0,245,212,.08), 0 20px 45px rgba(0,0,0,.20);
}
.ta-demo-note { border-radius: .15rem; border-left: 2px solid #ffbf56; background: rgba(255,191,86,.045); }
div[data-baseweb="input"] > div,
div[data-baseweb="select"] > div,
[data-testid="stNumberInput"] > div > div,
[data-testid="stDateInput"] > div > div { border-radius: .12rem !important; }
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] button {
  position: relative;
  border-radius: .12rem;
  border-color: rgba(0,245,212,.42);
  color: #dffffa;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  letter-spacing: .025em;
  background: linear-gradient(100deg, rgba(0,245,212,.13), rgba(82,168,255,.12) 55%, rgba(255,60,172,.11));
  box-shadow: inset 0 0 22px rgba(0,245,212,.04), 0 0 20px rgba(0,245,212,.05);
}

.ta-hero {
  min-height: 28.5rem;
  padding: 1.15rem 2.5rem 2.45rem;
  border-radius: 0;
  border-color: rgba(0, 245, 212, .24);
  clip-path: polygon(0 0, calc(100% - 28px) 0, 100% 28px, 100% 100%, 28px 100%, 0 calc(100% - 28px));
  background:
    linear-gradient(90deg, rgba(0,245,212,.055) 1px, transparent 1px),
    linear-gradient(rgba(0,245,212,.04) 1px, transparent 1px),
    radial-gradient(circle at 79% 52%, rgba(0,245,212,.105), transparent 20rem),
    radial-gradient(circle at 95% 20%, rgba(255,60,172,.13), transparent 24rem),
    linear-gradient(120deg, rgba(4,17,27,.98), rgba(3,11,20,.96));
  background-size: 58px 58px, 58px 58px, auto, auto, auto;
  box-shadow: 0 35px 90px rgba(0,0,0,.52), inset 0 0 70px rgba(0,245,212,.025);
}
.ta-hero::before {
  width: 33rem;
  height: 33rem;
  right: -3rem;
  top: -3rem;
  border: 1px solid rgba(0,245,212,.11);
  box-shadow: 0 0 0 4rem rgba(0,245,212,.012), 0 0 0 8rem rgba(255,60,172,.012);
  animation: ta-spin 45s linear infinite;
}
.ta-hero::after {
  content: "";
  position: absolute;
  z-index: 0;
  left: -20%;
  right: -20%;
  top: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, #00f5d4, #52a8ff, #ff3cac, transparent);
  box-shadow: 0 0 24px rgba(0,245,212,.75);
  animation: ta-vertical-scan 5.5s ease-in-out infinite;
}
.ta-hero-topline {
  position: relative;
  z-index: 2;
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: 0 -1.2rem 2rem;
  padding: .55rem 1rem;
  border-bottom: 1px solid rgba(0,245,212,.12);
  color: #4d8290;
  font: 680 .62rem/1 ui-monospace, SFMono-Regular, Consolas, monospace;
  letter-spacing: .13em;
}
.ta-live-lock { color: #00f5d4; text-shadow: 0 0 12px rgba(0,245,212,.55); }
.ta-hero-grid { grid-template-columns: minmax(0, 1fr) minmax(19rem, 25rem); align-items: center; gap: 2.8rem; }
.ta-eyebrow { color: #00f5d4; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; text-shadow: 0 0 15px rgba(0,245,212,.4); }
.ta-hero h1 {
  position: relative;
  width: fit-content;
  color: #efffff;
  font-family: "Arial Narrow", "Segoe UI Variable", "Microsoft YaHei UI", sans-serif;
  font-size: clamp(4.6rem, 9vw, 8.6rem);
  font-weight: 920;
  line-height: .8;
  letter-spacing: -.085em;
  text-transform: uppercase;
  text-shadow: 0 0 10px rgba(0,245,212,.2), 0 0 45px rgba(82,168,255,.16);
}
.ta-hero h1::after {
  content: attr(data-symbol);
  position: absolute;
  inset: 0;
  color: #ff3cac;
  opacity: .28;
  clip-path: inset(42% 0 37% 0);
  transform: translateX(3px);
  animation: ta-glitch 4.8s steps(1,end) infinite;
}
.ta-hero-cn { margin-top: 1.25rem; color: #bad0db; font-size: 1.08rem; font-weight: 640; letter-spacing: .22em; }
.ta-hero-copy { max-width: 42rem; color: #7995a3; }
.ta-chip {
  border-radius: .12rem;
  border-color: rgba(0,245,212,.18);
  color: #698b98;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  background: rgba(0,245,212,.025);
}
.ta-chip b { color: #00d9c0; font-size: .61rem; letter-spacing: .08em; }

.ta-core { position: relative; width: 22rem; height: 22rem; margin: auto; filter: drop-shadow(0 0 28px rgba(0,245,212,.10)); }
.ta-core::before, .ta-core::after { content: ""; position: absolute; inset: 1.3rem; border: 1px dashed rgba(0,245,212,.15); border-radius: 50%; }
.ta-core::after { inset: 4.4rem; border-style: solid; border-color: rgba(255,60,172,.18); box-shadow: inset 0 0 28px rgba(255,60,172,.04); }
.ta-core-ring { position: absolute; border-radius: 50%; }
.ta-core-ring-a { inset: .15rem; background: conic-gradient(from 20deg, transparent 0 12%, #00f5d4 12% 13%, transparent 13% 42%, #52a8ff 42% 43%, transparent 43% 72%, #ff3cac 72% 73%, transparent 73%); mask: radial-gradient(transparent 66%, black 67%); animation: ta-spin 13s linear infinite; }
.ta-core-ring-b { inset: 2.8rem; border: 1px solid rgba(82,168,255,.18); border-left-color: #52a8ff; border-right-color: #ff3cac; animation: ta-spin-reverse 8s linear infinite; }
.ta-core-scan { position: absolute; z-index: 1; inset: 2rem; border-radius: 50%; overflow: hidden; background: conic-gradient(from 0deg, rgba(0,245,212,.13), transparent 18%, transparent); animation: ta-spin 4.5s linear infinite; mask: radial-gradient(black 0 70%, transparent 71%); }
.ta-core-node {
  --angle: calc(var(--node) * 30deg);
  position: absolute;
  z-index: 3;
  left: 50%;
  top: 50%;
  width: .52rem;
  height: .52rem;
  border: 1px solid #00f5d4;
  background: #03171a;
  box-shadow: 0 0 11px rgba(0,245,212,.85);
  transform: translate(-50%,-50%) rotate(var(--angle)) translateY(-8.25rem) rotate(45deg);
  animation: ta-nodepulse 2.4s ease-in-out calc(var(--node) * -.14s) infinite;
}
.ta-core-center {
  position: absolute;
  z-index: 4;
  inset: 6.25rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  clip-path: polygon(18% 0, 82% 0, 100% 18%, 100% 82%, 82% 100%, 18% 100%, 0 82%, 0 18%);
  color: #a9bec9;
  text-align: center;
  background: rgba(2,12,18,.90);
  box-shadow: inset 0 0 34px rgba(0,245,212,.07);
}
.ta-core-center::before { content: ""; position: absolute; inset: 0; border: 1px solid currentColor; opacity: .3; clip-path: inherit; }
.ta-core-center span, .ta-core-center small { color: #60808e; font: .48rem/1.25 ui-monospace, SFMono-Regular, Consolas, monospace; letter-spacing: .08em; }
.ta-core-center strong { margin: .35rem 0; font: 850 1.25rem/1 ui-monospace, SFMono-Regular, Consolas, monospace; letter-spacing: .04em; text-shadow: 0 0 20px currentColor; }
.ta-core-buy { color: #00f5a0; }
.ta-core-sell { color: #ff467e; }
.ta-core-hold { color: #ffd166; }
.ta-core-neutral { color: #8ca7b7; }

.ta-metric-grid { grid-template-columns: repeat(12, minmax(0, 1fr)); grid-auto-rows: 7.7rem; gap: .68rem; }
.ta-metric { min-height: 0; border-radius: 0; clip-path: polygon(0 0, calc(100% - 13px) 0, 100% 13px, 100% 100%, 0 100%); background: linear-gradient(145deg, rgba(5,20,29,.94), rgba(3,12,19,.92)); }
.ta-metric::before { content: ""; position: absolute; left: 0; top: 0; width: 42%; height: 1px; background: linear-gradient(90deg, #00f5d4, transparent); box-shadow: 0 0 10px rgba(0,245,212,.6); }
.ta-metric:nth-child(1) { grid-column: span 4; grid-row: span 2; padding: 1.45rem; }
.ta-metric:nth-child(2) { grid-column: span 2; }
.ta-metric:nth-child(3) { grid-column: span 3; }
.ta-metric:nth-child(4) { grid-column: span 3; }
.ta-metric:nth-child(5) { grid-column: span 8; }
.ta-metric:nth-child(1) .ta-metric-value { margin-top: 1.5rem; font-size: clamp(2.4rem, 5vw, 4.6rem); line-height: .9; text-shadow: 0 0 28px var(--metric-glow); }
.ta-metric:nth-child(5) .ta-metric-value { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }
.ta-metric-label, .ta-metric-hint { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }

.ta-section-kicker { color: #00f5d4; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; text-shadow: 0 0 12px rgba(0,245,212,.35); }
.ta-section-title { font-size: 1.45rem; text-transform: uppercase; letter-spacing: .015em; }
.ta-section-head::after { content: ""; flex: 1; order: 1; height: 1px; max-width: 9rem; align-self: center; background: linear-gradient(90deg, rgba(0,245,212,.55), transparent); }
.ta-section-note { order: 2; }
.ta-stage { border-radius: 0; clip-path: polygon(0 0, calc(100% - 11px) 0, 100% 11px, 100% 100%, 11px 100%, 0 calc(100% - 11px)); background: linear-gradient(145deg, rgba(4,18,27,.92), rgba(2,10,16,.94)); }
.ta-stage-index { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }
.ta-stage-icon { width: fit-content; margin: .72rem 0 .58rem; color: #7aa2ae; font: 820 1.15rem/1 ui-monospace, SFMono-Regular, Consolas, monospace; letter-spacing: -.05em; }
.ta-stage.done .ta-stage-icon { color: #00f5d4; text-shadow: 0 0 14px rgba(0,245,212,.45); }
.ta-stage.active .ta-stage-icon { color: #52a8ff; text-shadow: 0 0 14px rgba(82,168,255,.55); }
@media (min-width: 1101px) {
  .ta-stage:not(:last-child)::after { content: ""; position: absolute; z-index: 3; right: -.65rem; top: 50%; width: .68rem; height: 1px; background: linear-gradient(90deg, rgba(0,245,212,.65), rgba(0,245,212,.08)); }
}
.stTabs [data-baseweb="tab-list"] { border-radius: 0; border-color: rgba(0,245,212,.16); background: rgba(2,10,16,.88); }
.stTabs [data-baseweb="tab"] { border-radius: 0; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; text-transform: uppercase; }
[data-testid="stExpander"] { border-radius: 0 !important; border-color: rgba(0,245,212,.13) !important; background: rgba(3,13,21,.82) !important; }

@keyframes ta-gridshift { to { background-position: 44px 44px, 44px 44px, 176px 176px, 176px 176px; } }
@keyframes ta-spin-reverse { to { transform: rotate(-360deg); } }
@keyframes ta-vertical-scan { 0%,100% { transform: translateY(0); opacity: 0; } 12% { opacity: .75; } 75% { opacity: .28; } 90% { transform: translateY(28rem); opacity: 0; } }
@keyframes ta-nodepulse { 0%,100% { opacity: .4; box-shadow: 0 0 5px rgba(0,245,212,.4); } 50% { opacity: 1; box-shadow: 0 0 17px rgba(0,245,212,1); } }
@keyframes ta-glitch { 0%,91%,100% { transform: translateX(3px); opacity: .25; } 92% { transform: translateX(-7px); opacity: .7; } 94% { transform: translateX(8px); opacity: .45; } 96% { transform: translateX(-2px); opacity: .22; } }

@keyframes ta-pulse { 0%,100% { opacity: .55; transform: scale(.85); } 50% { opacity: 1; transform: scale(1.12); } }
@keyframes ta-float { 0%,100% { transform: translateY(0) rotate(0); } 50% { transform: translateY(10px) rotate(3deg); } }
@keyframes ta-spin { to { transform: rotate(360deg); } }
@keyframes ta-scan { from { transform: translateX(-25%); } to { transform: translateX(25%); } }

@media (max-width: 1100px) {
  .ta-metric-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .ta-metric { grid-column: span 1 !important; grid-row: span 1 !important; min-height: 7.25rem; }
  .ta-metric:nth-child(1) .ta-metric-value { margin-top: .7rem; font-size: clamp(1.2rem, 3vw, 2rem); }
  .ta-stage-rail { grid-template-columns: repeat(4, minmax(0, 1fr)); }
  .ta-hero-grid { grid-template-columns: minmax(0, 1fr) 19rem; }
  .ta-core { width: 18rem; height: 18rem; }
  .ta-core-node { transform: translate(-50%,-50%) rotate(var(--angle)) translateY(-6.7rem) rotate(45deg); }
  .ta-core-center { inset: 5.2rem; }
}
@media (max-width: 760px) {
  .stMainBlockContainer { padding: 1.2rem .85rem 3rem; }
  .ta-hero { min-height: auto; padding: 1.5rem 1.25rem; border-radius: 1.2rem; }
  .ta-hero-grid { grid-template-columns: 1fr; gap: 1.35rem; }
  .ta-hero { padding: .9rem 1.15rem 1.6rem; clip-path: polygon(0 0, calc(100% - 16px) 0, 100% 16px, 100% 100%, 16px 100%, 0 calc(100% - 16px)); }
  .ta-hero-topline { margin: 0 -.25rem 1.5rem; font-size: .5rem; }
  .ta-hero h1 { font-size: clamp(3.7rem, 22vw, 6rem); }
  .ta-hero-cn { font-size: .9rem; letter-spacing: .12em; }
  .ta-core { width: 16rem; height: 16rem; }
  .ta-core-node { transform: translate(-50%,-50%) rotate(var(--angle)) translateY(-5.9rem) rotate(45deg); }
  .ta-core-center { inset: 4.6rem; }
  .ta-signal-wrap { min-width: 0; text-align: left; }
  .ta-metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .ta-stage-rail { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .ta-agent-grid { grid-template-columns: 1fr 1fr; }
  .ta-section-head { display: block; }
  .ta-section-note { margin-top: .35rem; text-align: left; }
}
@media (max-width: 460px) {
  .ta-metric-grid, .ta-agent-grid { grid-template-columns: 1fr; }
  .ta-running-top { align-items: flex-start; }
  .ta-orbit { flex-basis: 4.5rem; width: 4.5rem; height: 4.5rem; }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: .01ms !important; animation-iteration-count: 1 !important; scroll-behavior: auto !important; transition-duration: .01ms !important; }
}
</style>
"""


def inject_theme() -> None:
    st.markdown(APP_CSS, unsafe_allow_html=True)


def signal_tone(signal: str) -> str:
    normalized = str(signal or "").strip().upper()
    if normalized in {"BUY", "OVERWEIGHT"}:
        return "buy"
    if normalized in {"SELL", "UNDERWEIGHT"}:
        return "sell"
    if normalized == "HOLD":
        return "hold"
    return "neutral"


def render_sidebar_brand() -> None:
    st.markdown(
        """
        <div class="ta-brand">
          <div class="ta-logo">TA</div>
          <div>
            <div class="ta-brand-name">TradingAgents</div>
            <div class="ta-brand-sub">Research Intelligence</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_report_hero(ticker: str, trade_date: str, signal: str) -> None:
    tone = signal_tone(signal)
    orbit_nodes = "".join(
        f'<span class="ta-core-node" style="--node:{index}"></span>'
        for index in range(12)
    )
    st.markdown(
        f"""
        <section class="ta-hero">
          <div class="ta-hero-topline">
            <span>TA://NEURAL.MARKET.OS</span>
            <span class="ta-live-lock">● POINT-IN-TIME LOCKED</span>
          </div>
          <div class="ta-hero-grid">
            <div>
              <div class="ta-eyebrow">Autonomous intelligence matrix</div>
              <h1 data-symbol="{escape(ticker)}">{escape(ticker)}</h1>
              <div class="ta-hero-cn">多智能体投研指挥舱</div>
              <p class="ta-hero-copy">四维市场情报进入12-Agent神经网络，多空观点交叉对抗，最终结论通过非LLM硬风控闸门。</p>
              <div class="ta-meta-row">
                <span class="ta-chip"><b>AS-OF</b> {escape(trade_date)}</span>
                <span class="ta-chip"><b>NODES</b> 12 ACTIVE</span>
                <span class="ta-chip"><b>MODE</b> ADVISORY</span>
              </div>
            </div>
            <div class="ta-core" aria-label="12-Agent intelligence core">
              <div class="ta-core-scan"></div>
              <div class="ta-core-ring ta-core-ring-a"></div>
              <div class="ta-core-ring ta-core-ring-b"></div>
              {orbit_nodes}
              <div class="ta-core-center ta-core-{tone}">
                <span>RISK-CONTROLLED</span>
                <strong>{escape(signal or 'N/A')}</strong>
                <small>FINAL SIGNAL</small>
              </div>
            </div>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_metric_grid(metrics: Sequence[Mapping[str, str]]) -> None:
    cards = []
    for metric in metrics:
        tone = escape(str(metric.get("tone", "blue")))
        cards.append(
            "<article class='ta-metric ta-tone-{tone}'>"
            "<div class='ta-metric-label'>{label}</div>"
            "<div class='ta-metric-value'>{value}</div>"
            "<div class='ta-metric-hint'>{hint}</div>"
            "</article>".format(
                tone=tone,
                label=escape(str(metric.get("label", ""))),
                value=escape(str(metric.get("value", "N/A"))),
                hint=escape(str(metric.get("hint", ""))),
            )
        )
    st.markdown(
        "<div class='ta-metric-grid'>" + "".join(cards) + "</div>",
        unsafe_allow_html=True,
    )


def render_section_head(kicker: str, title: str, note: str = "") -> None:
    st.markdown(
        f"""
        <div class="ta-section-head">
          <div>
            <div class="ta-section-kicker">{escape(kicker)}</div>
            <div class="ta-section-title">{escape(title)}</div>
          </div>
          <div class="ta-section-note">{escape(note)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_stage_rail(
    stages: Sequence[tuple[str, str, str]],
    completed: Iterable[str],
    active_index: int | None = None,
) -> None:
    done_keys = set(completed)
    stage_codes = {
        "market_report": "MKT",
        "sentiment_report": "SNT",
        "news_report": "NWS",
        "fundamentals_report": "FND",
        "investment_plan": "DBT",
        "trader_investment_plan": "TRD",
        "final_trade_decision": "PM",
    }
    items = []
    for index, (icon, name, key) in enumerate(stages):
        state = "done" if key in done_keys else "active" if index == active_index else "pending"
        code = stage_codes.get(key, icon)
        items.append(
            f'<div class="ta-stage {state}">'
            '<div class="ta-stage-status"></div>'
            f'<div class="ta-stage-index">STEP {index + 1:02d}</div>'
            f'<div class="ta-stage-icon">{escape(code)}</div>'
            f'<div class="ta-stage-name">{escape(name)}</div>'
            '</div>'
        )
    st.markdown("<div class='ta-stage-rail'>" + "".join(items) + "</div>", unsafe_allow_html=True)


def render_agent_grid(roles: Sequence[tuple[str, str, str]]) -> None:
    items = []
    for index, (name, label, _) in enumerate(roles):
        items.append(
            '<div class="ta-agent">'
            f'<div class="ta-agent-index">AGENT {index + 1:02d}</div>'
            f'<div class="ta-agent-name">{escape(name)}</div>'
            f'<div class="ta-agent-role">{escape(label)}</div>'
            '</div>'
        )
    st.markdown("<div class='ta-agent-grid'>" + "".join(items) + "</div>", unsafe_allow_html=True)


def render_running_header(ticker: str, trade_date: str, progress: float, current: str) -> None:
    percent = max(0, min(100, round(progress * 100)))
    st.markdown(
        f"""
        <section class="ta-running-card">
          <div class="ta-running-top">
            <div>
              <div class="ta-running-kicker">Live research orchestration</div>
              <div class="ta-running-title">正在研究 {escape(ticker)}</div>
              <div class="ta-running-copy">当前任务：{escape(current)} · 数据截止 {escape(trade_date)}。页面会自动更新，风控校验完成前不会生成最终结论。</div>
            </div>
            <div class="ta-orbit"></div>
          </div>
          <div class="ta-progress-track"><div class="ta-progress-fill" style="width:{percent}%"></div></div>
          <div class="ta-progress-meta"><span>{percent}% COMPLETE</span><span>POINT-IN-TIME RESEARCH</span></div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_terminal(log_lines: Sequence[str]) -> None:
    rows = []
    for index, line in enumerate(log_lines[-18:], start=max(1, len(log_lines) - 17)):
        rows.append(
            f"<div class='ta-log-line'><span class='ta-log-n'>{index:02d}</span><span>{escape(str(line))}</span></div>"
        )
    if not rows:
        rows.append("<div class='ta-log-line'><span class='ta-log-n'>00</span><span>等待第一个Agent返回状态…</span></div>")
    st.markdown(
        "<div class='ta-terminal'><div class='ta-terminal-head'>"
        "<span class='ta-terminal-dot live'></span><span class='ta-terminal-dot'></span>"
        "<span>Orchestration event stream</span></div>"
        + "".join(rows)
        + "</div>",
        unsafe_allow_html=True,
    )


def render_empty_state() -> None:
    st.markdown(
        """
        <section class="ta-empty">
          <div>
            <div class="ta-empty-mark">⌁</div>
            <h2>从一个可审计的投资问题开始</h2>
            <p>在左侧选择历史研究，或输入股票代码与组合约束启动一次新的多智能体分析。所有结论均为研究建议，不连接券商执行。</p>
            <div class="ta-meta-row" style="justify-content:center">
              <span class="ta-chip">01 选择标的</span>
              <span class="ta-chip">02 设置约束</span>
              <span class="ta-chip">03 启动研究</span>
            </div>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_state_card(kind: str, title: str, copy: str) -> None:
    safe_kind = kind if kind in {"success", "error"} else ""
    st.markdown(
        f"<div class='ta-state-card {safe_kind}'><div class='ta-state-title'>{escape(title)}</div>"
        f"<div class='ta-state-copy'>{escape(copy)}</div></div>",
        unsafe_allow_html=True,
    )


def render_legal_footer() -> None:
    st.markdown(
        "<div class='ta-legal'>TradingAgents Portfolio Demo · Research advisory only · "
        "No brokerage execution · Verify data provenance and risk assumptions before use</div>",
        unsafe_allow_html=True,
    )
