import Vue from 'vue'
import VueRouter from 'vue-router'
import Home from '../views/Home.vue'
import Peer from '../views/Peer.vue'

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
  }
]

const router = new VueRouter({
  mode: 'history',
  base: process.env.BASE_URL,
  routes
})

export default router
