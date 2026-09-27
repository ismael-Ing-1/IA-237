/**
 * ISO-8601 datetime serialized by FastAPI/Pydantic.
 *
 * Example:
 * "2026-09-26T14:30:00+00:00"
 */
export type ISODateTime = string;


/**
 * Generic JSON-like metadata object.
 *
 * The backend intentionally allows flexible resource/event attributes.
 */
export type Metadata = Record<string, unknown>;
