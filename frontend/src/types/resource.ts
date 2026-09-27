import type {
  ISODateTime,
  Metadata,
} from "./common";


/**
 * Mirrors app.models.resource.Resource.
 */
export interface Resource {
  id: string;

  resource_type: string;

  quantity: number;

  unit: string;

  available_from: ISODateTime | null;

  available_until: ISODateTime | null;

  attributes: Metadata;
}


/**
 * Mirrors app.models.resource.ResourceRequest.
 */
export interface ResourceRequest {
  id: string;

  resource_type: string;

  quantity: number;

  unit: string;

  deadline: ISODateTime | null;

  attributes: Metadata;
}


/**
 * Convenient creation shape for forms before an ID is generated
 * by the backend.
 */
export type CreateResourceInput = Omit<
  Resource,
  "id"
> & {
  id?: string;
};


/**
 * Convenient creation shape for forms before an ID is generated
 * by the backend.
 */
export type CreateResourceRequestInput = Omit<
  ResourceRequest,
  "id"
> & {
  id?: string;
};
