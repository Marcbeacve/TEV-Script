export type TevTypeName =
  | "Bool"
  | "Int"
  | "Rat"
  | "Text"
  | "Vec2"
  | "Vec3"
  | "Unit";

export class Rational {
  readonly numerator: bigint;
  readonly denominator: bigint;
  constructor(numerator: bigint | number | string, denominator?: bigint | number | string);
  static from(value: Rational | bigint | number | string): Rational;
  add(other: Rational | bigint | number | string): Rational;
  sub(other: Rational | bigint | number | string): Rational;
  mul(other: Rational | bigint | number | string): Rational;
  div(other: Rational | bigint | number | string): Rational;
  neg(): Rational;
  compare(other: Rational | bigint | number | string): number;
  equals(other: unknown): boolean;
}

export class TevScriptError extends Error {
  readonly code: string;
  constructor(code: string, message: string);
}

export type TevRuntimeValue =
  | boolean
  | bigint
  | Rational
  | string
  | Rational[]
  | null;

export type TevCapability = (...arguments_: TevRuntimeValue[]) => TevRuntimeValue;

export interface EmittedEvent {
  entity_id: string;
  event_id: string;
  arguments: TevRuntimeValue[];
}

export class ScriptRuntime {
  constructor(ir: object, capabilities?: Record<string, TevCapability>);
  readonly emitted: EmittedEvent[];
  invoke(entityId: string, eventId: string, ...arguments_: TevRuntimeValue[]): EmittedEvent[];
  encodedState(entityId: string): Record<string, {type: TevTypeName; value: unknown}>;
}

export function encodeTypedValue(typeName: TevTypeName, value: TevRuntimeValue): unknown;
export const IR_SCHEMA: "TEV_SCRIPT_PROGRAM_IR_V2";
export const LANGUAGE_VERSION: "0.2.0";

export function validateProgramIr(ir: object): void;
