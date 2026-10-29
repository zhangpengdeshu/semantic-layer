import { createI18n } from 'vue-i18n'

import en from './locales/en.json'
import zhCN from './locales/zh-CN.json'

const STORAGE_KEY = 'semantic-layer.locale'
const stored = typeof localStorage === 'undefined' ? '' : localStorage.getItem(STORAGE_KEY)
const locale = stored || 'zh-CN'

const i18n = createI18n({
  legacy: false,
  globalInjection: true,
  locale,
  fallbackLocale: 'zh-CN',
  messages: {
    'zh-CN': zhCN,
    en,
  },
})

export default i18n