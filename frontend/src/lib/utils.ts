/**
 * Generic frontend helpers.
 *
 * This file intentionally has no dependency on React or external packages.
 */


/**
 * Joins truthy class names.
 *
 * Example:
 *
 * cn(
 *   "rounded-xl",
 *   active && "border-cyan-400",
 *   disabled && "opacity-50",
 * )
 */
export function cn(
  ...values: Array<
    | string
    | false
    | null
    | undefined
  >
): string {
  return values
    .filter(Boolean)
    .join(" ");
}


/**
 * Clamps a numeric value between min and max.
 */
export function clamp(
  value: number,
  min: number,
  max: number,
): number {
  return Math.min(
    Math.max(value, min),
    max,
  );
}


/**
 * Returns a value between 0 and 1.
 */
export function normalizeScore(
  value: number,
): number {
  return clamp(
    value,
    0,
    1,
  );
}


/**
 * Generates a browser-side temporary ID.
 *
 * Backend-generated entity IDs remain authoritative.
 * This helper is only for temporary UI objects/forms/events.
 */
export function createLocalId(
  prefix = "local",
): string {
  if (
    typeof crypto !== "undefined" &&
    "randomUUID" in crypto
  ) {
    return `${prefix}-${crypto.randomUUID()}`;
  }

  return [
    prefix,
    Date.now(),
    Math.random()
      .toString(36)
      .slice(2),
  ].join("-");
}


/**
 * Type-safe helper for exhaustive switch statements.
 */
export function assertNever(
  value: never,
  message = "Unexpected value",
): never {
  throw new Error(
    `${message}: ${String(value)}`,
  );
}


/**
 * Removes null and undefined values from an object.
 *
 * Useful before sending query parameters.
 */
export function compactObject<
  T extends Record<
    string,
    unknown
  >,
>(
  object: T,
): Partial<T> {
  return Object.fromEntries(
    Object.entries(
      object,
    ).filter(
      (
        [, value],
      ) =>
        value !== null &&
        value !== undefined,
    ),
  ) as Partial<T>;
}


/**
 * Returns the last item of an array.
 */
export function lastItem<T>(
  values: readonly T[],
): T | undefined {
  return values[
    values.length - 1
  ];
}


/**
 * Simple stable sort helper.
 *
 * Native Array.sort mutates the array. This function does not.
 */
export function sortedCopy<T>(
  values: readonly T[],
  compare: (
    a: T,
    b: T,
  ) => number,
): T[] {
  return [...values].sort(
    compare,
  );
}


/**
 * Capitalizes the first character of a string.
 */
export function capitalize(
  value: string,
): string {
  if (!value) {
    return value;
  }

  return (
    value.charAt(0).toUpperCase() +
    value.slice(1)
  );
}


/**
 * Converts snake_case or kebab-case to a readable label.
 *
 * Example:
 * "waiting_human" -> "Waiting Human"
 */
export function humanize(
  value: string,
): string {
  return value
    .replace(
      /[_-]+/g,
      " ",
    )
    .replace(
      /\b\w/g,
      (character) =>
        character.toUpperCase(),
    );
}


/**
 * Checks whether a string is non-empty after trimming.
 */
export function isNonEmptyString(
  value: unknown,
): value is string {
  return (
    typeof value === "string" &&
    value.trim().length > 0
  );
}
