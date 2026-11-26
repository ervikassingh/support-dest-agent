import { Suspense } from 'react';
import { ApprovalsForm } from '../../components/ApprovalsForm';

export default function ApprovalsPage() {
  return (
    <>
      <header className="page-intro">
        <h1>Human approvals</h1>
        <p>
          Resume a paused refund thread. Copy the thread ID from chat, choose a
          decision, and submit — the agent continues from the checkpoint.
        </p>
      </header>

      <Suspense
        fallback={
          <section className="panel" aria-label="Approval decision">
            <div className="meta-bar">
              <span className="pill pill-neutral">
                <span className="pill-dot" aria-hidden="true" />
                Loading…
              </span>
            </div>
            <div className="approval-form">
              <p className="field-help">Preparing the approval form…</p>
            </div>
          </section>
        }
      >
        <ApprovalsForm />
      </Suspense>
    </>
  );
}
