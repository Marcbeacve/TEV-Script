# @tev-script/runtime

Portable JavaScript runtime for `TEV_SCRIPT_PROGRAM_IR_V2`.

- no runtime dependencies;
- no Node-only imports in the root runtime, canonicalizer or conformance core;
- exact `BigInt` integers and normalized rationals;
- pure JavaScript SHA-256;
- browser/worker-compatible core when `TextEncoder` is available;
- strict pure JSON parser at `@tev-script/runtime/strict-json`;
- Node file loader at `@tev-script/runtime/strict-json-node`;
- physical behaviour supplied only through named capabilities.

```javascript
import { Rational, ScriptRuntime } from "@tev-script/runtime";

const runtime = new ScriptRuntime(ir, {
  "input.move2d": () => [new Rational(1n), new Rational(0n)],
  "motion.move2d": (delta) => move(delta),
  "animation.play": (name) => animate(name),
  "debug.log": (text) => console.log(text),
});

runtime.invoke("Player", "start");
runtime.invoke("Player", "update");
```

Strict text input:

```javascript
import { parseStrictJson } from "@tev-script/runtime/strict-json";

const ir = parseStrictJson(irText);
```

Distribution verification:

```text
npm test
npm run conformance
```
