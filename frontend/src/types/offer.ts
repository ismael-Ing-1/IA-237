import type {
  ISODateTime,
} from "./common";

import type {
  Resource,
  ResourceRequest,
} from "./resource";


/**
 * Mirrors app.models.offer.OfferStatus.
 */
export type OfferStatus =
  | "pending"
  | "accepted"
  | "rejected"
  | "countered"
  | "expired"
  | "cancelled";


/**
 * Mirrors app.models.offer.Offer.
 */
export interface Offer {
  id: string;

  negotiation_id: string | null;

  sender_id: string;

  receiver_id: string;

  offered_resources: Resource[];

  requested_resources: ResourceRequest[];

  status: OfferStatus;

  parent_offer_id: string | null;

  created_at: ISODateTime;

  expires_at: ISODateTime | null;

  message: string | null;
}
