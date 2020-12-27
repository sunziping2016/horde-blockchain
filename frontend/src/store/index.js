import Vue from 'vue'
import Vuex from 'vuex'
import axios from '@/axios'

Vue.use(Vuex)

export default new Vuex.Store({
  state: {
    this_config: {},
    peers: {},
    transactions: {},
    unconfirmed_blockchains: {},  // key -> (blockchain, count)
    confirmed_blockchains: {},
    messages: [],
    new_message: '',  // for snackbar
    peer_num: Infinity,
  },
  mutations: {
    update_peers(state, connections) {
      state.this_config = connections.self
      state.peers = connections.peers
      const peer_num = Object.keys(state.peers).length
      state.peer_num = peer_num <= 3 ? peer_num : 2 * Math.ceil((peer_num - 1) / 3) + 1
    },
    insert_transaction(state, transaction) {
      Vue.set(state.transactions, transaction.hash, transaction)
    },
    remove_transactions(state, transaction_hashes) {
      for (const hash of transaction_hashes)
        Vue.delete(state.transactions, hash)
    },
    new_blockchain(state, data) {
      const {orderer, blockchain} = data
      const hash = blockchain.hash
      if (state.confirmed_blockchains[hash] !== undefined)
        return
      if (state.unconfirmed_blockchains[hash] !== undefined) {
        state.unconfirmed_blockchains[hash][0] = blockchain
        if (state.unconfirmed_blockchains[hash][1] >= state.peer_num) {
          Vue.set(state.confirmed_blockchains, hash, state.unconfirmed_blockchains[hash][0])
          Vue.delete(state.unconfirmed_blockchains, hash)
          state.new_message = `new blockchain ${hash.slice(0, 16)} generated!`
          state.messages.unshift(state.new_message)
        }
      } else {
        Vue.set(state.unconfirmed_blockchains, hash, [blockchain, 0])
      }
      state.messages.unshift(`new blockchain ${blockchain.hash.slice(0, 16)} from ${orderer}`)
    },
    new_blockchain_verified(state, data) {
      const {peer, hash, verified} = data
      state.messages.unshift(`blockchain ${hash.slice(0, 16)} ${verified ? 'accepted' : 'rejected'} by ${peer}`)
      if (verified) {
        if (state.unconfirmed_blockchains[hash] === undefined) {
          Vue.set(state.unconfirmed_blockchains, hash, [undefined, 0])
        }
        state.unconfirmed_blockchains[hash][1] += 1
        if (state.unconfirmed_blockchains[hash][0] !== undefined &&
          state.unconfirmed_blockchains[hash][1] >= state.peer_num) {
          Vue.set(state.confirmed_blockchains, hash, state.unconfirmed_blockchains[hash][0])
          Vue.delete(state.unconfirmed_blockchains, hash)
          state.new_message = `new blockchain ${hash.slice(0, 16)} generated!`
          state.messages.unshift(state.new_message)
        }
      }
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
})
