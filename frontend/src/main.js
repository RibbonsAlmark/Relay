// import './assets/main.css'

// import { createApp } from 'vue'
// import App from './App.vue'

// createApp(App).mount('#app')


import { createApp } from 'vue'
import { createPinia } from 'pinia' // 增加这行
import App from './App.vue'

import './assets/main.css'

const app = createApp(App)

app.use(createPinia()) // 增加这行
app.mount('#app')