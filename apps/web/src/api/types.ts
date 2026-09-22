// Types derived from packages/contracts/CONTRACT.md (v1, frozen).
// Do not edit to match a different API — if the backend diverges, note it in the report.

export type Role = 'INVESTIGATOR' | 'LEGAL_REVIEWER' | 'EVIDENCE_CUSTODIAN' | 'SECURITY_AUDITOR';

export interface User {
  id: string;
  username: string;
  display_name: string;
  role: Role;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface CaseMember {
  user_id: string;
  username: string;
  display_name: string;
  role: Role;
}

export interface CaseDetail {
  id: string;
  case_number: string;
  title: string;
  description: string;
  status: string;
  created_by: string;
  created_at: string;
  members: CaseMember[];
  document_count?: number;
}

export type DocStatus = 'INGESTING' | 'QUARANTINED' | 'ACTIVE' | 'FROZEN';

export interface Version {
  id: string;
  version_number: number;
  sha256: string;
  size_bytes: number;
  mime_type: string;
  av_status: string;
  av_detail?: string | null;
  created_at: string;
  created_by: string;
}

export interface Document {
  id: string;
  case_id: string;
  title: string;
  doc_type: string;
  description?: string;
  status: DocStatus;
  current_version: Version;
  version_count: number;
  created_at: string;
  quarantine_reason?: string;
}

export interface IngestResponse {
  document_id: string;
  version_id: string;
  status: DocStatus;
}

export interface VerifyResult {
  document_id: string;
  version_id: string;
  stored_sha256: string;
  computed_sha256: string;
  match: boolean;
  verified_at: string;
}

export interface CustodyEvent {
  id: string;
  document_id: string;
  action: string;
  from_user_id?: string;
  to_user_id?: string;
  reason: string;
  created_at: string;
}

export type TimelineKind = 'custody' | 'audit' | 'ingest' | 'verify' | 'redaction' | 'export';

export interface TimelineEvent {
  id: string;
  kind: TimelineKind;
  actor: string;
  action: string;
  object_id: string;
  reason?: string;
  created_at: string;
  detail?: Record<string, unknown> | string;
}

export type RedactionLabel = 'AADHAAR' | 'PHONE' | 'EMAIL' | 'NAME';

export interface RedactionMark {
  mark_id: string;
  page: number;
  bbox: [number, number, number, number];
  label: RedactionLabel;
  confidence: number;
  text_excerpt: string;
}

export interface AnalyzeResponse {
  version_id: string;
  marks: RedactionMark[];
}

export interface DerivativeInfo {
  derivative_version_id: string;
  version_number: number;
  sha256: string;
}

export interface ExportBundle {
  id: string;
  case_id: string;
  status: string;
  sha256?: string;
  created_at: string;
  created_by: string;
  manifest?: ExportManifest;
}

export interface ExportManifest {
  bundle_id: string;
  case_number: string;
  exported_at: string;
  exported_by: string;
  audit_chain_head?: string;
  documents: Array<{
    document_id: string;
    title: string;
    doc_type: string;
    version_number: number;
    sha256: string;
    custody: unknown[];
  }>;
}

export type AuditOutcome = 'ALLOWED' | 'DENIED' | 'FAILED' | 'INCIDENT';

export interface AuditEvent {
  id: string;
  case_id?: string;
  actor_id?: string;
  actor_name?: string;
  action: string;
  object_type?: string;
  object_id?: string;
  outcome: AuditOutcome;
  reason?: string;
  request_id?: string;
  created_at: string;
  event_hash?: string;
  prev_hash?: string;
}

export interface ChainVerifyResult {
  ok: boolean;
  events_checked: number;
  broken_at_id: string | null;
}

export const ROLE_LABEL: Record<Role, string> = {
  INVESTIGATOR: 'Investigator',
  LEGAL_REVIEWER: 'Legal Reviewer',
  EVIDENCE_CUSTODIAN: 'Evidence Custodian',
  SECURITY_AUDITOR: 'Security Auditor',
};
