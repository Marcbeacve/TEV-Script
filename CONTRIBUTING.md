# Contributing

1. Work on a dedicated `agent/` branch.
2. Do not change a normative schema in place. Introduce a new version.
3. Add positive, negative, budget, tampering, and cross-runtime tests.
4. Prepare the local certification/test environment with
   `python -m pip install -r requirements-certification.txt`.
5. Run `python RUN_PORTABLE_CONFORMANCE.py` before publication.
6. For the 3.1 platform completion candidate, run
   `python RUN_TEV_SCRIPT_PLATFORM_COMPLETION.py` only from a complete clean
   checkout after the certification requirements are present.
7. Keep physical host behavior behind explicit capabilities.
8. Do not add runtime source interpretation, reflection, dynamic code, or
   unbounded loops without a new architectural decision and contract.
9. Open a draft pull request. Do not merge without explicit authorization.

`requirements-certification.txt` is test/certification-only. It must not be
copied into `[project].dependencies`; TEVScript platform release evidence
continues to require `runtime_dependency_count=0`.

GitHub Actions are intentionally absent. Certification is local and receipt
based.
