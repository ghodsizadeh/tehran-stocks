// @flow
import AppBar from "AppBar";
import React from "react";
import Body from "./Body";
import Cards from "./Cards";
import { makeStyles, Theme } from "@material-ui/core";

const useStyles = makeStyles((theme: Theme) => ({
  root: {
    margin: "15px",
  },
}));

function Home() {
  const classes = useStyles();
  return (
    <div>
      <AppBar />
      <div className={classes.root}>
        <Body />
        <Cards />
      </div>
    </div>
  );
}

export default Home;
