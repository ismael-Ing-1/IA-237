import { useEffect, useMemo, useRef, useState } from "react";
import { ErrorState, LoadingSpinner, Panel } from "../components";
import {
  AgentActivityFeed, AgentPanel, ApprovalModal, BottomPanel, DashboardHeader,
  DashboardLayout, EventHistory, GoalComposer, LeftPanel, MarketGraph, MarketLegend,
  NegotiationPanel, RightPanel, SimulationControls, UpcomingEvents,
} from "../features";
import type { GoalComposerValue } from "../features/agents/GoalComposer";
import { CoalitionPanel } from "../features/coalitions/CoalitionPanel";
import { CoalitionApprovalModal } from "../features/coalitions/CoalitionApprovalModal";
import { useAgent, useNegotiation, useSimulation, useUserDashboard } from "../hooks";
import { useStopAgentObjective } from "../hooks/useAgentRuntime";
import { useCoalitionActions } from "../hooks/useCoalition";
import { useActivityStore, useUIStore } from "../store";
import {
  approvalIsReady, displayedNegotiation, isClosedStatus, usePresentationStore,
} from "../store/presentation.store";
import type { AgentAction, CoalitionDeal, RankedCoalition } from "../types/agent";
import type { AgentRuntimeState, RuntimeSimulationState } from "../types/runtime";
import type { Negotiation } from "../types/negotiation";
import type { ResourceRequest } from "../types/resource";
import { useRealtimeConnected } from "../websocket";
import { activityPresentationQueue } from "../websocket/activityQueue";

const errorMessage = (error: unknown) => error instanceof Error ? error.message : "Unexpected error.";
const actionForStatus: Partial<Record<AgentRuntimeState["status"], AgentAction>> = {
  searching: "search_market", negotiating: "start_negotiation", waiting_human: "wait_human",
  searching_coalition: "search_coalition", coalition_proposed: "search_coalition",
  coalition_validating: "search_coalition", coalition_waiting_humans: "wait_human",
  coalition_approved: "accept", approved: "accept", exhausted: "stop", failed: "stop", cancelled: "stop", completed: "stop",
};

/** Une ligne du journal est un événement passé, jamais l'état courant d'un agent. */
function currentAction(
  runtime: AgentRuntimeState | undefined,
  negotiations: Negotiation[],
  tracked: ReturnType<typeof usePresentationStore.getState>["tracked"],
  selected: Negotiation | null,
  snapshotFallback: boolean,
): AgentAction | null {
  if (runtime) {
    const live = negotiations.find((n) => n.id === runtime.negotiation_id);
    if (runtime.status === "waiting_human") {
      if (!live || isClosedStatus(live.status) || live.status === "approved") return "stop";
      if (snapshotFallback && live.status === "waiting_human") return "wait_human";
      if (!approvalIsReady(live, tracked)) {
        const shown = displayedNegotiation(live, tracked);
        return shown?.status === "agreement_found" ? "accept" : "start_negotiation";
      }
    }
    return actionForStatus[runtime.status] ?? null;
  }
  if (!selected) return null;
  if (isClosedStatus(selected.status)) return "stop";
  if (selected.status === "waiting_human") {
    return snapshotFallback || approvalIsReady(selected, tracked)
      ? "wait_human"
      : "start_negotiation";
  }
  if (selected.status === "approved" || selected.status === "agreement_found") return "accept";
  return "start_negotiation";
}

function activityEventType(activity: { metadata?: Record<string, unknown> }): string | null {
  const value = activity.metadata?.event_type;
  return typeof value === "string" ? value : null;
}

function activityEntityId(activity: { metadata?: Record<string, unknown> }): string | null {
  const value = activity.metadata?.entity_id;
  return typeof value === "string" ? value : null;
}

