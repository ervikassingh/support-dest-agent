import { ApprovalsWorkspace } from '../../components/ApprovalsWorkspace';

export default function ApprovalsPage() {
  return (
    <>
      <header className="page-intro">
        <h1>Human approvals</h1>
        <p>
          Refunds the agent has drafted wait here. Check the draft and the conversation, then approve, edit, or reject.
          Every decision is kept under Decided.
        </p>
      </header>
      <ApprovalsWorkspace />
    </>
  );
}
