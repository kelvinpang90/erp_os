import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import LanguageDetector from 'i18next-browser-languagedetector'

import enCommon from './locales/en-US/common.json'
import enMenu from './locales/en-US/menu.json'
import zhCommon from './locales/zh-CN/common.json'
import zhMenu from './locales/zh-CN/menu.json'

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      'en-US': {
        common: enCommon,
        menu: enMenu,
      },
      'zh-CN': {
        common: zhCommon,
        menu: zhMenu,
      },
    },
    fallbackLng: 'en-US',
    defaultNS: 'common',
    interpolation: {
      escapeValue: false, // React already escapes
    },
    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
      lookupLocalStorage: 'erp-lang',
    },
  })

export default i18n
