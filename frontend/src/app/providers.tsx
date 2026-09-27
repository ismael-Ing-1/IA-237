// src/app/providers.tsx

import type { PropsWithChildren } from "react";

import {
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";

import { ReactFlowProvider } from "@xyflow/react";


/*
 * Une seule instance de QueryClient doit être utilisée
 * pendant toute la durée de vie de l'application.
 */
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      /*
       * Les données de notre marketplace peuvent changer
       * assez rapidement.
       *
       * Les WebSockets nous permettront ensuite
       * d'invalider explicitement les queries lorsqu'un
       * événement arrive.
       */
      staleTime: 5_000,

      /*
       * Évite de refaire automatiquement toutes les requêtes
       * simplement parce que l'utilisateur revient sur l'onglet.
       */
      refetchOnWindowFocus: false,

      /*
       * En cas d'erreur réseau temporaire.
       */
      retry: 1,
    },

    mutations: {
      retry: 0,
    },
  },
});


export function AppProviders({
  children,
}: PropsWithChildren) {
  return (
    <QueryClientProvider client={queryClient}>
      <ReactFlowProvider>
        {children}
      </ReactFlowProvider>
    </QueryClientProvider>
  );
}


/*
 * On exporte aussi QueryClient.
 *
 * Cela sera utile au système WebSocket.
 *
 * Exemple :
 *
 * exchange_completed
 *       ↓
 * queryClient.invalidateQueries(...)
 *       ↓
 * React récupère le nouvel état du monde
 */
export { queryClient };