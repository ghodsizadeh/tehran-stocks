// @flow
import AppBar from "@material-ui/core/AppBar";
import Button from "@material-ui/core/Button";
import IconButton from "@material-ui/core/IconButton";
import { makeStyles, Theme } from "@material-ui/core/styles";
import Toolbar from "@material-ui/core/ToolBar";
import Typography from "@material-ui/core/Typography";
import ChartIcons from "@material-ui/icons/ShowChartOutlined";
import GithubIcon from "@material-ui/icons/GitHub";
import TwitterIcon from "@material-ui/icons/Twitter";
import CardGiftcardIcon from "@material-ui/icons/CardGiftcard";

import React from "react";
import type { Node } from "react";
import { useTranslation } from "react-i18next";

const useStyles = makeStyles((theme: Theme) => ({
  root: {
    flexGrow: 1
  },

  title: {
    flexGrow: 1
  }
}));

type SLinkProps = {
  icon: Node,
  link: string
};
function SocialLink(props: SLinkProps) {
  const { link, icon } = props;
  return (
    <IconButton href={link} edge="start" color="inherit">
      {icon}
    </IconButton>
  );
}

function ChangeLanguage() {
  const { i18n } = useTranslation();
  const { language } = i18n;
  const new_language: string = language === "fa" ? "en" : "fa";
  return (
    <Button color="inherit" onClick={() => i18n.changeLanguage(new_language)}>
      <Typography>EN/FA</Typography>
    </Button>
  );
}
function TheAppBar() {
  const classes = useStyles();
  const { t } = useTranslation();

  return (
    <div className={classes.root}>
      <AppBar position="static">
        <Toolbar>
          <ChartIcons />
          <Typography variant="h6" className={classes.title}>
            {t("title")}
          </Typography>
          <SocialLink
            link="https://github.com/ghodsizadeh/tehran-stocks"
            icon={<GithubIcon />}
          />
          <SocialLink
            link="https://twitter.com/ghodsizadeh"
            icon={<TwitterIcon />}
          />
          <SocialLink
            link="https://idpay.ir/ghodsizadeh"
            icon={<CardGiftcardIcon />}
          />
          <ChangeLanguage />
        </Toolbar>
      </AppBar>
    </div>
  );
}

export default TheAppBar;
