import { ChatWorkspace } from '../components/ChatWorkspace';

export default function ChatPage() {
  return (
    <>
      <header className="page-intro">
        <h1>Customer chat</h1>
        <p>
          Ask about policies, orders, or refunds. Refunds that spend money pause for a human decision on Approvals.
          Every chat is saved, so you can reopen it from the list.
        </p>
      </header>
      <ChatWorkspace />
    </>
  );
}
