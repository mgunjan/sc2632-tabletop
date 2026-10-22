# Separate hierarchy diagnostic

This is an additional CPU algorithm comparison, specified during the neural repair run. It is not Laya and will not replace its result. The original authored test has already been examined in prior experiments.

Freeze one architecture without hyperparameter search: shared plus candidate-conditioned TF-IDF features (existing word/character feature recipe), logistic regression C=4, balanced class weights, max_iter=2000. Stage one predicts relevance from operator intent only. Stage two predicts recommend versus review on relevant rendered training rows using intent/evidence/constraints. Static candidate catalog prose does not supply incident evidence. Non-rendered relevant controls map to handoff by the existing task contract. Compose the two probabilities into the original four dispositions. No keyword rules or case-specific patches are added.

Train this exact architecture twice: once on the original 360 rows and once on the repaired 1,310 rows. Record development results for both, then score both with unchanged benchmark calibration/test logic regardless of outcome. This separates the architecture comparison from the data comparison. Neither model is selected using test results. All results, including accepted wrong plans, remain visible. No hosted calls occur.
