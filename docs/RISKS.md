# Risks & Assumptions
## Telugu → Hindi/English Shorts Bot (Personal Use)

**Date:** 2026-05-11
**Methodology:** `identify-assumptions-new` + `pre-mortem`

---

## ⚠️ Non-Negotiable Constraint

**The output videos MUST be watchable.** This overrides all cadence, cost, and schedule trade-offs.

- If the pipeline cannot produce watchable Shorts, **lower the cadence**, do not lower the quality.
- A manual quality-review gate exists before YouTube upload — operator can reject any render that fails the watchability bar.
- "Watchable" means: smooth animations, clear/natural TTS, visuals matching the script, readable captions, professional polish — not amateur or AI-slop.

---

## Part 1: Risky Assumptions (by category)

### A. Value Assumptions — *"Will the output be watchable / engaging?"*

| # | Assumption | Risk Level | Test |
|---|---|---|---|
| V1 | Hindi/English Shorts based on Telugu long-form content will get views & engagement | **High** | Publish 10 Shorts, measure views & retention before investing more |
| V2 | ~60% Hoog-style visual fidelity is "good enough" to attract viewers | **High** | A/B test motion-graphics Shorts vs plain B-roll Shorts |
| V3 | The "Watch full video" CTA will drive meaningful click-through to long-form | **Medium** | Track referral clicks via UTM-tagged links in description |
| V4 | Daily cadence is sustainable (no creative/topic fatigue from 2 source channels) | **Medium** | Track unique-topic ratio; if source channels post < daily, queue/buffer videos |

### B. Usability Assumptions — *"Will I (the operator) actually use it daily?"*

| # | Assumption | Risk Level | Test |
|---|---|---|---|
| U1 | The script review step takes ≤ 5 min/day | **Medium** | Time the first 5 review sessions; if > 10 min, simplify UI |
| U2 | Generated scripts will need minimal edits (≤ 20% changes) | **High** | Track edit-distance between draft and approved script |
| U3 | Style selection is intuitive (comedy/documentary combos make sense) | **Low** | Self-test |

### C. Feasibility Assumptions — *"Can it technically be built reliably?"*

| # | Assumption | Risk Level | Test |
|---|---|---|---|
| F1 | Whisper large-v3 transcribes Telugu accurately enough (≥ 90% word accuracy) | **High** | Manually verify 5 transcriptions; compare against subtitles if available |
| F2 | Claude can plagiarism-safe-rewrite Telugu→Hindi/English in target styles | **Medium** | Run plagiarism check (e.g. Copyscape) on 5 generated scripts |
| F3 | Remotion can render Hoog-style motion graphics at acceptable quality | **Medium** | Build 1 template POC before full pipeline |
| F4 | ElevenLabs Hindi voice sounds natural enough for documentary tone | **Medium** | Generate 30s sample, listen-test |
| F5 | YouTube Data API quota (10k units/day) supports daily uploads | **Low** | 1 upload ≈ 1,600 units → daily upload uses 16% quota. Safe. |
| F6 | The pipeline runs end-to-end in < 15 min unattended | **Medium** | Measure first end-to-end run; profile bottlenecks |

### D. Viability / Cost Assumptions

| # | Assumption | Risk Level | Test |
|---|---|---|---|
| C1 | Total cost per Short < $0.50 (personal budget) | **Medium** | Track actual costs for first 30 Shorts |
| C2 | API rate limits won't block daily runs (ElevenLabs free → paid tier) | **Low** | Set up usage alerts |
| C3 | Local machine has enough CPU/RAM for Whisper large-v3 (~10GB VRAM ideal) | **High** | Benchmark; fall back to Whisper medium if needed |

### E. Legal / Compliance Assumptions

| # | Assumption | Risk Level | Test |
|---|---|---|---|
| L1 | Transformative-use (translation + restyle + Shorts repackaging + credit) is sufficient under YouTube ToS | **High** | Reach out to source creators for explicit permission. If denied, switch channels. |
| L2 | YouTube algorithm won't flag uploads as duplicate/reuploaded | **High** | Monitor first 10 uploads for strikes / monetization issues |
| L3 | Crediting + linking original is enough to avoid copyright strikes | **High** | Same as L1/L2 — get permission upfront |

---

## Part 2: Pre-Mortem — *"It's 6 months later. The project failed. Why?"*

### Top 10 Failure Modes (ranked by likelihood × impact)

| # | Failure | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | **Copyright strike on output channel** | High | Catastrophic (channel taken down) | Get written permission from source creators FIRST. Add prominent credit + link in every video & description. Keep a copy of permission emails. |
| 2 | **Whisper Telugu accuracy is poor** → bad translations → poor Shorts | Med | High | Test on 5 sample videos before full build. Fallback: AssemblyAI paid API for Telugu. |
| 3 | **Daily review burden > 10 min** → I stop using the tool | Med | High | Optimize review UI ruthlessly. Allow "auto-approve" mode after 30 days of high-quality drafts. |
| 4 | **Remotion output looks cheap/amateur**, channel can't grow | Med | High | Build template library iteratively. Hire a Fiverr designer to make 3 high-quality Remotion templates. |
| 5 | **YouTube algorithm doesn't promote** the Shorts (low views) | High | Medium | Iterate on hooks, thumbnails, titles. Track per-style performance via cohort-analysis. |
| 6 | **API costs spiral** (ElevenLabs + Claude usage) past $50/mo | Low | Medium | Set hard monthly budget caps. Use Whisper local (free), shorter scripts. |
| 7 | **Pipeline breaks silently** in production, no Shorts for days | Med | Medium | Robust error handling + desktop notification on failure. Health-check job. |
| 8 | **ElevenLabs voice sounds robotic** in Hindi | Med | Medium | Test multiple voices upfront. Fallback: Google Cloud TTS or Eleven multilingual v2. |
| 9 | **Source channels stop posting** or change topic | Low | Medium | Make source channels configurable. Maintain a pool of 4–5 backup channels. |
| 10 | **YouTube Data API quota exceeded** during testing | Low | Low | Already budgeted (~16% of daily quota per upload). Cache aggressively. |

---

## Part 3: Pre-Build Validations (MUST DO before writing code)

1. **Get permission from source channel creators** (or explicit transformative-use comfort) — L1, top failure mode
2. **Run Whisper large-v3 on 1 sample Telugu video** — F1, C3 (does my hardware handle it?)
3. **Generate 1 ElevenLabs Hindi voiceover** — F4 (sounds natural?)
4. **Build 1 Remotion template** matching Hoog's animated-map look — F3
5. **Run plagiarism check on 1 Claude rewrite** — F2

If any of #1–#5 fail, the project plan needs revision before code.

---

## Part 4: Decision Triggers

| Trigger | Action |
|---|---|
| 2+ copyright strikes in first 30 days | Halt project, reconsider legal approach |
| Avg watch-time retention < 40% after 20 Shorts | Pivot style or topic mix |
| API costs > $50/month | Switch to free/cheaper alternatives |
| Daily review takes > 10 min/day for 1 week | Simplify UI or auto-approve mode |
| Whisper accuracy < 85% on Telugu | Switch to paid transcription (AssemblyAI) |
