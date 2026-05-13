# Metrics & Growth Loops
## Telugu → Hindi/English Shorts Bot

**Date:** 2026-05-11
**Frameworks:** `north-star-metric` + `growth-loops`

---

## 1. North-Star Metric

### Primary
**Long-form click-through rate from Shorts**
= (clicks on "Watch full video" link in Shorts description) ÷ (total Shorts views)

**Target:** ≥ 2% within first 90 days

### Why this is the North-Star
This single metric captures whether the entire strategy works:
- If high → Shorts are good hooks AND viewers want more depth → channel grows
- If low → either Shorts aren't engaging, OR they don't tease the long-form well, OR the audience doesn't care about deeper content
- Unlike pure "views," it forces alignment between Short quality and the actual goal (driving people to the source channel and your own growth)

---

## 2. Input Metrics (the levers you can pull)

These are the metrics you optimize **to move the North-Star**:

| Metric | What it measures | Target | Drives |
|---|---|---|---|
| **Avg watch-time retention %** | How much of each Short people watch | ≥ 65% | More views → more clicks |
| **Hook retention (first 3 sec)** | % still watching at 3 seconds | ≥ 80% | Stops scrollers, all downstream metrics |
| **CTA strength score** | Manual 1–5 rating of how compelling the close is | ≥ 4 | Direct lever on click-through |
| **Shorts published per week** | Volume of content shipped | 7/week | Discovery surface area |
| **Style mix balance** | % of Shorts per style (comedy/documentary/etc.) | Tracked, no target | A/B insights |
| **Script edit-distance** | How much I have to edit each draft | ≤ 20% | Tool usability (am I actually using it?) |

---

## 3. Output Metrics (the result you measure)

| Metric | What it measures | 90-day target |
|---|---|---|
| Total Shorts views | Reach | 100k |
| Subscribers gained | Channel growth | 1,000 |
| Long-form click-throughs (CTR) | **North-star** | 2,000 (~2%) |
| Comments per Short | Engagement depth | avg 5/Short |
| Shares per Short | Virality | avg 2/Short |

---

## 4. Anti-Metrics (things you do NOT optimize for, watch for inflation)

- **Pure view count** — easy to inflate with clickbait; doesn't correlate with channel growth
- **Likes** — vanity, weak signal
- **Watch time in minutes** (raw) — meaningless without retention %

---

## 5. Growth Loops

### Loop A — The Primary Loop (Shorts → Long-Form → Subscribe → More Shorts)

```
[New Telugu video posted by source channel]
            ↓
[Bot generates Hoog-style Hindi/English Short]
            ↓
[Short surfaces on YouTube Shorts feed → viewer scrolls past, but hooked in first 3 sec]
            ↓
[Viewer watches to end → sees "Watch full video" CTA]
            ↓
[Viewer clicks → arrives at original long-form Telugu video on source channel]
            ↓
[If viewer is Hindi/English speaker → also visits MY channel link in description]
            ↓
[Viewer subscribes to my channel → sees MORE Shorts in feed]
            ↓ (loop)
```

**Acceleration levers:**
- Hook quality (top 3 sec retention)
- CTA strength
- Description copywriting (clear value prop for clicking through)
- Cross-link my own channel prominently

### Loop B — The Discovery Loop (Algorithm Promotion)

```
[High retention on a Short]
            ↓
[YouTube algorithm pushes it to more viewers]
            ↓
[More views → more retention data → more pushes]
            ↓ (loop)
```

**Acceleration levers:**
- Pick high-retention styles (data from `ab-test-analysis` later)
- Trending topics from source channels
- Strong thumbnails (auto-generated, A/B tested)

### Loop C — The Content Engine Loop (Source Channels → Pipeline → My Output)

```
[Source Telugu channels keep posting]
            ↓
[Bot keeps producing daily Shorts]
            ↓
[More Shorts in market → more chances to catch a viral one]
            ↓
[Viral hit → channel grows → builds audience for future Shorts]
            ↓ (loop)
```

**Acceleration levers:**
- Add more source channels (broadens topic mix)
- Faster pipeline (more daily output)
- Better template variety

---

## 6. Measurement Setup (what to build for tracking)

| What | How | When |
|---|---|---|
| Shorts views, retention, subscribers gained | YouTube Studio Analytics + YouTube Data API export to local CSV | Day 1 |
| Long-form click-throughs | UTM-tagged links in description, tracked via bit.ly/Rebrandly | Day 1 |
| Per-style performance | Log style tags per Short in local SQLite; join with Analytics export | Week 2 |
| Hook retention (3-sec) | YouTube Analytics "Audience retention" report, scraped weekly | Week 2 |
| Script edit-distance | Compute in code, log to SQLite at each approval | Day 1 |
| Plagiarism score | Run rewrite through originality check API monthly | Week 4 |

---

## 7. Decision Cadence

| Cadence | Review |
|---|---|
| **Daily** | Did the pipeline run? Was the script editable? |
| **Weekly** | Top/bottom Shorts by retention. What style/topic worked? |
| **Monthly** | North-star CTR. Cost per Short. Trigger reviews from RISKS.md? |
| **Quarterly** | Strategic review: keep going, pivot, or shut down? |
