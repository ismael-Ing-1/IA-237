import type {
  ISODateTime,
} from "./common";

import type {
  Offer,
} from "./offer";


/**
 * Mirrors app.models.negotiation.NegotiationStatus.
 */
export type NegotiationStatus =
  | "open"
  | "negotiating"
  | "agreement_found"
  | "waiting_human"
  | "approved"
  | "rejected"
  | "cancelled"
  | "failed";


/**
 * Mirrors app.models.negotiation.Negotiation.
 */
export interface Negotiation {
  id: string;

  participant_ids: string[];

  offers: Offer[];

  status: NegotiationStatus;

  current_round: number;

  max_rounds: number;

  accepted_offer_id: string | null;

  created_at: ISODateTime;

  updated_at: ISODateTime;
}
