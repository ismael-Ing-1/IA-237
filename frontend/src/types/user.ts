import type {
  Metadata,
} from "./common";

import type {
  Resource,
  ResourceRequest,
} from "./resource";


/**
 * Mirrors app.models.user.NegotiationStrategy.
 */
export type NegotiationStrategy =
  | "balanced"
  | "conservative"
  | "aggressive"
  | "fast";


/**
 * Mirrors app.models.user.UserConstraints.
 *
 * IMPORTANT:
 * This object is private backend data.
 * It should not be rendered for arbitrary marketplace users.
 */
export interface UserConstraints {
  minimum_reputation: number;

  max_negotiation_rounds: number;

  max_quantity_to_give: Record<string, number>;

  require_human_approval: boolean;

  reveal_exact_inventory: boolean;

  additional_constraints: Metadata;
}


/**
 * Public marketplace representation of a user.
 *
 * Mirrors app.models.user.PublicUserProfile.
 */
export interface PublicUserProfile {
  user_id: string;

  display_name: string;

  offered_resource_types: string[];

  requested_resource_types: string[];

  online: boolean;
}


/**
 * Full backend user model.
 *
 * This contains PRIVATE fields such as preferences and constraints.
 * It is currently useful when creating users through the hackathon API,
 * but should not be exposed as public marketplace state.
 */
export interface User {
  id: string;

  name: string;

  resources: Resource[];

  needs: ResourceRequest[];

  preferred_partners: string[];

  blocked_partners: string[];

  strategy: NegotiationStrategy;

  constraints: UserConstraints;

  online: boolean;
}


/**
 * Owner-facing dashboard payload returned by:
 *
 * GET /users/{user_id}/dashboard
 *
 * Deliberately excludes private negotiation limits and partner preferences.
 */
export interface UserDashboard {
  id: string;

  name: string;

  online: boolean;

  resources: Resource[];

  needs: ResourceRequest[];

  strategy: NegotiationStrategy;
}


/**
 * Useful for user creation forms.
 *
 * The backend can generate User.id and has defaults for several fields,
 * so the frontend does not necessarily need to provide everything.
 */
export interface CreateUserInput {
  id?: string;

  name: string;

  resources?: Resource[];

  needs?: ResourceRequest[];

  preferred_partners?: string[];

  blocked_partners?: string[];

  strategy?: NegotiationStrategy;

  constraints?: Partial<UserConstraints>;

  online?: boolean;
}
