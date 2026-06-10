/**
 * API helpers for the Customer & Partner Portal module.
 *
 * Backed by /api/v1/portal/ — see backend/app/modules/portal/router.py
 *
 * Exposes the internal-admin surface (RequirePermission-gated):
 *   - users (invite / list / get / patch / resend)
 *   - access-rules (grant / revoke)
 *   - document-access-log (audit log, read-only)
 *
 * The portal-user-facing /auth/* + /me/* endpoints are NOT wrapped here;
 * those live on a different session token system and have their own UI.
 */

import { apiGet, apiPost, apiPatch, apiDelete } from '@/shared/lib/api';

/* ── Types ─────────────────────────────────────────────────────────────── */

export type PortalRole =
  | 'client'
  | 'investor'
  | 'consultant'
  | 'subcontractor'
  | 'supplier'
  | 'building_user';

export type PortalUserStatus = 'invited' | 'active' | 'suspended' | 'expired';

export type AccessPermission = 'view' | 'comment' | 'submit' | 'sign';

export type AccessAction = 'view' | 'download' | 'sign';

export interface PortalUser {
  id: string;
  email: string;
  full_name: string;
  portal_role: PortalRole | string;
  language: string;
  timezone: string;
  status: PortalUserStatus | string;
  invited_at: string | null;
  last_login_at: string | null;
  failed_login_count: number;
  locked_until: string | null;
  created_at: string;
  updated_at: string;
}

export interface PortalUserList {
  items: PortalUser[];
  total: number;
}

export interface InvitePayload {
  email: string;
  full_name?: string;
  portal_role: PortalRole;
  language?: string;
  timezone?: string;
  redirect_path?: string | null;
}

export interface InviteResponse {
  user: PortalUser;
  magic_link_token: string;
  magic_link_expires_at: string;
}

export interface UserPatch {
  status?: PortalUserStatus;
  full_name?: string;
  language?: string;
  timezone?: string;
}

export interface AccessRule {
  id: string;
  portal_user_id: string;
  resource_type: string;
  resource_id: string;
  permission: AccessPermission | string;
  granted_at: string | null;
  granted_by: string | null;
  expires_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AccessRuleCreate {
  portal_user_id: string;
  resource_type: string;
  resource_id: string;
  permission?: AccessPermission;
  expires_at?: string | null;
}

export interface AccessRuleList {
  items: AccessRule[];
  total: number;
}

export interface DocumentAccessLogEntry {
  id: string;
  portal_user_id: string;
  document_type: string;
  document_id: string;
  action: AccessAction | string;
  occurred_at: string | null;
  ip_address: string | null;
  created_at: string;
}

/* ── Users ─────────────────────────────────────────────────────────────── */

export function listPortalUsers(params?: {
  offset?: number;
  limit?: number;
  portal_role?: string;
  status?: string;
}): Promise<PortalUserList> {
  const qs = new URLSearchParams();
  if (params?.offset !== undefined) qs.set('offset', String(params.offset));
  if (params?.limit !== undefined) qs.set('limit', String(params.limit));
  if (params?.portal_role) qs.set('portal_role', params.portal_role);
  if (params?.status) qs.set('status', params.status);
  const q = qs.toString();
  return apiGet<PortalUserList>(`/v1/portal/admin/users${q ? `?${q}` : ''}`);
}

export function getPortalUser(id: string): Promise<PortalUser> {
  return apiGet<PortalUser>(`/v1/portal/admin/users/${id}`);
}

export function invitePortalUser(data: InvitePayload): Promise<InviteResponse> {
  return apiPost<InviteResponse>('/v1/portal/admin/users/invite', data);
}

export function patchPortalUser(id: string, data: UserPatch): Promise<PortalUser> {
  return apiPatch<PortalUser>(`/v1/portal/admin/users/${id}`, data);
}

export function suspendPortalUser(id: string): Promise<PortalUser> {
  return patchPortalUser(id, { status: 'suspended' });
}

export function reactivatePortalUser(id: string): Promise<PortalUser> {
  return patchPortalUser(id, { status: 'active' });
}

export function resendInvite(id: string): Promise<InviteResponse> {
  return apiPost<InviteResponse>(`/v1/portal/admin/users/${id}/resend-invite`, {});
}

/* ── Access rules ──────────────────────────────────────────────────────── */

export function listAccessRules(params?: {
  portal_user_id?: string;
  resource_type?: string;
  offset?: number;
  limit?: number;
}): Promise<AccessRuleList> {
  const qs = new URLSearchParams();
  if (params?.portal_user_id) qs.set('portal_user_id', params.portal_user_id);
  if (params?.resource_type) qs.set('resource_type', params.resource_type);
  if (params?.offset !== undefined) qs.set('offset', String(params.offset));
  if (params?.limit !== undefined) qs.set('limit', String(params.limit));
  const q = qs.toString();
  return apiGet<AccessRuleList>(
    `/v1/portal/admin/access-rules${q ? `?${q}` : ''}`,
  );
}

export function grantAccess(data: AccessRuleCreate): Promise<AccessRule> {
  return apiPost<AccessRule>('/v1/portal/admin/access-rules', data);
}

export function revokeAccess(ruleId: string): Promise<void> {
  return apiDelete(`/v1/portal/admin/access-rules/${ruleId}`);
}

/* ── Audit log ─────────────────────────────────────────────────────────── */

export function listDocumentAccessLog(params?: {
  portal_user_id?: string;
  document_type?: string;
  offset?: number;
  limit?: number;
}): Promise<DocumentAccessLogEntry[]> {
  const qs = new URLSearchParams();
  if (params?.portal_user_id) qs.set('portal_user_id', params.portal_user_id);
  if (params?.document_type) qs.set('document_type', params.document_type);
  if (params?.offset !== undefined) qs.set('offset', String(params.offset));
  if (params?.limit !== undefined) qs.set('limit', String(params.limit));
  const q = qs.toString();
  return apiGet<DocumentAccessLogEntry[]>(
    `/v1/portal/admin/document-access-log${q ? `?${q}` : ''}`,
  );
}
