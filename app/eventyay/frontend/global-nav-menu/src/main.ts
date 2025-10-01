import { createApp } from 'vue'

import App from './App.vue'

// Note: The ID of the element to mount the Vue app to is hardcoded in the Django template.
createApp(App).mount('#global-nav-menu')
