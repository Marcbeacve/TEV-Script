/-
TEV Script Axiomatic Semantics V0.
Meta-theory only. The object-level paraconsistent status is represented as data.
-/

import Std

universe u v

namespace TEVScript.AxiomsV0

structure Theory (Field : Type u) (Transformation : Type v) where
  fieldEq : Field → Field → Prop
  transEq : Transformation → Transformation → Prop
  step : Transformation → Field → Field → Prop
  composable : Transformation → Transformation → Prop
  compose : Transformation → Transformation → Transformation

  realize : Transformation
  discover : Transformation
  zeroResidual : Field → Field → Prop

  candidateOf : Field → Field → Prop
  admitted : Field → Field → Prop
  selected : Field → Field → Prop
  proofRequired : Field → Field → Prop
  rejected : Field → Field → Prop
  best : Field → Field → Prop
  indeterminate : Field → Prop
  noAdmissible : Field → Prop

  fieldEq_refl : ∀ x, fieldEq x x
  fieldEq_symm : ∀ {x y}, fieldEq x y → fieldEq y x
  fieldEq_trans : ∀ {x y z}, fieldEq x y → fieldEq y z → fieldEq x z

  transEq_refl : ∀ t, transEq t t
  transEq_symm : ∀ {f g}, transEq f g → transEq g f
  transEq_trans : ∀ {f g h}, transEq f g → transEq g h → transEq f h

  step_trans_congr :
    ∀ {f g}, transEq f g →
      ∀ {x y}, (step f x y ↔ step g x y)

  step_field_congr :
    ∀ {t x x' y y'},
      fieldEq x x' → fieldEq y y' →
      (step t x y ↔ step t x' y')

  step_compose :
    ∀ {g f}, composable g f →
      ∀ {x z},
        (step (compose g f) x z ↔
          ∃ y, step f x y ∧ step g y z)

  trans_extensional :
    ∀ {f g},
      (∀ x y, step f x y ↔ step g x y) →
      transEq f g

  residual_zero_sound :
    ∀ {theory world theory'},
      step realize theory world →
      step discover world theory' →
      zeroResidual theory theory' →
      fieldEq theory theory'

  selected_candidate :
    ∀ {problem candidate},
      selected problem candidate → candidateOf problem candidate

  selected_admitted :
    ∀ {problem candidate},
      selected problem candidate → admitted problem candidate

  selected_not_proofRequired :
    ∀ {problem candidate},
      selected problem candidate → ¬ proofRequired problem candidate

  selected_not_rejected :
    ∀ {problem candidate},
      selected problem candidate → ¬ rejected problem candidate

  noAdmissible_iff :
    ∀ {problem},
      noAdmissible problem ↔
        ∀ candidate, candidateOf problem candidate → rejected problem candidate

  open_admission_indeterminate :
    ∀ {problem},
      (∃ candidate,
        candidateOf problem candidate ∧ proofRequired problem candidate) →
      indeterminate problem

  indeterminate_no_selection :
    ∀ {problem},
      indeterminate problem → ∀ candidate, ¬ selected problem candidate

  tied_distinct_best_indeterminate :
    ∀ {problem left right},
      admitted problem left →
      admitted problem right →
      best problem left →
      best problem right →
      ¬ fieldEq left right →
      indeterminate problem

theorem governed_compose_associative
    {Field : Type u} {Transformation : Type v}
    (T : Theory Field Transformation)
    {f g h : Transformation}
    (hgf : T.composable g f)
    (hhg : T.composable h g)
    (hh_gf : T.composable h (T.compose g f))
    (h_hg_f : T.composable (T.compose h g) f) :
    T.transEq
      (T.compose h (T.compose g f))
      (T.compose (T.compose h g) f) := by
  apply T.trans_extensional
  intro x z
  constructor
  · intro hxz
    have houter := (T.step_compose hh_gf).mp hxz
    cases houter with
    | intro y houterPair =>
      cases houterPair with
      | intro hgfStep hhStep =>
        have hinner := (T.step_compose hgf).mp hgfStep
        cases hinner with
        | intro m hinnerPair =>
          cases hinnerPair with
          | intro hfStep hgStep =>
            apply (T.step_compose h_hg_f).mpr
            exact ⟨m, hfStep, (T.step_compose hhg).mpr ⟨y, hgStep, hhStep⟩⟩
  · intro hxz
    have houter := (T.step_compose h_hg_f).mp hxz
    cases houter with
    | intro m houterPair =>
      cases houterPair with
      | intro hfStep hhgStep =>
        have hinner := (T.step_compose hhg).mp hhgStep
        cases hinner with
        | intro y hinnerPair =>
          cases hinnerPair with
          | intro hgStep hhStep =>
            apply (T.step_compose hh_gf).mpr
            exact ⟨y, (T.step_compose hgf).mpr ⟨m, hfStep, hgStep⟩, hhStep⟩

theorem noAdmissible_no_selection
    {Field : Type u} {Transformation : Type v}
    (T : Theory Field Transformation)
    {problem candidate : Field}
    (hnone : T.noAdmissible problem) :
    ¬ T.selected problem candidate := by
  intro hselected
  have hcandidate := T.selected_candidate hselected
  have hrejected := (T.noAdmissible_iff.mp hnone) candidate hcandidate
  exact (T.selected_not_rejected hselected) hrejected

theorem open_admission_no_selection
    {Field : Type u} {Transformation : Type v}
    (T : Theory Field Transformation)
    {problem openCandidate candidate : Field}
    (hcandidate : T.candidateOf problem openCandidate)
    (hopen : T.proofRequired problem openCandidate) :
    ¬ T.selected problem candidate := by
  have hindeterminate :=
    T.open_admission_indeterminate ⟨openCandidate, hcandidate, hopen⟩
  exact T.indeterminate_no_selection hindeterminate candidate

theorem tied_distinct_best_no_selection
    {Field : Type u} {Transformation : Type v}
    (T : Theory Field Transformation)
    {problem left right candidate : Field}
    (hleftAdmitted : T.admitted problem left)
    (hrightAdmitted : T.admitted problem right)
    (hleftBest : T.best problem left)
    (hrightBest : T.best problem right)
    (hdistinct : ¬ T.fieldEq left right) :
    ¬ T.selected problem candidate := by
  have hindeterminate :=
    T.tied_distinct_best_indeterminate
      hleftAdmitted hrightAdmitted hleftBest hrightBest hdistinct
  exact T.indeterminate_no_selection hindeterminate candidate

theorem selected_is_fail_closed
    {Field : Type u} {Transformation : Type v}
    (T : Theory Field Transformation)
    {problem candidate : Field}
    (hselected : T.selected problem candidate) :
    T.candidateOf problem candidate ∧
      T.admitted problem candidate ∧
      ¬ T.proofRequired problem candidate ∧
      ¬ T.rejected problem candidate := by
  exact ⟨
    T.selected_candidate hselected,
    T.selected_admitted hselected,
    T.selected_not_proofRequired hselected,
    T.selected_not_rejected hselected
  ⟩

theorem zero_residual_cycle_closes
    {Field : Type u} {Transformation : Type v}
    (T : Theory Field Transformation)
    {theory world theory' : Field}
    (hr : T.step T.realize theory world)
    (hd : T.step T.discover world theory')
    (hz : T.zeroResidual theory theory') :
    T.fieldEq theory theory' :=
  T.residual_zero_sound hr hd hz

inductive FourValue where
  | neither
  | trueOnly
  | falseOnly
  | both
  deriving Repr, DecidableEq

def FourValue.support : FourValue → Bool
  | .neither => false
  | .trueOnly => true
  | .falseOnly => false
  | .both => true

def FourValue.refute : FourValue → Bool
  | .neither => false
  | .trueOnly => false
  | .falseOnly => true
  | .both => true

def FourValue.ofPair : Bool → Bool → FourValue
  | false, false => .neither
  | true, false => .trueOnly
  | false, true => .falseOnly
  | true, true => .both

def FourValue.negate (v : FourValue) : FourValue :=
  FourValue.ofPair v.refute v.support

def FourValue.conjunction (a b : FourValue) : FourValue :=
  FourValue.ofPair
    (a.support && b.support)
    (a.refute || b.refute)

def FourValue.disjunction (a b : FourValue) : FourValue :=
  FourValue.ofPair
    (a.support || b.support)
    (a.refute && b.refute)

theorem fourValue_negate_involutive (v : FourValue) :
    v.negate.negate = v := by
  cases v <;> rfl

theorem fourValue_conjunction_commutative (a b : FourValue) :
    a.conjunction b = b.conjunction a := by
  cases a <;> cases b <;> rfl

theorem fourValue_disjunction_commutative (a b : FourValue) :
    a.disjunction b = b.disjunction a := by
  cases a <;> cases b <;> rfl

theorem fourValue_conjunction_associative (a b c : FourValue) :
    (a.conjunction b).conjunction c = a.conjunction (b.conjunction c) := by
  cases a <;> cases b <;> cases c <;> rfl

theorem fourValue_disjunction_associative (a b c : FourValue) :
    (a.disjunction b).disjunction c = a.disjunction (b.disjunction c) := by
  cases a <;> cases b <;> cases c <;> rfl

theorem fourValue_deMorgan_conjunction (a b : FourValue) :
    (a.conjunction b).negate = a.negate.disjunction b.negate := by
  cases a <;> cases b <;> rfl

theorem fourValue_deMorgan_disjunction (a b : FourValue) :
    (a.disjunction b).negate = a.negate.conjunction b.negate := by
  cases a <;> cases b <;> rfl

theorem both_keeps_support_and_refutation :
    FourValue.both.support = true ∧ FourValue.both.refute = true := by
  exact ⟨rfl, rfl⟩

inductive Judgment where
  | pass
  | reject
  | proofRequired
  deriving Repr, DecidableEq

inductive Resolution where
  | selected
  | indeterminate
  | noAdmissible
  deriving Repr, DecidableEq

def mayCommit : Judgment → Bool
  | .pass => true
  | .reject => false
  | .proofRequired => false

theorem proofRequired_cannot_commit :
    mayCommit .proofRequired = false := rfl

theorem reject_cannot_commit :
    mayCommit .reject = false := rfl

structure MetadataModelField where
  semanticTag : Nat
  backendTag : Nat
  costTag : Nat
  deriving Repr, DecidableEq

def metadataSemEq (a b : MetadataModelField) : Prop :=
  a.semanticTag = b.semanticTag

def modelA : MetadataModelField := ⟨0, 0, 0⟩
def modelB : MetadataModelField := ⟨0, 1, 1⟩
def modelC : MetadataModelField := ⟨1, 0, 0⟩

theorem metadata_noncollapse_same_semantics :
    metadataSemEq modelA modelB := rfl

theorem metadata_noncollapse_backend_cost_not_semantics :
    ¬ metadataSemEq modelA modelC := by
  decide

end TEVScript.AxiomsV0
