import { NavLink, Route, Routes } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Jobs from "./pages/Jobs";
import Library from "./pages/Library";

export default function App() {
  return (
    <div className="layout">
      <nav className="nav">
        <div className="brand">CCTV AI Search</div>
        <NavLink to="/" end>
          Dashboard
        </NavLink>
        <NavLink to="/library">Video library</NavLink>
        <NavLink to="/jobs">Jobs</NavLink>
        <div className="nav-foot">Local only · nothing leaves this computer</div>
      </nav>
      <main>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/library" element={<Library />} />
          <Route path="/jobs" element={<Jobs />} />
          <Route path="*" element={<p>Page not found.</p>} />
        </Routes>
      </main>
    </div>
  );
}
