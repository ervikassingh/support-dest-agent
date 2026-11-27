import { DocumentsPanel } from '../../components/DocumentsPanel';

export default function DocumentsPage() {
  return (
    <>
      <header className="page-intro">
        <h1>Documents</h1>
        <p>
          Add a policy file or a public link. It is queued, parsed, chunked, and
          embedded. Search keeps every version and prefers the newest copy of
          identical text.
        </p>
      </header>
      <DocumentsPanel />
    </>
  );
}