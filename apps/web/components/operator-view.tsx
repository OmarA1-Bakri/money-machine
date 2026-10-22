import { artifactPath, fetchRunSummary, type RunRecovery, type RunSummary } from "../lib/operator-summary";
import { fetchOperatorView, operatorViews, type OperatorView } from "../lib/operator";

const descriptions: Record<OperatorView, string> = {
  now: "The current product and its workflow state.",
  pipeline: "Jobs moving the product from research to draft.",
  shop: "Stored listing versions and their draft state.",
  blocked: "Work waiting on a recorded blocker.",
  decisions: "The reasoning recorded along the product's path.",
  incidents: "Recorded incidents for the selected run.",
  settings: "Integration connections and their operating mode.",
};
const titles: Record<OperatorView, string> = {
  now: "NOW", pipeline: "Pipeline", shop: "Shop", blocked: "Blocked",
  decisions: "Decisions", incidents: "Incidents", settings: "Settings",
};

export type OperatorPageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export async function OperatorViewPage({ view, searchParams }: OperatorPageProps & { view: OperatorView }) {
  const params = await searchParams;
  const selected = params.run_id;
  const requestedRun = Array.isArray(selected) ? selected[0] : selected;
  const result = await fetchOperatorView(view, requestedRun);
  const runId = result.kind === "ready" ? result.data.run_id : requestedRun;
  const needsSummary = view === "now" || view === "pipeline" || view === "shop" || view === "incidents";
  const fetchedSummary = result.kind === "ready" && needsSummary && runId
    ? await fetchRunSummary(runId) : null;
  const summary = fetchedSummary?.kind === "ready" && result.kind === "ready" &&
    fetchedSummary.data.execution_mode !== result.data.execution_mode
    ? { kind: "unavailable" as const } : fetchedSummary;
  const query = runId === undefined ? "" : "?" + new URLSearchParams({ run_id: runId }).toString();
  return (
    <div className="console-shell">
      <aside className="sidebar">
        <a className="brand" href={"/" + query} aria-label="Money Machine home">
          <span className="brand-mark" aria-hidden="true">M</span>
          <span>Money Machine<small>Operator console</small></span>
        </a>
        <nav aria-label="Operator views">
          {operatorViews.map((item) => (
            <a key={item} href={(item === "now" ? "/" : "/" + item) + query}
              aria-current={item === view ? "page" : undefined}>
              <span className="nav-dot" aria-hidden="true" />{titles[item]}
            </a>
          ))}
        </nav>
        <div className="sidebar-note"><span className="mode-dot" />Read-only console
          <p>Business transitions and external actions are disabled.</p>
        </div>
      </aside>
      <main>
        <header className="page-heading">
          <p className="eyebrow">Product operations</p>
          <h1>{titles[view]}</h1>
          <p className="lede">{descriptions[view]}</p>
        </header>
        {result.kind === "unavailable" ? (
          <section className="notice unavailable" role="status">
            <span className="notice-symbol" aria-hidden="true">!</span>
            <div><h2>Data unavailable</h2>
              <p>The operator API could not return this view. Check the connection or the selected run, then reload.</p>
              <a className="reload-link" href={(view === "now" ? "/" : "/" + view) + query}>Reload view <span aria-hidden="true">↗</span></a>
            </div>
          </section>
        ) : (
          <>
            <section className="run-strip" aria-label="Selected run">
              <div><span className="label">{result.data.execution_mode === "fixture" ? "Fixture run" : "Real draft run"}</span><code>{result.data.run_id}</code></div>
              <span className="read-label">Stored records · Read only</span>
            </section>
            {summary?.kind === "unavailable" && (
              <section className="notice proof-unavailable" role="status"><h2>Product proof unavailable</h2>
                <p>The API could not verify this run’s completion or stored files. Reload to try again.</p>
              </section>
            )}
            {summary?.kind === "ready" && <ProductProof summary={summary.data} view={view} />}
            <section aria-label={titles[view] + " records"} className="records">
              {result.data.items.length === 0 ? (
                <div className="notice"><h2>No records returned</h2><p>This run has no stored records for this view.</p></div>
              ) : result.data.items.map((item) => (
                <article className="record-card" key={item.id} data-record-id={item.id}>
                  <div className="record-heading"><h2>{item.label}</h2><span className="state">{item.state}</span></div>
                  {item.detail && <p className="record-detail">{item.detail}</p>}
                  <dl className="identities">
                    <div><dt>Record</dt><dd>{item.id}</dd></div>
                    {item.product_id && <div><dt>Product</dt><dd>{item.product_id}</dd></div>}
                    {item.listing_version_id && <div><dt>Listing version</dt><dd>{item.listing_version_id}</dd></div>}
                  </dl>
                </article>
              ))}
            </section>
            <footer>{result.data.execution_mode === "fixture" ? "Fixture evidence only." : "Private draft work. Publishing and spend remain disabled."} Provider connections are shown as recorded.</footer>
          </>
        )}
      </main>
    </div>
  );
}

