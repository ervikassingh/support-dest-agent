import { EvalsDashboard } from '../../components/evals/EvalsDashboard';

export default function EvalsPage() {
  return (
    <>
      <header className="page-intro">
        <h1>Evals</h1>
        <p>
          Run the retrieval, answer, and agent test sets against the live services. Each run is
          saved, so you can see what a change did to the scores.
        </p>
      </header>
      <EvalsDashboard />
    </>
  );
}
