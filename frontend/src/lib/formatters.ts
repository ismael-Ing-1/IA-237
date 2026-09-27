import type {
  AgentAction,
} from "../types/agent";

import type {
  NegotiationStatus,
} from "../types/negotiation";

import type {
  OfferStatus,
} from "../types/offer";

import type {
  Resource,
  ResourceRequest,
} from "../types/resource";

import type {
  EventType,
} from "../types/simulation";

import {
  AGENT_ACTION_LABELS,
  EVENT_TYPE_LABELS,
  NEGOTIATION_STATUS_LABELS,
  OFFER_STATUS_LABELS,
} from "./constants";

import {
  humanize,
} from "./utils";


/**
 * Formats a number while avoiding unnecessary decimal zeros.
 */
export function formatNumber(
  value: number,
  options: {
    maximumFractionDigits?: number;
    minimumFractionDigits?: number;
  } = {},
): string {
  return new Intl.NumberFormat(
    undefined,
    {
      maximumFractionDigits:
        options.maximumFractionDigits ??
        2,

      minimumFractionDigits:
        options.minimumFractionDigits ??
        0,
    },
  ).format(value);
}


/**
 * Formats a reputation / score in the [0, 1] range.
 *
 * Example:
 * 0.923 -> "92%"
 */
export function formatScore(
  value: number,
): string {
  return `${Math.round(
    value * 100,
  )}%`;
}


/**
 * Formats an ISO datetime with the current browser locale.
 */
export function formatDateTime(
  value:
    | string
    | Date
    | null
    | undefined,
): string {
  if (!value) {
    return "—";
  }

  const date =
    value instanceof Date
      ? value
      : new Date(value);

  if (
    Number.isNaN(
      date.getTime(),
    )
  ) {
    return "Invalid date";
  }

  return date.toLocaleString(
    [],
    {
      year: "numeric",
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    },
  );
}


/**
 * Formats only the time component.
 */
export function formatTime(
  value:
    | string
    | Date
    | null
    | undefined,
): string {
  if (!value) {
    return "--:--";
  }

  const date =
    value instanceof Date
      ? value
      : new Date(value);

  if (
    Number.isNaN(
      date.getTime(),
    )
  ) {
    return "--:--";
  }

  return date.toLocaleTimeString(
    [],
    {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    },
  );
}


/**
 * Formats only the date component.
 */
export function formatDate(
  value:
    | string
    | Date
    | null
    | undefined,
): string {
  if (!value) {
    return "—";
  }

  const date =
    value instanceof Date
      ? value
      : new Date(value);

  if (
    Number.isNaN(
      date.getTime(),
    )
  ) {
    return "Invalid date";
  }

  return date.toLocaleDateString(
    [],
    {
      year: "numeric",
      month: "short",
      day: "2-digit",
    },
  );
}


/**
 * Formats a duration in seconds into a compact readable value.
 */
export function formatDuration(
  totalSeconds: number,
): string {
  const seconds = Math.max(
    0,
    Math.floor(
      totalSeconds,
    ),
  );

  if (seconds < 60) {
    return `${seconds}s`;
  }

  const minutes =
    Math.floor(
      seconds / 60,
    );

  const remainingSeconds =
    seconds % 60;

  if (minutes < 60) {
    return remainingSeconds > 0
      ? `${minutes}m ${remainingSeconds}s`
      : `${minutes}m`;
  }

  const hours =
    Math.floor(
      minutes / 60,
    );

  const remainingMinutes =
    minutes % 60;

  if (hours < 24) {
    return remainingMinutes > 0
      ? `${hours}h ${remainingMinutes}m`
      : `${hours}h`;
  }

  const days =
    Math.floor(
      hours / 24,
    );

  const remainingHours =
    hours % 24;

  return remainingHours > 0
    ? `${days}d ${remainingHours}h`
    : `${days}d`;
}


/**
 * Formats a resource or resource request.
 *
 * Example:
 * H100 · 8 gpu-hour
 */
export function formatResource(
  resource:
    | Resource
    | ResourceRequest,
): string {
  return [
    resource.resource_type,
    "·",
    formatNumber(
      resource.quantity,
    ),
    resource.unit,
  ].join(" ");
}


/**
 * Formats a list of resources.
 */
export function formatResources(
  resources: Array<
    Resource | ResourceRequest
  >,
): string {
  if (
    resources.length === 0
  ) {
    return "None";
  }

  return resources
    .map(formatResource)
    .join(", ");
}


/**
 * Shortens technical identifiers for compact UI display.
 *
 * Full IDs should still be used internally.
 */
export function formatEntityId(
  id:
    | string
    | null
    | undefined,
  visibleCharacters = 8,
): string {
  if (!id) {
    return "—";
  }

  if (
    id.length <=
    visibleCharacters
  ) {
    return id;
  }

  return `${id.slice(
    0,
    visibleCharacters,
  )}…`;
}


export function formatNegotiationStatus(
  status: NegotiationStatus,
): string {
  return (
    NEGOTIATION_STATUS_LABELS[
      status
    ] ??
    humanize(status)
  );
}


export function formatOfferStatus(
  status: OfferStatus,
): string {
  return (
    OFFER_STATUS_LABELS[
      status
    ] ??
    humanize(status)
  );
}


export function formatAgentAction(
  action: AgentAction,
): string {
  return (
    AGENT_ACTION_LABELS[
      action
    ] ??
    humanize(action)
  );
}


export function formatEventType(
  eventType: EventType,
): string {
  return (
    EVENT_TYPE_LABELS[
      eventType
    ] ??
    humanize(eventType)
  );
}


/**
 * Returns a friendly relative-time label.
 *
 * Example:
 * "in 5m"
 * "3m ago"
 */
export function formatRelativeTime(
  target:
    | string
    | Date,
  base:
    | string
    | Date = new Date(),
): string {
  const targetDate =
    target instanceof Date
      ? target
      : new Date(target);

  const baseDate =
    base instanceof Date
      ? base
      : new Date(base);

  const differenceSeconds =
    Math.round(
      (
        targetDate.getTime() -
        baseDate.getTime()
      ) / 1000,
    );

  const absoluteSeconds =
    Math.abs(
      differenceSeconds,
    );

  let value: number;
  let unit:
    | Intl.RelativeTimeFormatUnit;

  if (
    absoluteSeconds <
    60
  ) {
    value = differenceSeconds;
    unit = "second";
  } else if (
    absoluteSeconds <
    3600
  ) {
    value =
      Math.round(
        differenceSeconds /
          60,
      );
    unit = "minute";
  } else if (
    absoluteSeconds <
    86400
  ) {
    value =
      Math.round(
        differenceSeconds /
          3600,
      );
    unit = "hour";
  } else {
    value =
      Math.round(
        differenceSeconds /
          86400,
      );
    unit = "day";
  }

  return new Intl.RelativeTimeFormat(
    undefined,
    {
      numeric: "auto",
    },
  ).format(
    value,
    unit,
  );
}
