# PyPI wheel registry V1

This file records the canonical TEVScript MAX 3.0.0 release artifact. It exists to prevent confusion between the historical root packaging profile and the dedicated V3 packaging profile.

## Canonical TEVScript MAX release identity

```text
repository                  = Marcbeacve/TEV-Script
release_kind                = STABLE
repository_release          = 3.0.0
language_release            = 3.0.0
tag                         = v3.0.0
release_commit              = edd868cf481c358a2b435eb014af8dfee7ab7417
release_tree                = 5c17d42967965e4f6ec5316bb84d41a75f141edc
stable_admission            = PASS
language_stable             = YES
full_test_count             = 1335
```

The tag `v3.0.0` points to the exact stable-admitted commit above.

## Canonical Python distribution identity for V3

TEVScript V3 does **not** use the repository-root `pyproject.toml` as its release packaging authority. The V3 governed packaging surface is:

```text
packaging/v3/pyproject.toml
packaging/v3/tools/tev_script_build_backend_v3.py
```

At the exact `v3.0.0` release commit, `packaging/v3/pyproject.toml` declares:

```text
project.name                = tev-script-portable-reference
project.version             = 3.0.0
build_backend               = tev_script_build_backend_v3
backend_schema              = TEV_SCRIPT_PYTHON_WHEEL_BACKEND_V3
wheel_tag                   = py3-none-any
runtime_dependencies        = []
```

Therefore the canonical Python publication identity for TEVScript MAX 3.0.0 is:

```text
distribution                = tev-script-portable-reference
python_distribution_version = 3.0.0
wheel                       = tev_script_portable_reference-3.0.0-py3-none-any.whl
wheel_sha256                = 800cab8a9390a44b281fb49a52f796127fa4e6cd2b21043718603899f1137707
pypi                        = https://pypi.org/project/tev-script-portable-reference/3.0.0/
pypi_redownload_byte_match  = PASS
```

The V3 backend reads the dedicated V3 `project.name` and `project.version`, collects the repository `tev_script` Python package, emits deterministic ZIP metadata under `SOURCE_DATE_EPOCH`, and requires zero runtime dependencies.

## Root packaging is not V3 publication authority

The repository-root `pyproject.toml` still declares the historical `1.0.0` package profile. That file remains part of earlier compatibility/product history but **must not be used to infer the V3 wheel identity**.

For V3/MAX publication, the authority order is:

```text
v3 stable-admission receipt
→ packaging/v3/pyproject.toml
→ packaging/v3/tools/tev_script_build_backend_v3.py
→ exact wheel filename + SHA-256
→ PyPI redownload byte identity
```

Do not substitute the root `pyproject.toml` for this V3 packaging boundary.

## Stable admission evidence

```text
technical_parent            = e858097c6610df6d11c58b90728cfb94f5785388
technical_receipt_hash      = e2c9ba26f5ef891229c0796703f6b3e2adf71980491901f7b1832b55e3a46b4d
stable_receipt_hash         = a94a2f336663a0f3b6c4129a239b69063c0c34154306bd0a0fa34c14cb4b80a6
stable_receipt_file_sha256  = fb5f35023c90edab2c4d30b1c88390f7cd65a231eb9a08453ad178f5e4838d5e
stable_wheel_sha256         = 800cab8a9390a44b281fb49a52f796127fa4e6cd2b21043718603899f1137707
```

The external certification receipts remain the authority for the exact release and artifact bytes. This documentation records their identities and does not replace them.

## Anti-confusion rules

- `v3.0.0` is the canonical TEVScript MAX repository/language release tag.
- The canonical V3 Python distribution version is also `3.0.0`, from `packaging/v3/pyproject.toml`.
- The canonical V3 wheel is `tev_script_portable_reference-3.0.0-py3-none-any.whl` with the SHA-256 above.
- The root `pyproject.toml` `1.0.0` profile is not V3 publication authority.
- Never publish different wheel bytes under an already-published distribution version.
- Documentation commits after the release do not alter or supersede `edd868cf...` / `5c17d429...`.
