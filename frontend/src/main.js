import Vue from 'vue'
import App from './App.vue'
import router from './router'
import store from './store'
import vuetify from './plugins/vuetify';

Vue.config.productionTip = false

const uri = (window.location.protocol === 'https:' && 'wss://' || 'ws://') + window.location.host + '/api/ws';
const connection = new WebSocket(uri);
connection.onerror = e => {
  console.error('error:');
  console.error(e);
};
connection.onmessage = e => {
  const data = JSON.parse(e.data)
  if (data.type === 'new-blockchain') {
    store.commit('new_blockchain', data.data)
  } else if (data.type === 'new-blockchain-verified') {
    store.commit('new_blockchain_verified', data.data)
  }
};

store
  .dispatch('fetch_peers')
  .then(() => {
    new Vue({
      router,
      store,
      vuetify,
      render: h => h(App)
    }).$mount('#app')
  })
