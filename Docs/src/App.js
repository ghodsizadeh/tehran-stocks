// @flow
import { Theme, ThemeProvider } from "@material-ui/core";
import Home from "HomePage";
import React, { setGlobal, useGlobal } from "reactn";
import store from "store";
import { ltrTheme, rtlTheme } from "theme";
import "Translation";
import "./App.css";

setGlobal(store);
function App() {
  const [language] = useGlobal("language");

  const theme: Theme = language === "en" ? ltrTheme : rtlTheme;
  console.log("ll", language, theme.direction, theme.typography.fontSize);

  return (
    <ThemeProvider theme={theme}>
      <Home />
    </ThemeProvider>
  );
}

export default App;
