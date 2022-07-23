import { createApp } from 'vue'
import Buntpapier from 'buntpapier'

import App from './App.vue'
import '~/styles/global.styl'

const app = createApp(App, {
	locale: 'en-ie'
})
app.use(Buntpapier)
app.mount('#app')
