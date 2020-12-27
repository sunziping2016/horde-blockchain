import Vue from 'vue'
import Vuex from 'vuex'
import axios from '@/axios'

Vue.use(Vuex)

export default new Vuex.Store({
  state: {
    peers: {}
  },
  mutations: {
    update_peers(state, connections) {
      state.peers = connections
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
