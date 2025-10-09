declare module '*.vue' {
  import { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, unknown>
  export default component
}

declare module 'buntpapier' {
  import { Plugin } from 'vue'
  const plugin: Plugin
  export default plugin
}

declare module '~/lib/i18n' {
  import { Plugin } from 'vue'
  const plugin: (locale: string) => Promise<Plugin>
  export default plugin
}
