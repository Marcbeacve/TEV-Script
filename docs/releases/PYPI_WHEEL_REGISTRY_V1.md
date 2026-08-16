# PyPI wheel registry V1

This file records the stable TEVScript repository/language release and the Python distribution artifact as **separate identities**. This distinction is intentional and must be preserved to avoid confusing the TEVScript language version with the Python package version.

## Repository / language release identity

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
stable_wheel_sha256         = 800cab8a9390a44b281fb49a52f796127fa4e6cd2b21043718603899f1137707
```

The tag `v3.0.0` points to the exact stable-admitted commit above.

## Python distribution identity

At the exact `v3.0.0` source commit, `pyproject.toml` declares:

```text
project.name                = tev-script-portable-reference
project.version             = 1.0.0
```

The in-tree build backend reads `project.name` and `project.version` directly to form the wheel filename. Therefore the Python distribution identity associated with this tagged source is:

```text
distribution                = tev-script-portable-reference
python_distribution_version = 1.0.0
wheel                       = tev_script_portable_reference-1.0.0-py3-none-any.whl
wheel_sha256                = 800cab8a9390a44b281fb49a52f796127fa4e6cd2b21043718603899f1137707
pypi                        = https://pypi.org/project/tev-script-portable-reference/1.0.0/
```

## Why there are two version numbers

`3.0.0` identifies the TEVScript MAX language/repository release. `1.0.0` is the Python package version declared by the tagged source and consumed by the deterministic wheel backend. They are not interchangeable fields.

Do **not** infer a wheel named `tev_script_portable_reference-3.0.0-py3-none-any.whl` merely from the Git tag `v3.0.0`. A Python wheel version must be read from the package metadata or an exact publication receipt, not from the repository tag.

## Stable admission evidence

```text
technical_parent            = e858097c6610df6d11c58b90728cfb94f5785388
technical_receipt_hash      = e2c9ba26f5ef891229c0796703f6b3e2adf71980491901f7b1832b55e3a46b4d
stable_receipt_hash         = a94a2f336663a0f3b6c4129a239b69063c0c34154306bd0a0fa34c14cb4b80a6
stable_receipt_file_sha256  = fb5f35023c90edab2c4d30b1c88390f7cd65a231eb9a08453ad178f5e4838d5e
```

The external certification receipts remain the authority for the exact release and artifact bytes. This documentation records their identities and does not replace them.

## Anti-confusion rules

- `v3.0.0` is the **TEVScript language/repository release tag**.
- `1.0.0` is the **Python distribution version declared at that exact tag**.
- Never derive a Python wheel filename from the repository tag alone.
- Never publish different wheel bytes under an already-published Python distribution version.
- Documentation commits after the release do not alter or supersede `edd868cf...` / `5c17d429...`.
