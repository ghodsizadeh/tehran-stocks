// @flow
import React from "react";
import {
  Paper,
  makeStyles,
  Theme,
  Typography,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
} from "@material-ui/core";
import Grid from "@material-ui/core/Grid";

import Bullet from "@material-ui/icons/FiberManualRecord";
import { useTranslation } from "react-i18next";
const useStyles = makeStyles((theme: Theme) => ({
  root: {
    minHeight: "300px",
    flex: 1,
    flexDirection: "column",
    marginBottom: "10px",
    marginTop: "10px",
  },
  header: {
    margin: "8px",
    // width: "55%"
  },
  content: {
    margin: "10px",
    // width: "60%",
  },
  listItem: {
    marginLeft: "-30px",
    textAlign: theme.direction === "rtl" ? "right" : "left",
  },
  bullet: {
    color: "black",
    fontSize: "14px",
  },
  image: {
    borderRadius: "50px",
    // paddingLeft: "30px",
    // paddingRight: "40px",
    height: "auto",
    maxWidth: "90%",
  },
}));

function ShowFeatures() {
  const { t } = useTranslation();
  const features: Array<string> = [
    t("b_fast"),
    t("b_real"),
    t("b_pandas_ready"),
    t("b_exportable"),
  ];
  const classes = useStyles();
  return (
    <List>
      {features.map((item) => (
        <ListItem key={item}>
          <ListItemIcon>
            <Bullet className={classes.bullet} size={10} />
          </ListItemIcon>
          <ListItemText className={classes.listItem} primary={t(item)} />
        </ListItem>
      ))}
    </List>
  );
}
export default function Body() {
  const classes = useStyles();
  const { t } = useTranslation();

  return (
    <Paper elevation={5} className={classes.root}>
      <Grid container spacing={3}>
        <Grid item xs={12} sm={7}>
          <Typography className={classes.header} variant="h2" color="primary">
            {t("header")}
          </Typography>
          <Typography className={classes.content}>
            {t("bodyContent")}
          </Typography>
          <ShowFeatures />
        </Grid>
        <Grid item xs={12} sm={5}>
          <img
            className={classes.image}
            //$FlowFixMe
            src={process.env.PUBLIC_URL + "/stock.jpg"}
            alt="stock"
          />
        </Grid>
      </Grid>
    </Paper>
  );
}
