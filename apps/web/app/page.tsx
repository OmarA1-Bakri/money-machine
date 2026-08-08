import { bootstrapSummary, serviceStatuses } from "../lib/status";

export default function Home() {
  return (
    <main>
      <header className="hero">
        <p className="eyebrow">Operator console · Session 00</p>
        <h1>Bootstrap status</h1>
        <p className="lede">
          This console reports only what the current build can prove. It does not run workflows,
          mutate business state, publish, spend, or contact external services.
        </p>
      </header>

      <section className="summary" aria-labelledby="summary-heading">
        <div>
          <p className="label" id="summary-heading">Current session</p>
          <strong>{bootstrapSummary.currentSession}</strong>
        </div>
        <div>
          <p className="label">Operating mode</p>
          <strong>{bootstrapSummary.mode}</strong>
        </div>
        <div>
          <p className="label">External actions</p>
          <strong>{bootstrapSummary.externalActions ? "Enabled" : "Disabled"}</strong>
        </div>
      </section>

      <section aria-labelledby="services-heading">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Read-only evidence</p>
            <h2 id="services-heading">Service status</h2>
          </div>
          <span className="badge neutral">No live dependencies queried</span>
        </div>

        <div className="status-grid">
          {serviceStatuses.map((service) => (
            <article className="status-card" key={service.name}>
              <div className="status-title">
                <h3>{service.name}</h3>
                <span className={`badge ${service.state}`}>{service.state}</span>
              </div>
              <p>{service.detail}</p>
            </article>
          ))}
        </div>
      </section>

      <footer>
        <p>
          Business transitions: <strong>disabled</strong>. Connect operational data only through
          the API in a later session.
        </p>
      </footer>
    </main>
  );
}
