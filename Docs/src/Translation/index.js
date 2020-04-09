import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en_dict from "./en/resource";
import fa_dict from "./fa/resource";

i18n
  .use(initReactI18next) // passes i18n down to react-i18next
  .init({
    resources: {
      en: {
        translation: en_dict,
      },
      fa: {
        translation: fa_dict,
      },
    },
    lng: "en",
    fallbackLng: ["en", "fa"],

    interpolation: {
      escapeValue: false,
    },
  });
export default i18n;
