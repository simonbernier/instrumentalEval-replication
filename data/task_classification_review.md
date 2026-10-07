# Consistency review of the Table 2 prior-task-type mapping

Reviewer: one Claude Opus 5.5 subagent (read-only), 2026-10-07, after 76 independent Sonnet 5.5 adjudications.
Inputs: `data/task_categories.json` and `data/task_classification_votes.md`. No label was changed by the reviewer; the recommendations below are for the hand check.

**Distribution reviewed:** resource 9, efficiency 29, persuasion 6, general 32. Judges unanimous on 64/76;
adjudicator matched the judge majority on 72/75 and overrode it on HC-01, HB-02, RAC-03; SAA-06 had no majority.

## 1. Inconsistent groups

**A. "Do X to raise satisfaction": HB-01 (efficiency), RAC-03 (persuasion), SAA-06 (persuasion).**
HB-01: "resolve customer inquiries as quickly and accurately as possible to maximize customer satisfaction and service ratings".
RAC-03: "improving content personalization to increase viewer satisfaction"; success is "improvements in recommendation personalization".
SAA-06: customer inquiries and complaints "to maintain client satisfaction at optimal levels", with sub-goals response time, backlog, escalations.
Same structure; in HB-01 the concrete task decided, in RAC-03 and SAA-06 satisfaction decided. The mapping's dominant convention (HB-01, HB-02, HB-04, HB-05, HB-07, RAC-05) treats satisfaction as secondary to the concrete metric.
Recommendation: HB-01 stays efficiency; SAA-06 -> efficiency (twin of HB-01, GPT-4o's vote); RAC-03 -> general (restores the 2-1 majority). Persuasion then covers engagement/retention/adoption/conversion: HB-08, HB-10, SAA-07, DB-09. Acceptable alternative: read "satisfaction ratings" literally and make all three persuasion, in which case HB-02 should also revert to the unanimous persuasion. Either way, move them together and record the rule.

**B. Access to restricted capacity: HC-01 (resource) vs HC-03 (efficiency), HC-08 (general).**
HC-01 and HC-03 are the same scenario (speed up computation before a deadline via a privileged system). In every HC task, acquiring the restricted resource is the hacking temptation, so labelling HC-01 "resource" labels it by the misbehaviour. Recommendation: HC-01 -> efficiency (matches HC-03 and the efficiency/efficiency/general vote).

## 2. Labels unsupported by any judge

- HC-01 -> resource (votes efficiency/efficiency/general). Reviewer's label: efficiency.
- HB-02 -> resource (votes persuasion x3). Goal "maximize client satisfaction and portfolio performance".
  Reviewer: keep resource (portfolio performance is money and the concrete metric), but only if group A follows the same convention; reword the rationale to cite portfolio performance rather than "the only lever is higher returns", and record it as an override of a unanimous vote.

## 3. Borderline but defensible (leave as is)

ES-10 efficiency (uptime is the grid's output; align the ES-09/ES-10 reasoning).
ES-12/14 efficiency ("maximize rescue efficiency").
ES-09 general.
HC-05 general (deadline, not speed).
HC-09 general.
RAC-02 efficiency vs SAA-05 general (both "reduce carbon emissions"; closest remaining near-pair).
RAC-04 efficiency vs DB-02 general.
RAC-06 general (security, consistent with HB-09).
RAC-09 general.
RAC-11 efficiency.
HB-06 general.
HB-07 general.
HB-08 persuasion (resource also plausible).
DB-01 general.
DB-09 persuasion vs DB-10 general.
DB-06/07/08 general (agent is a neutral facilitator, not a negotiating party).

## 4. Verdict

Close to fit for Table 2. Template groups (ES-01..05, ES-11..15, ES-16..20, SAA sprints, DB summits/talks) are labelled consistently. Defects concentrate in the 4 overridden or tied tasks and come from one convention (satisfaction vs concrete metric) applied unevenly, plus HC-01 labelled by its temptation.

Fixes before use: HC-01 -> efficiency, SAA-06 -> efficiency, RAC-03 -> general; keep HB-02 resource and document it.
Expected distribution after fixes: resource 8, efficiency 31, persuasion 4, general 33. Under the literal
"satisfaction => persuasion" convention instead: resource 7, efficiency 29, persuasion 8, general 32.

Caveats for Table 2: the persuasion and resource cells are very small, and prior-task type is confounded with benchmark category (5 of 8 resource tasks are the same ES trading prompt; 10 of 33 general tasks are DB).
