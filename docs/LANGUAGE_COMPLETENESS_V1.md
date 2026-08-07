# TEV Script Language Completeness V1

Language version `0.2.0` remains intentionally bounded. Completeness means that the accepted source/IR domain and runtime behavior are closed and portable; it does not mean adopting general-purpose features outside the V0.2 boundary.

Closure criteria:

- source lexical and grammar authority is complete;
- static semantics is normative;
- successful source compilation must emit runtime-admissible IR;
- portable capabilities remain the default catalog while typed host catalogs are extensible without compiler mutation;
- IR V2 has normative operational semantics and a typed acyclic CFG verifier;
- canonical runtime invocation/binding ids are rejected rather than silently normalized;
- the shared eight-case negative corpus is rejected by Python, JavaScript and C# with `TEVS_IR_FLOW_INVALID`;
- the existing positive language receipts remain byte-identical;
- Browser-WASM and WASI recompile the changed C# Core under AOT/trimming.

Explicit non-goals of V0.2: modules/imports, loops, recursion, async capabilities, reflection, runtime source compilation, self-assembly, decentralized consensus and stable release promotion.
