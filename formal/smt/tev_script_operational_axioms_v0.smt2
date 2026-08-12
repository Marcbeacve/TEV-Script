(set-logic ALL)

; Exact non-negative resource quantities.
(declare-const a Real)
(declare-const b Real)
(declare-const c Real)
(assert (>= a 0))
(assert (>= b 0))
(assert (>= c 0))

(define-fun maxR ((x Real) (y Real)) Real
  (ite (>= x y) x y))

; L6.3: SUM aggregation is associative.
(push)
(assert (not (= (+ (+ a b) c) (+ a (+ b c)))))
(check-sat)
(pop)

; L6.3: MAX aggregation is associative.
(push)
(assert (not (= (maxR (maxR a b) c) (maxR a (maxR b c)))))
(check-sat)
(pop)

; L3.1/L3.3: a committed host effect requires an admitted capability.
(declare-const HasCapability Bool)
(declare-const CommitEffect Bool)
(assert (=> CommitEffect HasCapability))
(push)
(assert CommitEffect)
(assert (not HasCapability))
(check-sat)
(pop)

; L6.4/L5.3: an unknown upper resource bound cannot silently PASS a finite ceiling.
(declare-const ResourceUpperKnown Bool)
(declare-const ResourceAdmissionPass Bool)
(assert (=> (not ResourceUpperKnown) (not ResourceAdmissionPass)))
(push)
(assert (not ResourceUpperKnown))
(assert ResourceAdmissionPass)
(check-sat)
(pop)

; L8.1/L8.2: a verified system receipt binds exact API and artifact identities.
(declare-sort Hash 0)
(declare-const ExpectedApiHash Hash)
(declare-const ObservedApiHash Hash)
(declare-const ExpectedArtifactHash Hash)
(declare-const ObservedArtifactHash Hash)
(declare-const VerifiedReceipt Bool)
(assert (=> VerifiedReceipt (= ExpectedApiHash ObservedApiHash)))
(assert (=> VerifiedReceipt (= ExpectedArtifactHash ObservedArtifactHash)))

(push)
(assert VerifiedReceipt)
(assert (not (= ExpectedApiHash ObservedApiHash)))
(check-sat)
(pop)

(push)
(assert VerifiedReceipt)
(assert (not (= ExpectedArtifactHash ObservedArtifactHash)))
(check-sat)
(pop)

; L2.3: closed inputs cannot yield two different semantic next states unless an
; explicit observation/capability difference is present.
(declare-const SameClosedInput Bool)
(declare-const DifferentSemanticNextState Bool)
(declare-const ExplicitExternalDifference Bool)
(assert
  (=>
    (and SameClosedInput DifferentSemanticNextState)
    ExplicitExternalDifference))
(push)
(assert SameClosedInput)
(assert DifferentSemanticNextState)
(assert (not ExplicitExternalDifference))
(check-sat)
(pop)
