import Vue from 'vue'
import Vuex from 'vuex'
import axios from '@/axios'

Vue.use(Vuex)

export default new Vuex.Store({
  state: {
    this_config: {},
    peers: {},
  },
  mutations: {
    update_peers(state, connections) {
      state.this_config = connections.this_config
      state.peers = connections.peers
    }
  },
  actions: {
    async fetch_peers({commit}) {
      const peers = (await axios.get('/connections')).data.result
      commit('update_peers', peers)
    }
  },
  modules: {
  }
})
