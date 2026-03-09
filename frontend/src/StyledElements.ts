import styled from "styled-components";

export const NavBar = styled.nav`
  display: flex;
  flex-direction: row;
  justify-content: space-evenly;
  align-items: center;
  width: 100%;
  height: 80px;
  border: 10px black;
`;

export const Badge = styled.div`
  display: flex;
  width: 43px;
  height: 40px;
  border-radius: 40px;
  background-color: rgb(88, 88, 88);
  justify-content: center;
  align-items: center;
  margin: 20px;
`;

export const DesignNotes = styled.div`
  position: absolute;
  top: 50%;
  left: 130%;
  background-color: white;
  box-shadow: 2px 3px 17px rgb(200, 200, 200);
  width: 300px;
  padding: 20px;
  transform: translate(-50%, -50%);
  border-radius: 20px;
  display: flex;
  flex-direction: column;
  justify-content: space-evenly;
  align-items: center;
  animation: fade-in 1s;
  .cross-btn {
    position: absolute;
    transform: translate(750%, -400%) rotate(45deg);
  }
  textarea {
    width: 100%;
    height: 60px;
    border: none;
    outline: 1px solid #aa5df2;
    resize: none;
  }
  textarea.class {
    width: 100%;
    height: 60px;
    border: none;
    outline: 1px solid rgb(0, 100, 200);
    text-align: center;
    padding: 10px;
    border-radius: 10px;
    color: rgb(68, 68, 68);
    resize: none;
  }

  .add-row-btn {
    height: 40px;
    width: 40px;
    border-radius: 50%;
    color: #8d38cd;
    border: none;
    font-size: 1em;
    cursor: pointer;
    display: flex;
    justify-content: center;
    align-items: center;
    box-shadow: 5px 5px 40px rgb(158, 158, 158);
    outline: none;
  }

  input, select {
    color: rgb(108, 108, 108);
    width: 100%;
    font-weight: 200;
    font-size: 16px;
  }
  h3 {
    background: linear-gradient(
      90deg,
      rgba(0, 0, 255, 1) 0%,
      rgba(238, 130, 238, 1) 100%
    );
    background-repeat: no-repeat;
    -webkit-text-fill-color: transparent;
    -webkit-background-clip: text;
    background-clip: text;
    font-weight: 900;
  }
`;

export const SiteTitle = styled.div`
  font-size: 40px;
  font-weight: 700;
  width: 380px;
  display: flex;
  justify-content: space-evenly;
  p {
    background: linear-gradient(
      90deg,
      rgba(0, 0, 255, 1) 0%,
      rgba(238, 130, 238, 1) 100%
    );
    background-repeat: no-repeat;
    -webkit-text-fill-color: transparent;
    -webkit-background-clip: text;
    background-clip: text;
    font-weight: 900;
    cursor: pointer;

    :hover {
      background-size: 80%;
      animation: animate 6s infinite;
    }
  }

  img {
    width: 59px;
    height: 53px;
    border-radius: 20px;
  }
`;

export const Version = styled.div`
  font-size: 28px;
  font-weight: 400;
  display: flex;
  color: #555555;
  justify-content: space-evenly;
  width: 180px;
  align-items: center;
`;

export const SideBar = styled.div`
  display: flex;
  flex-direction: row;
  justify-content: space-evenly;
  align-items: center;
  width: 100%;

  i:hover {
    color: #8448f5;
  }
`;

export const CheckBoxElement = styled.div`
  /* The container */
  .container {
    width: 190px;
    display: flex;
    align-items: center;
    justify-content: space-around;
    margin: 10px;
    margin-bottom: 0px;
    cursor: pointer;
    background: linear-gradient(
      90deg,
      rgba(0, 0, 255, 1) 0%,
      rgba(238, 130, 238, 1) 100%
    );
    background-repeat: no-repeat;
    -webkit-text-fill-color: transparent;
    -webkit-background-clip: text;
    background-clip: text;
    font-weight: 900;

    -webkit-user-select: none;
    -moz-user-select: none;
    -ms-user-select: none;
    user-select: none;
  }

  /* Hide the browser's default checkbox */
  .container input {
    width: 0;
    opacity: 0;
    cursor: pointer;
  }

  /* Create a custom checkbox */
  .checkmark {
    height: 25px;
    width: 25px;
    background-color: rgb(250, 250, 250);
    border: rgb(209, 215, 238) solid 1px;
    border-radius: 5px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  /* On mouse-over, add a grey background color */
  .container:hover input ~ .checkmark {
    background-color: rgb(245, 245, 245);
  }

  /* When the checkbox is checked, add a background */
  .container input:checked ~ .checkmark {
    background-color: rgb(132, 74, 245);
  }

  /* Show the checkmark when checked */
  .container input:checked ~ .checkmark:after {
    display: block;
  }
`;
