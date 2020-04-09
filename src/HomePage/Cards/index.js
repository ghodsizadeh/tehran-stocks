import React from "react";
import { Grid } from "@material-ui/core";
import MainCard from "./Card";
import HelpIcon from "@material-ui/icons/Help";
import { useTranslation } from "react-i18next";
import DonateIcon from "@material-ui/icons/FreeBreakfastRounded";
import RunIcon from "@material-ui/icons/DirectionsRunRounded";
export default function Cards() {
  const { t } = useTranslation();
  return (
    <>
      <Grid container spacing={3}>
        <Grid item xs={12} sm={4}>
          <MainCard
            Icon={<HelpIcon />}
            title={t("start.title")}
            subheader={t("start.subheader")}
            content={t("start.content")}
          />
        </Grid>
        <Grid item xs={12} sm={4}>
          <MainCard
            Icon={<RunIcon />}
            title={t("titleRun")}
            subheader={t("subheaderRun")}
            content={t("contentRun")}
          />
        </Grid>
        <Grid item xs={12} sm={4}>
          <MainCard
            Icon={<DonateIcon />}
            title={t("titleCoffee")}
            subheader={t("subheaderCoffee")}
            content={t("contentCoffee")}
          />
        </Grid>
      </Grid>
    </>
  );
}
