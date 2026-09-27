import { create } from "zustand";
import type { Negotiation, NegotiationStatus } from "../types/negotiation";
import type { Offer } from "../types/offer";
import type { WebSocketEvent } from "../types/websocket";

const object = (v: unknown): Record<string, unknown> | null =>
  v !== null && typeof v === "object" && !Array.isArray(v) ? v as Record<string, unknown> : null;

export function eventNegotiationId(event: WebSocketEvent): string | null {
  const p = object(event.payload);
  if (typeof p?.negotiation_id === "string") return p.negotiation_id;
  const n = object(p?.negotiation);
  if (typeof n?.id === "string") return n.id;
  const d = object(p?.decision);
  if (typeof d?.negotiation_id === "string") return d.negotiation_id;
  const relevant = /^(negotiation_|offer_|human_|exchange_|mediation_)/.test(event.type) ||
    event.type === "counter_offer_sent";
  return relevant ? event.entity_id : null;
}

function snapshot(event: WebSocketEvent): Negotiation | null {
  const value = object(object(event.payload)?.negotiation);
  return value && typeof value.id === "string" && Array.isArray(value.participant_ids) &&
    Array.isArray(value.offers) && typeof value.status === "string"
    ? value as unknown as Negotiation : null;
}

export const isClosedStatus = (status: NegotiationStatus) =>
  ["rejected", "cancelled", "failed"].includes(status);

export function isUrgentEvent(event: WebSocketEvent): boolean {
  const n = snapshot(event);
  return ["human_rejected", "human_approved", "exchange_completed", "exchange_failed", "error"].includes(event.type) ||
    (n !== null && isClosedStatus(n.status));
}

export interface PresentedNegotiation {
  snapshot: Negotiation | null;
  readyOfferId: string | null;
  resolved: boolean;
}

interface PresentationState {
  tracked: Record<string, PresentedNegotiation>;
  pendingCount: number;
  track: (id: string) => void;
  observe: (event: WebSocketEvent) => void;
  present: (event: WebSocketEvent) => void;
  confirm: (negotiation: Negotiation) => void;
  setPendingCount: (count: number) => void;
  reset: () => void;
  releaseUnannounced: () => void;
}

const blank = (): PresentedNegotiation => ({ snapshot: null, readyOfferId: null, resolved: false });

/** Projection de lecture uniquement. Les commandes utilisent toujours le cache REST à jour. */
export const usePresentationStore = create<PresentationState>((set) => ({
  tracked: {}, pendingCount: 0,
  track: (id) => set((s) => s.tracked[id] ? s : { tracked: { ...s.tracked, [id]: blank() } }),
  observe: (event) => {
    const id = eventNegotiationId(event);
    if (!id) return;
    set((s) => {
      const entry = s.tracked[id] ?? blank();
      const n = snapshot(event);
      const resolution = ["human_rejected", "human_approved", "exchange_completed"].includes(event.type) ||
        (n !== null && isClosedStatus(n.status));
      // Un refus reçu annule immédiatement les anciens points d'approbation,
      // même si des événements historiques attendent encore dans le lecteur.
      return { tracked: { ...s.tracked, [id]: resolution ? {
        snapshot: n ?? entry.snapshot, readyOfferId: null, resolved: true,
      } : entry } };
    });
  },
  present: (event) => {
    const id = eventNegotiationId(event);
    if (!id) return;
    set((s) => {
      const entry = s.tracked[id] ?? blank();
      if (entry.resolved && !isUrgentEvent(event)) return s;
      const n = snapshot(event);
      let shown = n ?? entry.snapshot;
      const p = object(event.payload);
      const offer = object(p?.offer);
      if (shown && offer && typeof offer.id === "string" && Array.isArray(offer.offered_resources)) {
        const typedOffer = offer as unknown as Offer;
        const exists = shown.offers.some((item) => item.id === typedOffer.id);
        const offers = shown.offers.map((item) => item.id === typedOffer.id ? typedOffer :
          item.id === typedOffer.parent_offer_id ? { ...item, status: "countered" as const } : item);
        if (!exists) offers.push(typedOffer);
        shown = { ...shown, offers, current_round: Math.max(shown.current_round, offers.length) };
        if (event.type === "offer_accepted") shown = {
          ...shown, status: "agreement_found", accepted_offer_id: typedOffer.id,
        };
        else if (event.type === "counter_offer_sent") shown = { ...shown, status: "negotiating" };
      }
      const readyOfferId = event.type === "human_approval_required" && shown?.status === "waiting_human"
        ? shown.accepted_offer_id : entry.readyOfferId;
      return { tracked: { ...s.tracked, [id]: {
        snapshot: shown, resolved: entry.resolved,
        readyOfferId: entry.resolved ? null : readyOfferId,
      } } };
    });
  },
  confirm: (negotiation) => set((s) => ({ tracked: { ...s.tracked, [negotiation.id]: {
    snapshot: negotiation, readyOfferId: null, resolved: true,
  } } })),
  setPendingCount: (pendingCount) => set({ pendingCount }),
  reset: () => set({ tracked: {}, pendingCount: 0 }),
  releaseUnannounced: () => set((s) => ({ tracked: Object.fromEntries(
    Object.entries(s.tracked).filter(([, value]) => value.snapshot !== null),
  ) })),
}));

export function displayedNegotiation(
  live: Negotiation | null | undefined,
  tracked: PresentationState["tracked"],
): Negotiation | null {
  if (!live) return null;
  // La vérité terminale prime sur une lecture différée. Ne jamais montrer un refus comme approuvable.
  if (isClosedStatus(live.status) || live.status === "approved") return live;
  return tracked[live.id] ? tracked[live.id].snapshot : live;
}

export function approvalIsReady(live: Negotiation | null | undefined, tracked: PresentationState["tracked"]): boolean {
  if (!live || live.status !== "waiting_human" || !live.accepted_offer_id) return false;
  const entry = tracked[live.id];
  // Après chargement/reconnexion, un snapshot REST non rejoué peut être examiné directement.
  return !entry || (!entry.resolved && entry.readyOfferId === live.accepted_offer_id);
}
