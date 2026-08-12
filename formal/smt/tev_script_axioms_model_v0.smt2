(set-logic ALL)

(declare-datatypes () ((Field F0 F1 F2)))
(declare-datatypes () ((Backend B0 B1)))

(declare-fun SemanticTag (Field) Int)
(declare-fun BackendTag (Field) Backend)
(declare-fun CostTag (Field) Int)
(declare-fun SemEq (Field Field) Bool)

(assert (forall ((x Field) (y Field))
  (= (SemEq x y) (= (SemanticTag x) (SemanticTag y)))))

; F0 and F1: same semantics, different backend and cost.
(assert (= (SemanticTag F0) 0))
(assert (= (SemanticTag F1) 0))
(assert (= (BackendTag F0) B0))
(assert (= (BackendTag F1) B1))
(assert (= (CostTag F0) 0))
(assert (= (CostTag F1) 1))
(assert (SemEq F0 F1))
(assert (not (= (BackendTag F0) (BackendTag F1))))
(assert (not (= (CostTag F0) (CostTag F1))))

; F0 and F2: same backend/cost, different semantics.
(assert (= (SemanticTag F2) 1))
(assert (= (BackendTag F2) B0))
(assert (= (CostTag F2) 0))
(assert (not (SemEq F0 F2)))
(assert (= (BackendTag F0) (BackendTag F2)))
(assert (= (CostTag F0) (CostTag F2)))

(check-sat)
