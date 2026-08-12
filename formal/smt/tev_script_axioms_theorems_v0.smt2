(set-logic ALL)

(declare-sort Field 0)

(declare-fun SemEq (Field Field) Bool)
(declare-fun CandidateOf (Field Field) Bool)
(declare-fun Admitted (Field Field) Bool)
(declare-fun Selected (Field Field) Bool)
(declare-fun ProofRequired (Field Field) Bool)
(declare-fun Rejected (Field Field) Bool)
(declare-fun Best (Field Field) Bool)
(declare-fun Indeterminate (Field) Bool)
(declare-fun NoAdmissible (Field) Bool)

; A0: Field semantic equivalence.
(assert (forall ((x Field)) (SemEq x x)))
(assert (forall ((x Field) (y Field))
  (=> (SemEq x y) (SemEq y x))))
(assert (forall ((x Field) (y Field) (z Field))
  (=> (and (SemEq x y) (SemEq y z)) (SemEq x z))))

; A6: selection is a candidate relation and admission precedes selection.
(assert (forall ((p Field) (c Field))
  (=> (Selected p c) (CandidateOf p c))))
(assert (forall ((p Field) (c Field))
  (=> (Selected p c) (Admitted p c))))
(assert (forall ((p Field) (c Field))
  (=> (Selected p c) (not (ProofRequired p c)))))
(assert (forall ((p Field) (c Field))
  (=> (Selected p c) (not (Rejected p c)))))

; A7: NO_ADMISSIBLE is a closed result: every bound candidate is rejected.
(assert (forall ((p Field))
  (= (NoAdmissible p)
     (forall ((c Field))
       (=> (CandidateOf p c) (Rejected p c))))))

; A7: any open candidate admission forces indeterminacy.
(assert (forall ((p Field))
  (=> (exists ((c Field))
        (and (CandidateOf p c) (ProofRequired p c)))
      (Indeterminate p))))

; A7: indeterminate means no candidate is selected.
(assert (forall ((p Field))
  (=> (Indeterminate p)
      (forall ((c Field)) (not (Selected p c))))))

; A7: two distinct admitted best candidates force indeterminacy.
(assert (forall ((p Field) (a Field) (b Field))
  (=> (and
        (Admitted p a)
        (Admitted p b)
        (Best p a)
        (Best p b)
        (not (SemEq a b)))
      (Indeterminate p))))

(declare-const P Field)
(declare-const A Field)
(declare-const B Field)
(declare-const C Field)

; T4: a closed no-admissible result implies no selected candidate.
(push)
(assert (NoAdmissible P))
(assert (Selected P C))
(check-sat)
(pop)

; T5: an open admission forces indeterminate and hence no selection.
(push)
(assert (CandidateOf P A))
(assert (ProofRequired P A))
(assert (Selected P C))
(check-sat)
(pop)

; T6: distinct tied best candidates force indeterminate and hence no selection.
(push)
(assert (Admitted P A))
(assert (Admitted P B))
(assert (Best P A))
(assert (Best P B))
(assert (not (SemEq A B)))
(assert (Selected P C))
(check-sat)
(pop)

; T7a: a selected candidate cannot remain proof-required.
(push)
(assert (Selected P C))
(assert (ProofRequired P C))
(check-sat)
(pop)

; T7b: a selected candidate cannot be rejected.
(push)
(assert (Selected P C))
(assert (Rejected P C))
(check-sat)
(pop)
