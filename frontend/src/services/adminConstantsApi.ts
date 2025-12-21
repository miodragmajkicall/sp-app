// /home/miso/dev/sp-app/sp-app/frontend/src/services/adminConstantsApi.ts

import { apiClient } from "./apiClient";
import type {
  AppConstantsCurrentResponse,
  AppConstantsSetCreate,
  AppConstantsSetListResponse,
  AppConstantsSetRead,
  AppConstantsSetUpdate,
} from "../types/constants";

export async function adminConstantsList(params?: {
  jurisdiction?: string;
}): Promise<AppConstantsSetListResponse> {
  const res = await apiClient.get<AppConstantsSetListResponse>(
    "/admin/constants",
    { params }
  );
  return res.data;
}

export async function adminConstantsCreate(
  payload: AppConstantsSetCreate
): Promise<AppConstantsSetRead> {
  const res = await apiClient.post<AppConstantsSetRead>(
    "/admin/constants",
    payload
  );
  return res.data;
}

export async function adminConstantsUpdate(
  id: number,
  payload: AppConstantsSetUpdate
): Promise<AppConstantsSetRead> {
  const res = await apiClient.put<AppConstantsSetRead>(
    `/admin/constants/${id}`,
    payload
  );
  return res.data;
}

export async function constantsCurrent(params: {
  jurisdiction: string;
  as_of: string; // YYYY-MM-DD
}): Promise<AppConstantsCurrentResponse> {
  const res = await apiClient.get<AppConstantsCurrentResponse>(
    "/constants/current",
    { params }
  );
  return res.data;
}
