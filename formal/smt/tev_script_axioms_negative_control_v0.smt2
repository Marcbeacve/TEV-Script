(set-logic ALL)

(declare-sort Field 0)
(declare-fun Admitted (Field Field) Bool)
(declare-fun Selected (Field Field) Bool)

(declare-const P Field)
(declare-const C Field)

; Deliberately omit Selected -> Admitted.
; The forbidden state is now satisfiable. RepoTalk must run this as:
; expected_outcome=unsat, negative_control=true.
(assert (Selected P C))
(assert (not (Admitted P C)))
(check-sat)
