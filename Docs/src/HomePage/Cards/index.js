import React from "react";
import { Grid, Typography, Link, makeStyles } from "@material-ui/core";
import MainCard from "./Card";
import HelpIcon from "@material-ui/icons/Help";
import { useTranslation, Trans } from "react-i18next";
import DonateIcon from "@material-ui/icons/FreeBreakfastRounded";
import RunIcon from "@material-ui/icons/DirectionsRunRounded";
const useStyles = makeStyles((theme) => ({
  codeParent: {
    textAlign: "left",
    direction: "ltr",
    borderRadius: "10px",
    background: "black",
    padding: "7px",
  },
  code: { color: "white" },
}));
export default function Cards() {
  const classes = useStyles();
  const { t } = useTranslation();
  return (
    <>
      <Grid container spacing={3}>
        <Grid item xs={12} sm={4}>
          <MainCard
            Icon={<HelpIcon />}
            title={t("titleStart")}
            subheader={t("subheaderStart")}
            content={t("contentStart")}
          >
            <Trans i18nKey="virgol">
              <Typography variant="body2" color="textSecondary" component="p">
                Hello
                <Link href="https://virgool.io/@ghodsizadeh/%D8%A8%D9%88%D8%B1%D8%B3-%D8%AA%D9%87%D8%B1%D8%A7%D9%86-%D8%AF%D8%B1-%D9%BE%D8%A7%DB%8C%D8%AA%D9%88%D9%86-c01c6loigi4z">
                  site
                </Link>
                follow
              </Typography>
            </Trans>
            <Trans i18nKey="github">
              <Typography variant="body2" color="textSecondary" component="p">
                pregit
                <Link href="https://github.com/ghodsizadeh/tehran-stocks">
                  gitsite
                </Link>
                postgit
              </Typography>
            </Trans>
          </MainCard>
        </Grid>
        <Grid item xs={12} sm={4}>
          <MainCard
            Icon={<RunIcon />}
            title={t("titleRun")}
            subheader={t("subheaderRun")}
            content={t("contentRun")}
          >
            <div className={classes.codeParent}>
              <code className={classes.code}>
                $ pip install tehran_stocks
                <br />
                $ python
                <br />
                >>> import tehran_stocks
              </code>
            </div>
          </MainCard>
        </Grid>
        <Grid item xs={12} sm={4}>
          <MainCard
            Icon={<DonateIcon />}
            title={t("titleCoffee")}
            subheader={t("subheaderCoffee")}
            content={t("contentCoffee")}
          >
            <Trans i18nKey="coffeeShop">
              <Typography variant="body2" color="textSecondary" component="p">
                precoffe
                <Link href="https://idpay.ir/ghodsizadeh">coffelink</Link>
                postcoffes
              </Typography>
            </Trans>
          </MainCard>
        </Grid>
      </Grid>
    </>
  );
}
