import Logo from "./assets/logo.svg";
import { NavBar, SiteTitle, Version } from "./StyledElements";

export default function NavbarComponent(props: {
  version: string;
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
        <SiteTitle>
          <img src={Logo} alt="site logo" />
          <p>ORM Builder</p>
        </SiteTitle>
        <div className="large-cat">😼</div>
        <Version>
          <p>version: {props.version}</p>
        </Version>
        <button className="btn create-table-btn" onClick={props.onEventCreateTable}>
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