function projectedCoalitionDeal(
  deal: CoalitionDeal,
  activities: ReturnType<typeof useActivityStore.getState>["activities"],
  snapshotFallback: boolean,
): CoalitionDeal {
  if (snapshotFallback) return deal;

  const events = activities.filter((activity) => activityEntityId(activity) === deal.id);
  const evaluated = new Set(
    events.filter((activity) => activityEventType(activity) === "coalition_agent_evaluated")
      .map((activity) => activity.user_id).filter((id): id is string => typeof id === "string"),
  );
  const approvedHumans = new Set(
    events.filter((activity) => activityEventType(activity) === "coalition_human_approved")
      .map((activity) => activity.user_id).filter((id): id is string => typeof id === "string"),
  );
  const humanRejectionRevealed = events.some(
    (activity) => activityEventType(activity) === "coalition_human_rejected",
  );

  let status = deal.status;
  const hasSelected = events.some((activity) => activityEventType(activity) === "coalition_selected");
  const hasApprovalCheckpoint = events.some((activity) => activityEventType(activity) === "coalition_human_approval_required");
  const hasApproved = events.some((activity) => activityEventType(activity) === "coalition_approved");
  const hasExecutionStarted = events.some((activity) => activityEventType(activity) === "coalition_exchange_started");
  const hasExecutionCompleted = events.some((activity) => activityEventType(activity) === "coalition_exchange_completed");
  const hasTerminalFailure = events.some((activity) => [
    "coalition_rejected", "coalition_human_rejected", "coalition_cancelled", "coalition_exchange_failed",
  ].includes(activityEventType(activity) ?? ""));

  if (deal.status === "waiting_humans" && !hasApprovalCheckpoint) status = hasSelected ? "agent_validating" : "agent_validating";
  if (deal.status === "approved" && !hasApproved) status = "waiting_humans";
  if (deal.status === "executing" && !hasExecutionStarted) status = "approved";
  if (deal.status === "completed" && !hasExecutionCompleted) status = hasExecutionStarted ? "executing" : "approved";
  if (["rejected", "cancelled", "failed"].includes(deal.status) && !hasTerminalFailure) {
    status = hasApprovalCheckpoint ? "waiting_humans" : "agent_validating";
  }

  const humanApprovals = Object.fromEntries(
    deal.proposal.participant_ids.map((userId) => [
      userId,
      approvedHumans.has(userId)
        ? true
        : (humanRejectionRevealed && deal.human_approvals[userId] === false ? false : null),
    ]),
  );

  const evaluations = Object.fromEntries(
    Object.entries(deal.agent_evaluations).filter(([userId]) => evaluated.has(userId)),
  );

  return { ...deal, status, agent_evaluations: evaluations, human_approvals: humanApprovals };
}

