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
