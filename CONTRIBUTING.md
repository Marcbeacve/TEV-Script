# Contributing

1. Work on a dedicated `agent/` branch.
2. Do not change a normative schema in place. Introduce a new version.
3. Add positive, negative, budget, tampering, and cross-runtime tests.
4. Run `python RUN_PORTABLE_CONFORMANCE.py` before publication.
5. Keep physical host behavior behind explicit capabilities.
6. Do not add runtime source interpretation, reflection, dynamic code, or
   unbounded loops without a new architectural decision and contract.
7. Open a draft pull request. Do not merge without explicit authorization.

GitHub Actions are intentionally absent. Certification is local and receipt
based.
