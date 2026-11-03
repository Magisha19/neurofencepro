import { Link } from "react-router-dom";

export function ScopeFooter() {
  return (
    <footer className="scope-banner" role="note">
      <span className="scope-indicator" aria-hidden="true" />
      <p>
        Toy-model results only. Not evidence of production-model backdoor
        detection.
      </p>
      <Link to="/methodology">Read limitations</Link>
    </footer>
  );
}
