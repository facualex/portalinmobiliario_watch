import { NavLink, Route, Routes } from "react-router-dom";
import { PropertiesPage } from "./pages/PropertiesPage";
import { SettingsPage } from "./pages/SettingsPage";

const VERTICES_LOGO: Array<[number, number]> = [
  [4, 9.5],
  [11, 4.5],
  [20, 7.5],
  [18.5, 17],
  [9, 20],
  [3, 15],
];

function BrandMark() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
      <path
        d="M4 9.5 L11 4.5 L20 7.5 L18.5 17 L9 20 L3 15Z"
        fill="rgba(29,78,216,0.12)"
        stroke="var(--accent)"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      {VERTICES_LOGO.map(([cx, cy]) => (
        <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r="1.3" fill="var(--accent)" />
      ))}
    </svg>
  );
}

export function App() {
  return (
    <>
      <header className="topbar">
        <div className="brand">
          <BrandMark />
          <span className="brand-name">Lindero</span>
        </div>

        <nav className="toplinks">
          <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : "")}>
            Propiedades
          </NavLink>
          <NavLink
            to="/configuracion"
            className={({ isActive }) => (isActive ? "active" : "")}
          >
            Configuración
          </NavLink>
        </nav>
      </header>

      <Routes>
        <Route path="/" element={<PropertiesPage />} />
        <Route path="/configuracion" element={<SettingsPage />} />
      </Routes>
    </>
  );
}