export default function DashboardPage() {
  const connected = useRealtimeConnected();
  const simulation = useSimulation();
  const selectedUserId = useUIStore((s) => s.selectedUserId);
  const selectedNegotiationId = useUIStore((s) => s.selectedNegotiationId);
  const isApprovalModalOpen = useUIStore((s) => s.isApprovalModalOpen);
  const selectUser = useUIStore((s) => s.selectUser);
  const selectNegotiation = useUIStore((s) => s.selectNegotiation);
  const openApprovalModal = useUIStore((s) => s.openApprovalModal);
  const closeApprovalModal = useUIStore((s) => s.closeApprovalModal);
  const activities = useActivityStore((s) => s.activities);
  const tracked = usePresentationStore((s) => s.tracked);
  const pendingCount = usePresentationStore((s) => s.pendingCount);
  const userDashboard = useUserDashboard(selectedUserId);
  const agent = useAgent(selectedUserId);
  const negotiation = useNegotiation(selectedNegotiationId);
  const stop = useStopAgentObjective();
  const coalitionActions = useCoalitionActions();
  const [commandError, setCommandError] = useState<string | null>(null);
  const [draftNeed, setDraftNeed] = useState<ResourceRequest | null>(null);
  const [coalitionApprovalModalOpen, setCoalitionApprovalModalOpen] = useState(false);
  const dismissed = useRef(new Set<string>());
  const dismissedCoalitions = useRef(new Set<string>());

  useEffect(() => {
    setCommandError(null);
  }, [selectedUserId]);

  // Une reconnexion sans replay reprend le snapshot REST, pas un vieux WAIT_HUMAN.
  useEffect(() => {
    if (!connected) {
      activityPresentationQueue.flush();
      usePresentationStore.getState().reset();
    }
  }, [connected]);

  useEffect(() => {
    if (!simulation.isSuccess) return;
    if (!simulation.users.some((user) => user.user_id === selectedUserId)) {
      selectUser(simulation.users[0]?.user_id ?? null);
      dismissed.current.clear();
    }
  }, [simulation.isSuccess, simulation.users, selectedUserId, selectUser]);

  const allNegotiations = useMemo(() => [
    ...simulation.activeNegotiations, ...simulation.completedNegotiations,
  ], [simulation.activeNegotiations, simulation.completedNegotiations]);

  // WebSocket does not replay the complete historical event stream after a reload.
  // CONNECTED / MARKET_UPDATED alone therefore mean: render the authoritative REST
  // snapshot immediately instead of waiting forever for old presentation events.
  const hasPresentedBusinessEvent = activities.some((activity) => {
    const type = activityEventType(activity);
    return type !== null && ![
      "connected",
      "market_updated",
      "simulation_time_updated",
    ].includes(type);
  });

  const snapshotFallback =
    !connected || (pendingCount === 0 && !hasPresentedBusinessEvent);

  const visibleNegotiations = useMemo(() => {
    if (snapshotFallback) return simulation.activeNegotiations;

    return simulation.activeNegotiations
      .map((item) => displayedNegotiation(item, tracked))
      .filter((item): item is Negotiation => item !== null);
  }, [simulation.activeNegotiations, tracked, snapshotFallback]);
  const coalitionWasRevealed = (deal: CoalitionDeal) => snapshotFallback || activities.some((activity) =>
    activityEntityId(activity) === deal.id && activityEventType(activity) === "coalition_found");
  const coalitionClosureWasRevealed = (deal: CoalitionDeal) => activities.some((activity) =>
    activityEntityId(activity) === deal.id && [
      "coalition_rejected", "coalition_human_rejected", "coalition_cancelled", "coalition_exchange_failed",
    ].includes(activityEventType(activity) ?? ""));

  const visibleCoalitions = useMemo<RankedCoalition[]>(() => simulation.coalitionDeals
    .filter((deal) => coalitionWasRevealed(deal) && !coalitionClosureWasRevealed(deal))
    .map((deal) => ({
      proposal: deal.proposal,
      average_reputation: deal.average_reputation,
      participant_count: deal.proposal.participant_ids.length,
      score: deal.score,
    })), [simulation.coalitionDeals, activities, snapshotFallback]);

  const coalitionDeal = useMemo(() => {
    const relevant = simulation.coalitionDeals.filter((deal) =>
      selectedUserId !== null && deal.proposal.participant_ids.includes(selectedUserId) && coalitionWasRevealed(deal));
    return relevant[relevant.length - 1] ?? null;
  }, [simulation.coalitionDeals, selectedUserId, activities, snapshotFallback]);

  const shownCoalition = useMemo(() => coalitionDeal
    ? projectedCoalitionDeal(coalitionDeal, activities, snapshotFallback)
    : null, [coalitionDeal, activities, snapshotFallback]);

  const coalitionApprovalRevealed = !!coalitionDeal && (snapshotFallback || activities.some((activity) =>
    activityEntityId(activity) === coalitionDeal.id &&
    activityEventType(activity) === "coalition_human_approval_required" &&
    activity.user_id === selectedUserId));
  const coalitionExecutionRevealed = !!coalitionDeal && (snapshotFallback || activities.some((activity) =>
    activityEntityId(activity) === coalitionDeal.id && activityEventType(activity) === "coalition_approved"));

  const coalitionReviewReady = !!coalitionDeal &&
    coalitionDeal.status === "waiting_humans" &&
    selectedUserId !== null &&
    coalitionDeal.proposal.participant_ids.includes(selectedUserId) &&
    coalitionDeal.human_approvals[selectedUserId] == null &&
    coalitionApprovalRevealed;

  const coalitionApprovalKey = coalitionReviewReady && coalitionDeal && selectedUserId
    ? `${coalitionDeal.id}:${selectedUserId}`
    : null;

  useEffect(() => {
    if (selectedNegotiationId && allNegotiations.some((n) => n.id === selectedNegotiationId)) return;
    if (!simulation.isSuccess) return;
    const next = [...visibleNegotiations].reverse().find((n) => !isClosedStatus(n.status) &&
      (selectedUserId === null || n.participant_ids.includes(selectedUserId)));
    if (next) selectNegotiation(next.id);
    else if (selectedNegotiationId && !allNegotiations.some((n) => n.id === selectedNegotiationId)) selectNegotiation(null);
  }, [selectedNegotiationId, allNegotiations, visibleNegotiations, simulation.isSuccess, selectedUserId, selectNegotiation]);

  useEffect(() => {
    setDraftNeed(null);
  }, [selectedUserId]);

  const selectedProfile = simulation.users.find((user) => user.user_id === selectedUserId) ?? null;
  const runtime = (simulation.state as RuntimeSimulationState | undefined)?.agent_states
    ?.find((state) => state.user_id === selectedUserId);
  // Le détail REST est la source des commandes, la projection n'est que pour l'affichage.
  const live = negotiation.negotiation ?? allNegotiations.find((n) => n.id === selectedNegotiationId) ?? null;

  // On a fresh page load the REST state is already authoritative. There is no
  // historical WebSocket replay, so the UI must not hide nodes/deals/modals
  // while waiting for events that will never arrive.
  const shown = snapshotFallback ? live : displayedNegotiation(live, tracked);
  const ready = !!live && (
    snapshotFallback
      ? live.status === "waiting_human" && Boolean(live.accepted_offer_id)
      : approvalIsReady(live, tracked)
  );

  const approvalKey = live?.accepted_offer_id ? `${live.id}:${live.accepted_offer_id}` : null;
  const busy = negotiation.isRequestingApproval || negotiation.isApproving || negotiation.isRejecting ||
    negotiation.isExecuting || stop.isPending || coalitionActions.isPending;
  const catchingUp = !snapshotFallback && !!live && (
    !shown ||
    shown.status !== live.status ||
    shown.accepted_offer_id !== live.accepted_offer_id ||
    (live.status === "waiting_human" && !ready)
  );
  const executed = !!live && simulation.completedNegotiations.some((n) => n.id === live.id);

  useEffect(() => {
    if (!ready || !approvalKey || !live) {
      if (isApprovalModalOpen) closeApprovalModal();
      return;
    }
    if (!dismissed.current.has(approvalKey) && !isApprovalModalOpen) {
      dismissed.current.add(approvalKey);
      openApprovalModal(live.id);
    }
  }, [ready, approvalKey, live, isApprovalModalOpen, openApprovalModal, closeApprovalModal]);

  useEffect(() => {
    if (!coalitionReviewReady || !coalitionApprovalKey) {
      setCoalitionApprovalModalOpen(false);
      return;
    }

    if (!dismissedCoalitions.current.has(coalitionApprovalKey)) {
      dismissedCoalitions.current.add(coalitionApprovalKey);
      setCoalitionApprovalModalOpen(true);
    }
  }, [coalitionReviewReady, coalitionApprovalKey]);

  const resolveUserName = useMemo(() => {
    const names = new Map(simulation.users.map((user) => [user.user_id, user.display_name]));
    return (id: string) => names.get(id) ?? id;
  }, [simulation.users]);

  async function handleGoalSubmit(value: GoalComposerValue) {
    if (!selectedUserId) return;
    setCommandError(null);
    try {
      const result = await agent.pursueRequest(value);
      if (result.negotiation) {
        // La réponse HTTP ne doit pas faire surgir un deal en avance sur son événement.
        if (connected) usePresentationStore.getState().track(result.negotiation.id);
        selectNegotiation(result.negotiation.id);
      }
    } catch (error) { setCommandError(errorMessage(error)); }
  }

  async function perform(action: () => Promise<unknown>) {
    setCommandError(null);
    try { await action(); } catch (error) { setCommandError(errorMessage(error)); }
  }

  function dismissApproval() {
    if (approvalKey) dismissed.current.add(approvalKey);
    closeApprovalModal();
  }

  async function approve() {
    if (!ready || catchingUp) return;
    await perform(async () => {
      const result = await negotiation.approve();
      usePresentationStore.getState().confirm(result.negotiation);
      dismissApproval();
    });
  }

  async function reject() {
    if (!ready || catchingUp) return;
    await perform(async () => {
      const result = await negotiation.reject();
      usePresentationStore.getState().confirm(result.negotiation);
      dismissApproval();
      await simulation.refetch();
    });
  }

  async function stopObjective() {
    if (!selectedUserId) return;
    await perform(async () => { await stop.mutateAsync(selectedUserId); dismissApproval(); });
  }

  async function approveCoalition() {
    if (!coalitionDeal || !selectedUserId || !coalitionApprovalRevealed) return;
    await perform(async () => {
      await coalitionActions.approve({ coalitionId: coalitionDeal.id, userId: selectedUserId });
      setCoalitionApprovalModalOpen(false);
      await simulation.refetch();
    });
  }

  async function rejectCoalition() {
    if (!coalitionDeal || !selectedUserId || !coalitionApprovalRevealed) return;
    await perform(async () => {
      await coalitionActions.reject({ coalitionId: coalitionDeal.id, userId: selectedUserId });
      setCoalitionApprovalModalOpen(false);
      await simulation.refetch();
    });
  }

  async function executeCoalition() {
    if (!coalitionDeal || !coalitionExecutionRevealed) return;
    await perform(async () => {
      await coalitionActions.execute(coalitionDeal.id);
      await simulation.refetch();
    });
  }

  function catchUp() {
    activityPresentationQueue.flush();
    usePresentationStore.getState().releaseUnannounced();
    void simulation.refetch();
  }

  if (simulation.isLoading) return <div className="flex min-h-screen items-center justify-center bg-slate-950">
    <LoadingSpinner size="lg" label="Loading simulation..." />
  </div>;
  if (simulation.isError) return <div className="min-h-screen bg-slate-950 p-8 text-slate-100">
    <ErrorState title="Could not load SimulationWorld" message={errorMessage(simulation.error)}
      onRetry={() => { void simulation.refetch(); }} />
  </div>;

  return <>
    <DashboardLayout
      header={<DashboardHeader connected={connected} currentTime={simulation.currentTime}
        usersCount={simulation.users.length} activeNegotiationsCount={simulation.activeNegotiations.length} />}
      left={<LeftPanel>
        <AgentPanel
          profile={selectedProfile}
          dashboard={userDashboard.data ?? null}
          needPreview={draftNeed}
          currentAction={currentAction(runtime, allNegotiations, tracked, live, snapshotFallback)}
        />
        {runtime && <Panel>
          <p className="text-xs font-semibold text-cyan-300">{runtime.status.replaceAll("_", " ")}</p>
          <p className="mt-2 text-xs leading-5 text-slate-400">{
            runtime.status === "waiting_human" && !ready ? "Revealing the negotiation before showing the approval card." : runtime.reason
          }</p>
          {["searching", "negotiating", "waiting_human", "approved", "searching_coalition", "coalition_proposed", "coalition_validating", "coalition_waiting_humans", "coalition_approved"].includes(runtime.status) &&
            <button type="button" disabled={busy} onClick={() => { void stopObjective(); }}
              className="mt-3 w-full rounded-lg border border-rose-400/40 px-3 py-2 text-xs text-rose-300 disabled:opacity-50">
              Stop objective
            </button>}
        </Panel>}
        {selectedUserId ? <GoalComposer
          key={selectedUserId}
          dashboard={userDashboard.data ?? null}
          onRequestDraftChange={setDraftNeed}
          onSubmit={handleGoalSubmit}
          isSubmitting={agent.isPursuing}
        /> :
          <Panel><p className="text-sm text-slate-500">Create a marketplace user first.</p></Panel>}
        {commandError && <ErrorState title="Action failed" message={commandError} />}
      </LeftPanel>}
      center={<div className="flex h-full min-h-0 flex-col gap-3">
        <div className="shrink-0"><MarketLegend /></div>
        <div className="min-h-0 flex-1">
          <MarketGraph users={simulation.users} negotiations={visibleNegotiations} coalitions={visibleCoalitions}
            selectedUserId={selectedUserId} onSelectUser={selectUser} />
        </div>
      </div>}
      right={<RightPanel>
        <AgentActivityFeed activities={activities} pendingCount={pendingCount} onCatchUp={catchUp}
          emptyMessage={connected ? "Waiting for live agent events..." : "WebSocket offline; displaying the REST snapshot."} />
      </RightPanel>}
      bottom={<BottomPanel><div className="space-y-3">
        {catchingUp && <p className="rounded-lg border border-cyan-500/20 p-3 text-xs text-cyan-200">
          Reading the event stream. Approval controls appear with the corresponding activity.
          <button type="button" className="ml-2 underline" onClick={catchUp}>Catch up</button>
        </p>}
        <NegotiationPanel negotiation={shown} resolveUserName={resolveUserName}
          onRequestApproval={shown?.status === live?.status ? () => { void perform(negotiation.requestHumanApproval); } : undefined}
          onApprove={ready ? approve : undefined} onReject={ready ? reject : undefined}
          onExecute={!executed && !catchingUp && live?.status === "approved" ?
            () => { void perform(negotiation.execute); } : undefined}
          busy={busy || catchingUp} />
        {executed && <p className="text-sm text-emerald-300">Exchange completed; execution is not repeatable.</p>}
        <CoalitionPanel deal={shownCoalition} selectedUserId={selectedUserId}
          resolveUserName={resolveUserName} approvalRevealed={coalitionApprovalRevealed}
          executionRevealed={coalitionExecutionRevealed} busy={busy}
          onApprove={() => { void approveCoalition(); }} onReject={() => { void rejectCoalition(); }}
          onExecute={() => { void executeCoalition(); }} />
        {coalitionReviewReady && !coalitionApprovalModalOpen && (
          <button
            type="button"
            className="text-sm text-violet-300 underline"
            onClick={() => setCoalitionApprovalModalOpen(true)}
          >
            Review coalition for {selectedUserId ? resolveUserName(selectedUserId) : "participant"}
          </button>
        )}
        {ready && !isApprovalModalOpen && <button type="button" className="text-sm text-cyan-300 underline"
          onClick={() => live && openApprovalModal(live.id)}>Review current deal</button>}
      </div><div className="space-y-4">
        <SimulationControls />
        <Panel><UpcomingEvents events={simulation.scheduledEvents} /></Panel>
        <Panel><EventHistory events={simulation.eventHistory} maxItems={8} /></Panel>
      </div></BottomPanel>}
    />
    <ApprovalModal open={isApprovalModalOpen && ready && !catchingUp} negotiation={live}
      resolveUserName={resolveUserName} onApprove={approve} onReject={reject}
      onClose={dismissApproval} busy={busy} />

    <CoalitionApprovalModal
      open={coalitionApprovalModalOpen && coalitionReviewReady}
      deal={coalitionDeal}
      selectedUserId={selectedUserId}
      resolveUserName={resolveUserName}
      onApprove={approveCoalition}
      onReject={rejectCoalition}
      onClose={() => setCoalitionApprovalModalOpen(false)}
      busy={busy}
    />
  </>;
}
