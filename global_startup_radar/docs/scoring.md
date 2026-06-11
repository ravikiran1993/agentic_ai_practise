# Startup Trend Scoring Explained

Global Startup Radar uses an explainable heuristic score to rank evidence about startups after Pinecone retrieves semantically relevant chunks.

The score is designed for exploration, not investment decisions. It answers:

```text
Given the evidence currently available, which startup chunks look most relevant and most active for this query?
```

It does **not** answer:

```text
Which startup will succeed?
How much revenue does this startup have?
How much funding did it raise?
What is its valuation?
```

## Where Scoring Happens

The scoring logic lives in:

```text
global_startup_radar/src/startup_radar/scoring.py
global_startup_radar/src/startup_radar/reranking.py
```

The high-level flow is:

```text
User question
-> Gemini query embedding
-> Pinecone semantic retrieval
-> Retrieved chunks with similarity scores
-> Trend score calculation
-> Final rerank score
-> Sorted evidence order
-> Gemini answer prompt
```

## Two Scores Are Shown

The app uses two related scores.

### 1. Trend Score

The **trend score** is a 0-100 score that combines semantic relevance, freshness, Product Hunt traction, source breadth, and query metadata match.

It is calculated by `compute_trend_score()`.

### 2. Rerank Score

The **rerank score** is the final sorting score used after Pinecone retrieval.

It is calculated by `rerank_evidence()`:

```text
rerank_score =
  0.55 * pinecone_similarity_score
  + 0.45 * (trend_score / 100)
```

This means Pinecone semantic relevance remains the largest signal, but strong trend signals can change the final order.

## Trend Score Formula

Each component is normalized to a 0-1 range. The weighted sum is multiplied by 100.

```text
trend_score =
  100 * (
    0.30 * semantic_relevance
  + 0.18 * launch_recency
  + 0.14 * product_hunt_votes
  + 0.10 * product_hunt_comments
  + 0.10 * source_diversity
  + 0.08 * evidence_count
  + 0.10 * sector_or_region_match
  )
```

The final score is clamped between 0 and 100.

## Score Components

### Semantic Relevance

```text
Weight: 30%
Input: Pinecone similarity score
```

This measures how closely the retrieved chunk matches the user's question in vector space.

Example:

```text
Question: Which startups help businesses automate operations?
Relevant chunk: AI workflow automation platform for operations teams.
```

This should receive a higher semantic relevance score than an unrelated consumer entertainment startup.

### Launch Recency

```text
Weight: 18%
Input: published_at / launch date
```

Recent launches get more credit.

Current behavior:

```text
0-7 days old: full score
180+ days old: zero score
Between 7 and 180 days: linearly decays over time
```

This makes recent startup launches surface more strongly.

### Product Hunt Votes

```text
Weight: 14%
Input: product_hunt_votes
```

Votes are log-scaled so very large vote counts help, but do not completely dominate the ranking.

The implementation uses:

```text
log10(votes + 1) / log10(1000 + 1)
```

Then it clamps the result between 0 and 1.

Why log scaling?

```text
The difference between 10 and 100 votes matters a lot.
The difference between 900 and 1000 votes matters less.
```

### Product Hunt Comments

```text
Weight: 10%
Input: product_hunt_comments
```

Comments are also log-scaled:

```text
log10(comments + 1) / log10(200 + 1)
```

Comments are useful because they can indicate discussion, interest, feedback, and attention.

### Source Diversity

```text
Weight: 10%
Input: number of source types in retrieved evidence
```

This rewards result sets that include more than one kind of evidence.

Example source types:

```text
product_hunt
company_site
news
yc
```

In the current live system, source diversity commonly comes from Product Hunt plus company website chunks.

### Evidence Count

```text
Weight: 8%
Input: number of retrieved chunks for the same startup
```

If multiple chunks support the same startup, that startup receives a small boost.

The current normalization is:

```text
evidence_count_score = min(evidence_count / 5, 1)
```

This avoids over-rewarding a startup just because many chunks exist.

### Sector Or Region Match

```text
Weight: 10%
Input: query terms compared with sector, region, country, and topics metadata
```

This checks whether important query terms appear in metadata.

Example:

```text
Question: Which AI startups are trending in Europe?
Metadata: sector = AI, region = Europe
```

This should receive a stronger metadata match than a startup with no AI or Europe metadata.

## Example Calculation

Imagine a user asks:

```text
Which AI productivity startups are trending?
```

Suppose Pinecone retrieves a Product Hunt chunk for a startup with these signals:

```text
Pinecone similarity: 0.82
Launch age: 3 days
Votes: 500
Comments: 50
Source diversity: 0.50
Evidence count: 3 chunks
Metadata: topics include AI and Productivity
```

Approximate normalized component values:

```text
semantic_relevance       = 0.82
launch_recency           = 1.00
product_hunt_votes       ~= 0.90
product_hunt_comments    ~= 0.74
source_diversity         = 0.50
evidence_count           = 0.60
sector_or_region_match   = 0.50
```

Weighted trend score:

```text
trend_score =
  100 * (
    0.30 * 0.82
  + 0.18 * 1.00
  + 0.14 * 0.90
  + 0.10 * 0.74
  + 0.10 * 0.50
  + 0.08 * 0.60
  + 0.10 * 0.50
  )

trend_score ~= 77.4
```

Final rerank score:

```text
rerank_score =
  0.55 * 0.82
  + 0.45 * (77.4 / 100)

rerank_score ~= 0.799
```

The app then sorts chunks by `rerank_score` from highest to lowest.

## Why We Rerank After Pinecone

Pinecone answers:

```text
Which chunks are semantically closest to the question?
```

Reranking answers:

```text
Among the semantically relevant chunks, which ones also look fresh, active, well-supported, and query-aligned?
```

This matters because a startup can be semantically relevant but old or weakly supported. Another startup can be slightly less semantically similar but much more recent and active.

## What The Score Means

A high score means:

- the chunk matched the question well
- the launch is recent
- Product Hunt traction is stronger
- more evidence exists for the startup
- metadata aligns with the query

A low score means:

- the chunk may be less relevant
- the launch may be older
- votes/comments may be weaker
- evidence may be thin
- metadata may not match the question

## What The Score Does Not Mean

The score does **not** mean:

- the startup is a good investment
- the startup raised funding
- the startup has revenue
- the startup has strong customer traction
- the startup will become successful

The score is only a ranking signal for the current RAG evidence.

## Known Limitations

- Product Hunt votes are not the same as customers or revenue.
- Comments can reflect curiosity, criticism, or support.
- Company websites contain marketing claims and may omit weaknesses.
- Funding information is not available unless a retrieved source explicitly says it.
- Metadata matching is simple term matching, not deep classification.
- The current trend score is heuristic and intentionally transparent.

## Future Improvements

Possible improvements:

- Add funding/news sources for investment and fundraising questions.
- Add model-based reranking after the heuristic reranker.
- Add per-startup aggregate scoring instead of per-chunk scoring only.
- Add source reliability weights.
- Add confidence scoring based on source agreement.
- Add temporal trend tracking across multiple days or weeks.
