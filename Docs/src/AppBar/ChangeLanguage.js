// @flow
import Button from "@material-ui/core/Button";
import Typography from "@material-ui/core/Typography";
import i18next from "i18next";
import { useTranslation } from "react-i18next";
import React, { useGlobal } from "reactn";
function change_body(oldlang, setLang) {
  const lang = i18next.language;
  const newDirection = lang === "fa" ? "rtl" : "ltr";
  if (lang !== oldlang) {
    setLang(lang);
  }
  document.body.setAttribute("dir", newDirection);
}
export function ChangeLanguage() {
  const { i18n } = useTranslation();
  const { language } = i18n;
  const new_language: string = language === "fa" ? "en" : "fa";
  const [lang, setLang] = useGlobal("language");

  change_body(lang, setLang);

  return (
    <Button color="inherit" onClick={() => i18n.changeLanguage(new_language)}>
      <Typography>EN/FA</Typography>
    </Button>
  );
}
