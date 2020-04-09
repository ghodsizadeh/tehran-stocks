import { create } from "jss";
import rtl from "jss-rtl";
import { StylesProvider, jssPreset } from "@material-ui/core/styles";

// Configure JSS
const jss = create({ plugins: [...jssPreset().plugins, rtl()] });

export function RTL(props) {
  return <StylesProvider jss={jss}>{props.children}</StylesProvider>;
}

export function LTR(props) {
  return <StylesProvider>{props.children}</StylesProvider>;
}
