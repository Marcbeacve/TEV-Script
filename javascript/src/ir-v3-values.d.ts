import { Rational, TevScriptError } from "./runtime.mjs";

export type IrV3TypeKind = "primitive" | "unit" | "record" | "enum" | "option" | "result";

export class TypeDescriptorV3 {
  readonly typeId: string;
  readonly kind: IrV3TypeKind;
  readonly fields: readonly (readonly [string, string])[];
  readonly variants: readonly string[];
  readonly argument: string | null;
  readonly okType: string | null;
  readonly errType: string | null;
  fieldType(name: string): string | null;
}

export class RecordValueV3 {
  readonly typeId: string;
  readonly fields: readonly (readonly [string, IrV3RuntimeValue])[];
  constructor(typeId: string, fields: readonly (readonly [string, IrV3RuntimeValue])[]);
  field(name: string): IrV3RuntimeValue;
}

export class VariantValueV3 {
  readonly typeId: string;
  readonly variant: string;
  readonly payload: IrV3RuntimeValue;
  readonly hasPayload: boolean;
  constructor(typeId: string, variant: string, payload?: IrV3RuntimeValue);
}

export type IrV3RuntimeValue =
  | boolean
  | bigint
  | Rational
  | string
  | Rational[]
  | RecordValueV3
  | VariantValueV3;

export class TypeTableV3 {
  readonly descriptors: readonly TypeDescriptorV3[];
  readonly maximumValueNesting: number;
  get(typeId: string): TypeDescriptorV3 | null;
  require(typeId: string, context?: string): TypeDescriptorV3;
  isStorable(typeId: string): boolean;
  variantPayloadType(typeId: string, variant: string): string | null;
}

export function buildTypeTableV3(ir: object): TypeTableV3;
export function decodeV3Value(
  typeId: string,
  raw: unknown,
  table: TypeTableV3,
  options?: {context?: string; depth?: number},
): IrV3RuntimeValue;
export function encodeV3Value(
  typeId: string,
  value: IrV3RuntimeValue,
  table: TypeTableV3,
  options?: {context?: string; depth?: number},
): unknown;
export function v3ValuesEqual(
  typeId: string,
  left: IrV3RuntimeValue,
  right: IrV3RuntimeValue,
  table: TypeTableV3,
): boolean;

export { Rational, TevScriptError };
