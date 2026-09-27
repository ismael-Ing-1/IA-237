import { useActivityStore } from "../store/activity.store";
import { useUIStore } from "../store/ui.store";
import { eventNegotiationId, usePresentationStore } from "../store/presentation.store";
import type { WebSocketEvent } from "../types/websocket";

const rawDelay = Number(import.meta.env.VITE_ACTIVITY_FEED_DELAY_MS);
const defaultDelay = Number.isFinite(rawDelay) && rawDelay >= 0 ? Math.min(rawDelay, 3000) : 450;

/** Une seule horloge de présentation pour le journal, les offres et le point d'approbation.
 * Aucun retard ajouté aux commandes HTTP ou aux contrôles de sécurité.
 */
export class ActivityPresentationQueue {
  private queue: WebSocketEvent[] = [];
  private timer: ReturnType<typeof setTimeout> | null = null;
  constructor(readonly delayMs = defaultDelay) {}

  enqueue(event: WebSocketEvent, urgent = false): void {
    this.queue.push(event);
    usePresentationStore.getState().setPendingCount(this.queue.length);
    if (urgent || this.queue.length > 500) { this.flush(); return; }
    if (this.timer === null) this.showNext();
  }

  clear(): void {
    this.queue = [];
    if (this.timer !== null) clearTimeout(this.timer);
    this.timer = null;
    usePresentationStore.getState().setPendingCount(0);
  }

  flush(): void {
    if (this.timer !== null) clearTimeout(this.timer);
    this.timer = null;
    while (this.queue.length > 0) this.deliver(this.queue.shift()!);
    usePresentationStore.getState().setPendingCount(0);
  }

  private deliver(event: WebSocketEvent): void {
    useActivityStore.getState().addFromWebSocketEvent(event);
    usePresentationStore.getState().present(event);
    const id = eventNegotiationId(event);
    if (!id) return;
    const ui = useUIStore.getState();
    const contextChanged = event.type === "negotiation_started" && event.user_id === ui.selectedUserId;
    if (ui.selectedNegotiationId === null || contextChanged) ui.selectNegotiation(id);
    // L'ouverture de la modal est dérivée dans DashboardPage du point présenté
    // ET de l'état REST courant, jamais d'un événement historique isolé.
  }

  private showNext(): void {
    const event = this.queue.shift();
    if (!event) { this.timer = null; return; }
    this.deliver(event);
    usePresentationStore.getState().setPendingCount(this.queue.length);
    this.timer = setTimeout(() => { this.timer = null; this.showNext(); }, this.delayMs);
  }
}

export const activityPresentationQueue = new ActivityPresentationQueue();
if (import.meta.hot) import.meta.hot.dispose(() => activityPresentationQueue.clear());
