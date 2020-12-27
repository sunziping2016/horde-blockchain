import Vue from 'vue'
import Vuex from 'vuex'
import axios from '@/axios'

Vue.use(Vuex)

export default new Vuex.Store({
  state: {
    this_config: {},
    peers: {},
    transactions: {},
  },
  mutations: {
    update_peers(state, connections) {
      state.this_config = connections.self
      state.peers = connections.peers
    },
    insert_transaction(state, transaction) {
      Vue.set(state.transactions, transaction.hash, transaction)
    },
    remove_transactions(state, transaction_hashes) {
      for (const hash of transaction_hashes)
        Vue.delete(state.transactions, hash)
    }
  },
  actions: {
    async fetch_peers({commit}) {
      const peers = (await axios.get('/connections')).data.result
      commit('update_peers', peers)
    },
    async make_money({commit}, payload) {
      const transaction = (await axios.post('/transaction/make-money', payload)).data.result
      commit('insert_transaction', transaction)
    },
    async transfer_money({commit}, payload) {
      const transaction = (await axios.post('/transaction/transfer-money', payload)).data.result
      commit('insert_transaction', transaction)
    },
    async submit_transaction({state, commit}, payload) {
      const transactions = payload.data.map(hash => state.transactions[hash])
      await axios.post('/transaction/submit', {
        orderer: payload.orderer,
        data: transactions,
      })
      commit('remove_transactions', payload.data)
    },
  },
  modules: {
  }
})
