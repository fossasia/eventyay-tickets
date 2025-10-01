import { createApp } from 'vue'
import Buntpapier from 'buntpapier'

import App from './App.vue'
import '~/styles/global.styl'
import i18n from '~/lib/i18n'

const app = createApp(App, {
	locale: 'en-ie'
})
app.use(Buntpapier)
const lang = document.querySelector("#app").dataset.gettext
app.use(await i18n(lang))
app.mount('#app')
