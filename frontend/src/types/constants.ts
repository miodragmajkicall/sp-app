// /home/miso/dev/sp-app/sp-app/frontend/src/types/constants.ts

export type Jurisdiction = "RS" | "FBiH" | "BD";

export type AppConstantsSetRead = {
  id: number;
  jurisdiction: string;
  effective_from: string; // YYYY-MM-DD
  effective_to: string | null;

  payload: Record<string, unknown>;

  created_at: string; // ISO datetime
  updated_at: string; // ISO datetime

  created_by: string | null;
  created_reason: string | null;

  updated_by: string | null;
  updated_reason: string | null;
};

export type AppConstantsSetListResponse = {
  items: AppConstantsSetRead[];
};

export type AppConstantsSetCreate = {
  jurisdiction: string; // "RS" | "FBiH" | "BD"
  effective_from: string; // YYYY-MM-DD
  effective_to?: string | null; // YYYY-MM-DD | null

  payload: Record<string, unknown>;

  created_by?: string | null;
  created_reason: string;
};

export type AppConstantsSetUpdate = {
  jurisdiction?: string | null;
  effective_from?: string | null;
  effective_to?: string | null;

  payload?: Record<string, unknown> | null;

  updated_by?: string | null;
  updated_reason: string;
};

export type AppConstantsCurrentResponse = {
  jurisdiction: string;
  as_of: string; // YYYY-MM-DD
  found: boolean;
  item: AppConstantsSetRead | null;
};
