import { createMuiTheme } from "@material-ui/core";

export const rtlTheme = createMuiTheme({
  direction: "rtl",
  typography: { fontFamily: "Vazir" },
});
export const ltrTheme = createMuiTheme({
  direction: "ltr",
});

export const bodyDir = document.body.getAttribute("dir");