function ProductProof({ summary, view }: { summary: RunSummary; view: OperatorView }) {
  const real = summary.execution_mode === "real_draft";
  const held = summary.pending_effects > 0;
  const showWorkflow = view === "now" || view === "pipeline";
  const showArtifacts = view === "now" || view === "shop";
  const template = summary.artifacts.find((artifact) => artifact.kind === "product_html" &&
    artifact.media_type.split(";")[0]?.trim() === "text/html");
  return <section className="product-proof" aria-label="Stored product proof">
    <div className="proof-heading"><div><p className="eyebrow">{real ? "Private product · Real draft" : "Produced product · Fixture only"}</p>
      <h2>{summary.product_title}</h2></div><span className="state">Production lifecycle: {summary.product_state}</span></div>
    {showWorkflow && <>
      <div className="completion-strip"><div><span className="label">{real ? "Private draft workflow" : "Fixture workflow"}</span>
        <strong>{held ? "Held for provider reconciliation" : real
          ? (summary.workflow_completed ? "Draft workflow completed" : "Draft workflow in progress")
          : (summary.fixture_completed ? "Fixture completed" : "Fixture in progress")}</strong>
        {summary.completed_at && <time dateTime={summary.completed_at}>{summary.completed_at}</time>}
      </div><p>{real ? "Publishing and spend remain disabled. Job states below remain as stored; production is not commissioned."
        : "Fixture completion records the local proof. Job states below remain as stored; production is not commissioned."}</p></div>
      {held && <p role="status">{summary.pending_effects} uncertain provider operation{summary.pending_effects === 1 ? "" : "s"}. Writes are held until the outcome is reconciled.</p>}
      <ol className="job-list" aria-label="Stored workflow jobs">{summary.jobs.map((job) =>
        <li key={job.id}><div><strong>{job.job_type}</strong><code>{job.id}</code></div>
          <span className="state" data-state={job.status}>{job.status}</span></li>)}</ol>
      {summary.jobs.length === 0 && <p className="record-detail">No jobs returned for this workflow.</p>}
    </>}
    {(showWorkflow || view === "incidents") && summary.recoveries.length > 0 &&
      <section className="recovery-section" aria-label="Stored A07 recovery">
        <h3>Notification recovery</h3>
        <p className="record-detail">Effect confirmation does not complete the repair or workflow. Retained response identities may still require verification.</p>
        {summary.recoveries.map((recovery) => <RecoveryProof key={recovery.job_id} recovery={recovery} held={held} />)}
      </section>}
    {showArtifacts && <div className="artifact-section">
      <div className="artifact-heading"><h3>Produced template</h3>
        {template && <a className="file-link" href={artifactPath(summary.run_id, template.id)} target="_blank" rel="noreferrer">Open template ↗</a>}</div>
      {template ? <iframe className="template-preview" title={summary.product_title + " — stored product preview"}
        src={artifactPath(summary.run_id, template.id)} sandbox="" referrerPolicy="no-referrer" />
        : <p className="record-detail">{real ? "No verified template preview has been recorded yet." : "No stored HTML template returned for this run."}</p>}
      <ul className="artifact-list" aria-label="Stored product files">{summary.artifacts.map((artifact) =>
        <li key={artifact.id}><a href={artifactPath(summary.run_id, artifact.id)} target="_blank" rel="noreferrer">
          <span>{artifact.label}<small>{artifact.media_type} · {artifact.byte_size.toLocaleString("en-US")} bytes</small></span><span aria-hidden="true">↗</span>
        </a></li>)}</ul>
      {summary.artifacts.length === 0 && <p className="record-detail">No stored product files returned.</p>}
    </div>}
  </section>;
}

function RecoveryProof({ recovery, held }: { recovery: RunRecovery; held: boolean }) {
  const nextStep = recovery.effect_state === "UNKNOWN" || recovery.agent_run_status === "UNCERTAIN_EXTERNAL_EFFECT"
    ? (recovery.database_id && recovery.data_source_id
      ? "Read the retained database and data source through the original authorized connection, then reconcile this operation in the canonical ledger. Keep writes held. Do not resend create."
      : "Recover this operation’s retained provider request or resource evidence through the original authorized connection, then reconcile it in the canonical ledger. Keep writes held. Do not resend create.")
    : recovery.agent_run_status === "SUCCESS" && recovery.effect_state === "CONFIRMED"
      ? (held ? "Keep the original UNKNOWN held until the production owner reconciles it and verifies canonical selection before completing this repair."
        : "Ask the production owner to verify canonical selection and the original operation in the canonical ledger before completing this repair.")
      : recovery.agent_run_status === "RUNNING"
        ? "Check the persisted A07 run before proceeding. An active run does not authorize another send; reconcile unresolved effects first."
        : "Review the persisted A07 outcome and this job’s operation in the canonical ledger before taking any recovery action. Do not resend create.";
  return <article className="recovery-card">
    <dl className="identities">
      <div><dt>Recovery job</dt><dd>{recovery.job_id}</dd></div>
      <div><dt>Latest A07 run</dt><dd>{recovery.agent_run_id ?? "Not recorded"}</dd></div>
      <div><dt>Agent outcome</dt><dd>{recovery.agent_run_status ?? "Not recorded"}</dd></div>
      <div><dt>Effect state</dt><dd>{recovery.effect_state ?? "Not correlated or not recorded"}</dd></div>
      <div><dt>Database</dt><dd>{recovery.database_id ?? "Not retained"}</dd></div>
      <div><dt>Data source</dt><dd>{recovery.data_source_id ?? "Not retained"}</dd></div>
    </dl>
    <p className="record-detail"><strong>Next step: </strong>{nextStep}</p>
  </article>;
}
