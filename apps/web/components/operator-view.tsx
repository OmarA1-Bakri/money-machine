import { artifactPath, fetchRunSummary, type RunSummary } from "../lib/operator-summary";
import { fetchOperatorView, operatorViews, type OperatorView } from "../lib/operator";

const descriptions: Record<OperatorView, string> = {
  now: "The current product and its workflow state.",
  pipeline: "Jobs moving the product from research to draft.",
  shop: "Stored listing versions and their draft state.",
  blocked: "Work waiting on a recorded blocker.",
  decisions: "The reasoning recorded along the product's path.",
  incidents: "Recorded incidents and expected fixture negatives.",
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
  const needsSummary = view === "now" || view === "pipeline" || view === "shop";
  const summary = result.kind === "ready" && needsSummary && runId
    ? await fetchRunSummary(runId) : null;
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
            <section className="run-strip" aria-label="Selected fixture run">
              <div><span className="label">Fixture run</span><code>{result.data.run_id}</code></div>
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
            <footer>Fixture evidence only. Provider connections are shown as recorded.</footer>
          </>
        )}
      </main>
    </div>
  );
}

function ProductProof({ summary, view }: { summary: RunSummary; view: OperatorView }) {
  const showWorkflow = view === "now" || view === "pipeline";
  const showArtifacts = view === "now" || view === "shop";
  const template = summary.artifacts.find((artifact) => artifact.kind === "product_html" &&
    artifact.media_type.split(";")[0]?.trim() === "text/html");
  return <section className="product-proof" aria-label="Stored product proof">
    <div className="proof-heading"><div><p className="eyebrow">Produced product · Fixture only</p>
      <h2>{summary.product_title}</h2></div><span className="state">Production lifecycle: {summary.product_state}</span></div>
    {showWorkflow && <>
      <div className="completion-strip"><div><span className="label">Fixture workflow</span>
        <strong>{summary.fixture_completed ? "Fixture completed" : "Fixture in progress"}</strong>
        {summary.completed_at && <time dateTime={summary.completed_at}>{summary.completed_at}</time>}
      </div><p>Fixture completion records the local proof. Job states below remain as stored; production is not commissioned.</p></div>
      <ol className="job-list" aria-label="Stored workflow jobs">{summary.jobs.map((job) =>
        <li key={job.id}><div><strong>{job.job_type}</strong><code>{job.id}</code></div>
          <span className="state" data-state={job.status}>{job.status}</span></li>)}</ol>
      {summary.jobs.length === 0 && <p className="record-detail">No jobs returned for this workflow.</p>}
    </>}
    {showArtifacts && <div className="artifact-section">
      <div className="artifact-heading"><h3>Produced template</h3>
        {template && <a className="file-link" href={artifactPath(summary.run_id, template.id)} target="_blank" rel="noreferrer">Open template ↗</a>}</div>
      {template ? <iframe className="template-preview" title={summary.product_title + " — stored product preview"}
        src={artifactPath(summary.run_id, template.id)} sandbox="" referrerPolicy="no-referrer" />
        : <p className="record-detail">No stored HTML template returned for this run.</p>}
      <ul className="artifact-list" aria-label="Stored product files">{summary.artifacts.map((artifact) =>
        <li key={artifact.id}><a href={artifactPath(summary.run_id, artifact.id)} target="_blank" rel="noreferrer">
          <span>{artifact.label}<small>{artifact.media_type} · {artifact.byte_size.toLocaleString("en-US")} bytes</small></span><span aria-hidden="true">↗</span>
        </a></li>)}</ul>
      {summary.artifacts.length === 0 && <p className="record-detail">No stored product files returned.</p>}
    </div>}
  </section>;
}
