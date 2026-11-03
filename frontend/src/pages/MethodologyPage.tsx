import { useQuery } from "@tanstack/react-query";
import { apiRequest, ApiError } from "../api/client";
import type { LimitationsResponse } from "../types/api";

const riskBands = [
  { band: "Low", range: "0–24", className: "risk-badge-low" },
  { band: "Moderate", range: "25–49", className: "risk-badge-moderate" },
  { band: "High", range: "50–74", className: "risk-badge-high" },
  { band: "Critical", range: "75–100", className: "risk-badge-critical" },
];

const componentLabels: Record<string, string> = {
  behavioural_divergence: "Behavioural divergence",
  detector_consensus: "Detector consensus",
  fuzzing_fragility: "Fuzzing fragility",
  detector_disagreement: "Detector disagreement",
};

export function MethodologyPage() {
  const limitations = useQuery({
    queryKey: ["meta", "limitations"],
    queryFn: () => apiRequest<LimitationsResponse>("/meta/limitations"),
  });

  return (
    <main className="page-layout methodology-page">
      <section className="page-heading">
        <div>
          <p className="eyebrow">REFERENCE / SCOPE & METHODS</p>
          <h1>Methodology</h1>
          <p className="panel-copy">
            How this toy-model pipeline produces its measurements and what
            those measurements represent.
          </p>
        </div>
      </section>

      <section aria-labelledby="method-overview" className="panel methodology-panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">MODEL & MEASUREMENTS</p>
            <h2 id="method-overview">How to interpret results</h2>
          </div>
        </div>
        <div className="methodology-intro">
          <article className="methodology-section">
            <h3>Model</h3>
            <p>
              The toy classifier is a binary bag-of-words MLP (CountVectorizer,
              fixed vocabulary, lowercase on). It is not TF-IDF and not a
              transformer.
            </p>
          </article>
          <article className="methodology-section">
            <h3>Detector consensus and disagreement</h3>
            <p>
              Detector consensus is the mean fraction of detectors that flag
              each triggered sample (equal to mean detector recall). Detector
              disagreement is 0 when detectors are unanimous and 1 when evenly
              split; with one detector it is always 0.
            </p>
          </article>
          <article className="methodology-section">
            <h3>Mutation fuzzing</h3>
            <p>
              Fuzzing flip rates measure how mutations affect a fixed
              vocabulary. case_perturbation shows 0% because the vectorizer
              lowercases input. instruction_injection shows 0% because the
              injected words are outside the vocabulary and add no features;
              this classifier cannot follow instructions, so that strategy
              does not measure prompt-injection robustness. encoding_wrap and
              leetspeak flips mostly reflect known words turned into
              out-of-vocabulary tokens, so fuzzing fragility here measures
              vocabulary erosion, not general adversarial robustness.
            </p>
          </article>
          <article className="methodology-section">
            <h3>Provenance and scope</h3>
            <p>
              Provenance labels are SIMULATED, TOY_MODEL_HIDDEN, and
              TRANSFORMER_HIDDEN. Results do not show that any model is free of
              backdoors.
            </p>
          </article>
        </div>
      </section>

      <section
        aria-labelledby="risk-bands-heading"
        className="panel methodology-panel"
      >
        <div className="section-heading">
          <div>
            <p className="eyebrow">RISK SCORE</p>
            <h2 id="risk-bands-heading">Risk bands</h2>
          </div>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">Band</th>
                <th scope="col">Score</th>
              </tr>
            </thead>
            <tbody>
              {riskBands.map(({ band, range, className }) => (
                <tr key={band}>
                  <td>
                    <span className={`risk-badge ${className}`}>
                      <span aria-hidden="true">●</span>
                      <span>{band}</span>
                    </span>
                  </td>
                  <td>{range}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section
        aria-labelledby="limitations-heading"
        className="panel methodology-panel"
      >
        <div className="section-heading">
          <div>
            <p className="eyebrow">SCOPE & LIMITATIONS</p>
            <h2 id="limitations-heading">Limitations</h2>
          </div>
        </div>
        {limitations.isPending && (
          <p className="state-message" role="status">
            Loading methodology…
          </p>
        )}
        {limitations.isError && (
          <p className="form-error methodology-error" role="alert">
            {limitations.error instanceof ApiError
              ? limitations.error.detail
              : "Methodology details could not be loaded."}
          </p>
        )}
        {limitations.data && limitations.data.limitations.length === 0 && (
          <p className="empty-panel">No limitations were returned.</p>
        )}
        {limitations.data && limitations.data.limitations.length > 0 && (
          <div className="limitations-list">
            {limitations.data.limitations.map((item, index) => (
              <article className="limitation-item" key={`${index}-${item}`}>
                <span aria-hidden="true" className="limitation-index">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <p>{item}</p>
              </article>
            ))}
          </div>
        )}
      </section>

      <section
        aria-labelledby="risk-weights-heading"
        className="panel methodology-panel"
      >
        <div className="section-heading">
          <div>
            <p className="eyebrow">RISK SCORE</p>
            <h2 id="risk-weights-heading">Component weights</h2>
          </div>
        </div>
        {limitations.isPending && (
          <p className="state-message" role="status">
            Loading risk weights…
          </p>
        )}
        {limitations.isError && (
          <p className="form-error methodology-error" role="alert">
            Risk weights could not be loaded.
          </p>
        )}
        {limitations.data && (
          <>
            <div className="methodology-api-intro">
              <h3>{limitations.data.risk_score_label}</h3>
            </div>
            {Object.keys(limitations.data.weights).length === 0 ? (
              <p className="empty-panel">No component weights were returned.</p>
            ) : (
              <div className="weights-list">
                {Object.entries(limitations.data.weights).map(([name, weight]) => (
                  <div className="weight-row" key={name}>
                    <span>{componentLabels[name] ?? name.replaceAll("_", " ")}</span>
                    <strong>{weight}</strong>
                  </div>
                ))}
              </div>
            )}
            <p className="weights-note">{limitations.data.weights_note}</p>
          </>
        )}
      </section>
    </main>
  );
}
