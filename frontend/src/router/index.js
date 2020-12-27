import Vue from 'vue'
import VueRouter from 'vue-router'
import Home from '../views/Home.vue'
import Peer from '../views/Peer.vue'
import Blockchain from '../views/Blockchain.vue'

Vue.use(VueRouter)

const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home
  },
  {
    path: '/peer/:peer_id',
    name: 'Peer',
    component: Peer
  },
  {
    path: '/peer/:peer_id/blockchain/:blockchain_number',
    name: 'Blockchain',
    component: Blockchain
  }
]

const router = new VueRouter({
  mode: 'history',
  base: process.env.BASE_URL,
  routes
})

export default router
