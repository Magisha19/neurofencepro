import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiRequest, ApiError } from "../api/client";
import type { AuditLogList } from "../types/api";

const PAGE_SIZE = 50;

export function AuditPage() {
  const [offset, setOffset] = useState(0);
  const audit = useQuery({
    queryKey: ["audit", offset],
    queryFn: () =>
      apiRequest<AuditLogList>(`/audit?limit=${PAGE_SIZE}&offset=${offset}`),
  });

  const items = audit.data?.items ?? [];

  return (
    <main className="page-layout">
      <section className="page-heading">
        <div>
          <p className="eyebrow">WORKSPACE / ACTIVITY</p>
          <h1>Audit log</h1>
          <p className="panel-copy">
            Account activity recorded for your workspace.
          </p>
        </div>
      </section>

      <section aria-labelledby="audit-heading" className="panel table-panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">RECENT EVENTS</p>
            <h2 id="audit-heading">Audit entries</h2>
          </div>
          {audit.data && (
            <span className="count-chip">{audit.data.total} total</span>
          )}
        </div>
        {audit.isPending && (
          <p className="state-message" role="status">
            Loading audit entries…
          </p>
        )}
        {audit.isError && (
          <p className="form-error state-error" role="alert">
            {audit.error instanceof ApiError
              ? audit.error.detail
              : "Audit entries could not be loaded."}
          </p>
        )}
        {audit.data && items.length === 0 && (
          <div className="empty-state">
            <span aria-hidden="true" className="empty-glyph">
              ◇
            </span>
            <h3>No audit entries</h3>
            <p>Account activity will appear here when available.</p>
          </div>
        )}
        {items.length > 0 && (
          <>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Time</th>
                    <th scope="col">Action</th>
                    <th scope="col">Resource</th>
                    <th scope="col">Resource ID</th>
                    <th scope="col">IP</th>
                    <th scope="col">Detail</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => {
                    const ip = item.detail.ip;
                    return (
                      <tr key={item.id}>
                        <td className="date-cell">
                          {new Date(item.created_at).toLocaleString()}
                        </td>
                        <td className="mono-cell">{item.action}</td>
                        <td>{item.resource_type ?? "—"}</td>
                        <td className="mono-cell">{item.resource_id ?? "—"}</td>
                        <td className="mono-cell">
                          {typeof ip === "string" ? ip : "—"}
                        </td>
                        <td className="audit-detail">
                          {formatDetail(item.detail)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div aria-label="Audit log pages" className="pagination">
              <button
                className="quiet-button"
                disabled={offset === 0 || audit.isFetching}
                onClick={() =>
                  setOffset((current) => Math.max(0, current - PAGE_SIZE))
                }
                type="button"
              >
                Previous
              </button>
              <span>
                {offset + 1}–{Math.min(offset + PAGE_SIZE, audit.data?.total ?? 0)}{" "}
                of {audit.data?.total ?? 0}
              </span>
              <button
                className="quiet-button"
                disabled={
                  offset + PAGE_SIZE >= (audit.data?.total ?? 0) ||
                  audit.isFetching
                }
                onClick={() => setOffset((current) => current + PAGE_SIZE)}
                type="button"
              >
                Next
              </button>
            </div>
          </>
        )}
      </section>
    </main>
  );
}

function formatDetail(detail: Record<string, unknown>): string {
  const entries = Object.entries(detail).filter(([key]) => key !== "ip");
  if (!entries.length) return "—";
  return entries
    .map(([key, value]) => `${key}: ${formatValue(value)}`)
    .join(" · ");
}

function formatValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (value === null || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value) ?? String(value);
}
