<template>
  <v-app>
    <v-app-bar
      app
      color="primary"
      dark
    >
      <v-app-bar-title>
        <router-link to="/" tag="span" style="cursor: pointer">
          部落链 - Horde Blockchain
        </router-link>
      </v-app-bar-title>
      <v-spacer></v-spacer>
      <v-menu
          bottom
          close-delay="100"
          content-class="rounded"
          left
          max-height="500"
          offset-y
          open-delay="60"
          open-on-hover
          transition="slide-y-transition"
      >
        <template #activator="{ on, attrs }">
          <v-btn
              icon
              dark
              v-bind="attrs"
              v-on="on"
          >
            <v-icon>mdi-bell</v-icon>
          </v-btn>
        </template>
        <v-list style="min-width: 400px" v-if="$store.state.messages.length">
          <v-list-item v-for="(message, index) in $store.state.messages" :key="index">
            <v-list-item-content>
              <v-list-item-title>{{message}}</v-list-item-title>
            </v-list-item-content>
          </v-list-item>
        </v-list>
        <v-sheet style="min-width: 400px" v-else class="pa-4">
          <div class="text--secondary">No messages</div>
        </v-sheet>
      </v-menu>
    </v-app-bar>
    <v-main>
      <router-view />
    </v-main>
    <v-snackbar
        v-model="snackbar"
        :timeout="2000"
    >
      {{ snackbar_message }}
      <template v-slot:action="{ attrs }">
        <v-btn
            color="red"
            text
            v-bind="attrs"
            @click="snackbar = false"
        >
          Close
        </v-btn>
      </template>
    </v-snackbar>
  </v-app>
</template>

<script>
import {mapState} from 'vuex'

export default {
  name: 'App',
  data: () => ({
    snackbar: false,
    snackbar_message: '',
  }),
  computed: {
    ...mapState(['new_message'])
  },
  watch: {
    new_message() {
      if (this.snackbar) {
        this.snackbar = false
        this.$nextTick(() => {
          this.snackbar_message = this.new_message
          this.snackbar = true
        })
      } else {
        this.snackbar_message = this.new_message
        this.snackbar = true
      }
    }
  }
};
</script>

<style>
</style>
