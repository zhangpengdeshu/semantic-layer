/// <reference types="vite/client" />

import type { ElMessage, ElMessageBox, ElNotification } from 'element-plus'

declare module 'vue' {
  interface ComponentCustomProperties {
    $message: typeof ElMessage
    $notify: typeof ElNotification
    $msgbox: typeof ElMessageBox
    $alert: typeof ElMessageBox.alert
    $confirm: typeof ElMessageBox.confirm
    $t: (key: string, ...args: any[]) => string
  }
}

declare global {
  interface ImportMetaEnv {
    readonly VITE_API_BASE_URL?: string
    readonly VITE_PROXY_TARGET?: string
  }

  interface ImportMeta {
    readonly env: ImportMetaEnv
  }
}

export {}