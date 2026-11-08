import Logo from "./assets/logo.svg";
import { NavBar, SiteTitle, Version } from "./StyledElements";
import type { StudioFileAction } from "./StudioState";

// ============================================================ //
//                                                              //
//   NAVBAR COMPONENT                                           //
//                                                              //
//   Retains Studio's centered title, menu, version and action.  //
//   File and table events flow upward to the page container.   //
//                                                              //
// ============================================================ //

export default function NavbarComponent(props: {
  version: string;
  menuOpen: boolean;
  canCreateTable: boolean;
  onEventToggleMenu: () => void;
  onEventFileAction: (action: StudioFileAction) => void;
  onEventCreateTable: () => void;
}) {
  // ======================== //
  //                          //
  //   RENDERING              //
  //                          //
  // ======================== //

  return (
    <div className="nav">
      <NavBar>
        {/* File menu */}
        <div className="studio-menu">
          <button type="button" className="studio-menu-toggle" aria-label="File menu" aria-expanded={props.menuOpen} onClick={props.onEventToggleMenu}>☰</button>
          {props.menuOpen && <div className="studio-file-menu" role="menu">
            <button type="button" role="menuitem" onClick={() => props.onEventFileAction("new")}>New document</button>
            <button type="button" role="menuitem" onClick={() => props.onEventFileAction("open")}>Open JSON</button>
            <button type="button" role="menuitem" onClick={() => props.onEventFileAction("export-json")}>Export JSON</button>
            <button type="button" role="menuitem" onClick={() => props.onEventFileAction("export-sql")}>Export SQL</button>
            <button type="button" role="menuitem" disabled={!props.canCreateTable} onClick={() => props.onEventFileAction("namespaces")}>Namespaces</button>
            <button type="button" role="menuitem" disabled={!props.canCreateTable} onClick={() => props.onEventFileAction("enums")}>Enums</button>
          </div>}
        </div>
        {/* Branding and version */}
        <SiteTitle>
          <img src={Logo} alt="site logo" />
          <p>devOS Studio</p>
        </SiteTitle>
        <div className="large-cat">😼</div>
        <Version>
          <p>version: {props.version}</p>
        </Version>
        {/* Table authoring action */}
        <button className="btn create-table-btn" disabled={!props.canCreateTable} onClick={props.onEventCreateTable}>
          Create Table
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 15 15"
            width="12"
            height="12"
            style={{ marginLeft: "0.33em" }}
          >
            <g
              stroke="currentColor"
              strokeWidth="1.75"
              fill="none"
              fillRule="evenodd"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path
                d="M4.497 1H3a2 2 0 00-2 2v9a2 2 0 002 2h9a2 2 0 002-2v-1.5h0"
                opacity=".6"
              ></path>
              <path d="M9 1.008L14 1v5M14 1L6 9"></path>
            </g>
          </svg>
        </button>
      </NavBar>
      <div />
    </div>
  );
}
