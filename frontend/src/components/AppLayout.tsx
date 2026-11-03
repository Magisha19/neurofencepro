import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

export function AppLayout() {
  const { logout } = useAuth();

  return (
    <>
      <header className="topbar app-topbar">
        <NavLink aria-label="NeuroFence overview" className="brand-link" to="/">
          <span className="brand-mark small" aria-hidden="true">
            N
          </span>
          <span>NEUROFENCE</span>
        </NavLink>
        <nav aria-label="Main navigation" className="main-navigation">
          <NavLink
            className={({ isActive }) =>
              `navigation-link${isActive ? " navigation-link-active" : ""}`
            }
            end
            to="/"
          >
            Overview
          </NavLink>
          <NavLink
            className={({ isActive }) =>
              `navigation-link${isActive ? " navigation-link-active" : ""}`
            }
            to="/history"
          >
            History
          </NavLink>
          <NavLink
            className={({ isActive }) =>
              `navigation-link${isActive ? " navigation-link-active" : ""}`
            }
            to="/audit"
          >
            Audit log
          </NavLink>
        </nav>
        <button className="quiet-button" onClick={logout} type="button">
          Sign out
        </button>
      </header>
      <Outlet />
    </>
  );
}
