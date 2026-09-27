import {
  create,
} from "zustand";


export type GraphLayout =
  | "radial"
  | "horizontal"
  | "vertical";


interface UIState {
  /*
   * ----------------------------------------------------------
   * SELECTIONS
   * ----------------------------------------------------------
   */

  selectedUserId: string | null;

  selectedNegotiationId: string | null;

  selectedCoalitionId: string | null;


  /*
   * ----------------------------------------------------------
   * MODALS / PANELS
   * ----------------------------------------------------------
   */

  isApprovalModalOpen: boolean;

  isSimulationPanelOpen: boolean;

  isActivityPanelOpen: boolean;

  isSidebarCollapsed: boolean;


  /*
   * ----------------------------------------------------------
   * MARKET GRAPH
   * ----------------------------------------------------------
   */

  graphLayout: GraphLayout;

  graphAutoFit: boolean;


  /*
   * ----------------------------------------------------------
   * ACTIONS
   * ----------------------------------------------------------
   */

  selectUser: (
    userId: string | null,
  ) => void;

  selectNegotiation: (
    negotiationId: string | null,
  ) => void;

  selectCoalition: (
    coalitionId: string | null,
  ) => void;

  openApprovalModal: (
    negotiationId?: string,
  ) => void;

  closeApprovalModal: () => void;

  setSimulationPanelOpen: (
    open: boolean,
  ) => void;

  setActivityPanelOpen: (
    open: boolean,
  ) => void;

  setSidebarCollapsed: (
    collapsed: boolean,
  ) => void;

  toggleSidebar: () => void;

  setGraphLayout: (
    layout: GraphLayout,
  ) => void;

  setGraphAutoFit: (
    enabled: boolean,
  ) => void;

  resetUI: () => void;
}


const initialState = {
  selectedUserId: null,

  selectedNegotiationId: null,

  selectedCoalitionId: null,

  isApprovalModalOpen: false,

  isSimulationPanelOpen: true,

  isActivityPanelOpen: true,

  isSidebarCollapsed: false,

  graphLayout: "radial" as GraphLayout,

  graphAutoFit: true,
};


export const useUIStore =
  create<UIState>(
    (set) => ({
      ...initialState,

      selectUser: (
        userId,
      ) => {
        set({
          selectedUserId: userId,
        });
      },

      selectNegotiation: (
        negotiationId,
      ) => {
        set({
          selectedNegotiationId:
            negotiationId,
        });
      },

      selectCoalition: (
        coalitionId,
      ) => {
        set({
          selectedCoalitionId:
            coalitionId,
        });
      },

      openApprovalModal: (
        negotiationId,
      ) => {
        set((state) => ({
          isApprovalModalOpen: true,

          selectedNegotiationId:
            negotiationId ??
            state.selectedNegotiationId,
        }));
      },

      closeApprovalModal: () => {
        set({
          isApprovalModalOpen: false,
        });
      },

      setSimulationPanelOpen: (
        open,
      ) => {
        set({
          isSimulationPanelOpen:
            open,
        });
      },

      setActivityPanelOpen: (
        open,
      ) => {
        set({
          isActivityPanelOpen:
            open,
        });
      },

      setSidebarCollapsed: (
        collapsed,
      ) => {
        set({
          isSidebarCollapsed:
            collapsed,
        });
      },

      toggleSidebar: () => {
        set((state) => ({
          isSidebarCollapsed:
            !state.isSidebarCollapsed,
        }));
      },

      setGraphLayout: (
        layout,
      ) => {
        set({
          graphLayout: layout,
        });
      },

      setGraphAutoFit: (
        enabled,
      ) => {
        set({
          graphAutoFit: enabled,
        });
      },

      resetUI: () => {
        set({
          ...initialState,
        });
      },
    }),
  );


/*
 * ------------------------------------------------------------
 * OPTIONAL SELECTOR HELPERS
 * ------------------------------------------------------------
 *
 * They are useful when a component only needs one small part
 * of the store and should not re-render for unrelated changes.
 */

export const selectSelectedUserId = (
  state: UIState,
) => state.selectedUserId;


export const selectSelectedNegotiationId = (
  state: UIState,
) => state.selectedNegotiationId;


export const selectApprovalModalOpen = (
  state: UIState,
) => state.isApprovalModalOpen;
