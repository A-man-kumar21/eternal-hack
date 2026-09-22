import { useQuery } from '@tanstack/react-query';
import { ApiError, apiGet } from './client';
import type { Document, TimelineEvent } from './types';

/**
 * Documents for a case.
 *
 * CONTRACT GAP: v1 has no `GET /cases/{id}/documents` endpoint — single-document GET only.
 * We first probe the (common, but non-contracted) list endpoint and fall back to
 * deriving document IDs from timeline ingest events. See the build report.
 */
export function useCaseDocuments(caseId: string) {
  return useQuery({
    queryKey: ['case-documents', caseId],
    queryFn: async (): Promise<Document[]> => {
      try {
        const list = await apiGet<Document[] | { documents: Document[] }>(`/cases/${caseId}/documents`);
        if (Array.isArray(list)) return list;
        if (list && Array.isArray((list as { documents?: unknown }).documents)) {
          return (list as { documents: Document[] }).documents;
        }
      } catch (e) {
        if (!(e instanceof ApiError) || e.status !== 404) throw e;
        // 404 → fall through to the timeline-derived approach below
      }
      const tl = await apiGet<{ events: TimelineEvent[] }>(`/cases/${caseId}/timeline`);
      const ids = [...new Set(tl.events.filter((ev) => ev.kind === 'ingest').map((ev) => ev.object_id))];
      const docs = await Promise.all(
        ids.map((id) => apiGet<Document>(`/documents/${id}`).catch(() => null)),
      );
      return docs.filter((d): d is Document => d !== null);
    },
    refetchInterval: (query) => {
      const docs = query.state.data as Document[] | undefined;
      return docs?.some((d) => d.status === 'INGESTING') ? 2000 : false;
    },
  });
}
