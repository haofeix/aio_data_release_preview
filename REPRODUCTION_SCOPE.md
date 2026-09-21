# Reproduction Scope

This checklist follows the paper order. Reported values are reproduction targets.

Coverage: Tables 2–11 and Figures 2–5.

## 1. Collected dataset (§3.1–§3.2)

| Data | Target |
|---|---:|
| Observation window | March 13–April 21, 2026 (40 days) |
| Google Trends categories | 19 |
| Google Trends CSVs | 760 |
| Query executions | 55,393 |
| AIO observations | 7,583 (13.7%) |
| AIO reference occurrences | 61,212 |
| Unique AIO hostnames | 7,479 |
| AIO/SERP comparison cohort | 7,562 AIOs |
| AIO references in the comparison cohort | 61,046 |
| First-page SERP links in the comparison cohort | 241,710 |
| Cited pages without captured text | 44 (0.07%) |

## 2. Fact extraction and verification (§3.3)

| Paper item | Reproduce |
|---|---|
| Table 2 | Counts and shares for all five labels across 98,020 judgments from 7,491 AIOs; Consistent = Clear + Vague; Inconsistent = Ambiguous + Incorrect + Omitted. |

## 3. AIO activation (§4.1)

| Paper item | Reproduce |
|---|---|
| Figure 2 | Daily query count, daily AIO activation rate, and trailing 7-day average. |
| Table 3 | Queries, AIOs, activation rate, and corpus share by category. |
| Table 4 | Queries, AIOs, and activation rate by leading interrogative; question vs. non-question totals. |
| Table 5 | Queries, AIOs, and activation rate by query length, overall and for non-question queries. |
| Reported tests | Category query volume vs. activation; activation vs. fidelity; question vs. non-question activation. |

## 4. Source selection (§4.2)

| Paper item | Reproduce |
|---|---|
| Figure 3 | Distribution of reference counts per AIO. |
| Figure 4 | Median reference count by category. |
| Table 6 | Mean PC1, matched URL count, AIO–SERP difference, and corrected significance by category. |
| Table 7 | Query-paired PC1 under Top 1, 3, 5, 10, full-page, and geometric SERP specifications. |
| Table 8 | AIO and SERP UGC counts and shares by category, differences, and corrected significance. |
| Reference reliance | References per AIO; unique hosts; hostname concentration; most-cited hosts. |
| PC1 comparison | PC1 coverage, overall means, difference, confidence interval, Welch test, and category ANOVA. |
| AIO/SERP overlap | Domain overlap at Top 5, Top 10, and full page; off-page share; on-page vs. off-page PC1 and UGC. |

## 5. Claim fidelity (§4.3)

| Paper item | Reproduce |
|---|---|
| Claim extraction totals | 98,098 claims from 7,583 AIOs; mean 12.9, median 12, range 0–64. |
| Verification cohort | 7,491 AIOs and 98,020 judgments; exclude 80 AIOs with zero claims and 12 with only social-media references. |
| Overall fidelity | 87,204 consistent claims (88.97%) and 10,816 inconsistent claims (11.03%). |
| AIO-level fidelity | Median consistency; fully consistent, ≥90%, <50%, and 0% consistent AIO counts and shares. |
| Figure 5 | Verification-label distribution and claim count by category. |
| UGC sensitivity | Inconsistent claims associated with UGC-citing AIOs and the reported residual inconsistency estimate. |
| Real-time sensitivity | Adjusted fidelity for Technology, Shopping, and Jobs & Education after heuristic exclusions. |

## 6. Publisher economic exposure (§4.4)

| Paper item | Reproduce |
|---|---|
| Table 9 | Reference count, UGC count, and observed ad prevalence by category. |
| Cited-page ads | 30,994 of 61,212 references with observed ads (50.63%). |
| Sponsored search ads | 164 AIO SERPs with sponsored ads, 39 with an ad above the AIO, and 0 inside the AIO. |
| Sponsored-ad categories | Counts for Sports, Business & Finance, Entertainment, Politics, and Law & Government. |

## 7. Robustness analyses (Appendices B, E, and F)

| Paper item | Reproduce |
|---|---|
| Table 10 | Query-paired PC1 comparisons with MBFC factuality, Lasser mean, and Burdisso p-reliability. |
| Repeated-query description | 32,608 unique normalized queries; repetition groups, executions, and shares. |
| Table 11 | Baseline vs. query-balanced activation, references, UGC, PC1, ads, fidelity, failure labels, and domain concentration. |
| Repeated-observation stability | 17,867 adjacent cross-day pairs; AIO agreement, identical text, identical source sets, and URL-set Jaccard similarity. |
| Appendix F | Real-time exclusions for Jobs & Education, Technology, and Shopping, with AIO and claim counts. |

## Non-statistical paper items

- Figure 1: methodology overview.
- Appendix A: definitions of the 19 Google Trends categories.
- Appendices C and D: claim-extraction and verification prompts.
