(set-logic ALL)

(declare-const HasCapability Bool)
(declare-const CommitEffect Bool)

; Deliberately omit CommitEffect -> HasCapability.
; The forbidden state is therefore satisfiable. RepoTalk must execute this with
; expected_outcome=unsat and negative_control=true.
(assert CommitEffect)
(assert (not HasCapability))
(check-sat)
