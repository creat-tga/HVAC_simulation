import { createI18n } from 'vue-i18n'
import zhCN from './zh-CN'
import enUS from './en-US'

const LOCALE_KEY = 'hvac_locale'

const i18n = createI18n({
  legacy: false,
  locale: localStorage.getItem(LOCALE_KEY) || 'zh-CN',
  fallbackLocale: 'zh-CN',
  messages: {
    'zh-CN': zhCN,
    'en-US': enUS,
  },
})

export function setLocale(locale: string) {
  ;(i18n.global.locale as unknown as { value: string }).value = locale
  localStorage.setItem(LOCALE_KEY, locale)
}

export function getLocale(): string {
  return (i18n.global.locale as unknown as { value: string }).value
}

export default i18n
