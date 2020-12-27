<template>
  <div class="home-page">
    <v-breadcrumbs
        :items="[{
          text: '首页',
          to: '/'
        }]"
    />
    <v-card>
      <v-card-title>节点拓扑结构</v-card-title>
      <v-card-text>
        <!-- TODO: add visualize graph -->
        <v-list>
          <v-list-item
              v-for="(value, name) in peers"
              :key="name"
              two-line
              :to="`/peer/${name}`"
          >
            <v-list-item-icon>
              <v-icon v-if="value.config.type === 'orderer'">
                mdi-web
              </v-icon>
              <v-icon v-else>
                mdi-book
              </v-icon>
            </v-list-item-icon>
            <v-list-item-content>
              <v-list-item-title>{{name}}</v-list-item-title>
              <v-list-item-subtitle>
                <span >类型：{{value.config.type}}</span>
                <span
                    v-if="value.connections.length"
                    class="ml-2"
                >连接至：{{value.connections.join(',')}}</span>
              </v-list-item-subtitle>
            </v-list-item-content>
          </v-list-item>
        </v-list>
      </v-card-text>
    </v-card>
    <v-card>
      <v-card-title>交易</v-card-title>
    </v-card>
  </div>
</template>

<script>
import { mapState } from 'vuex'

export default {
  name: 'Home',
  computed: {
    ...mapState(['peers'])
  }
}
</script>

<style scoped lang="scss">
.home-page {
  max-width: 800px;
  margin: 0 auto;
}
</style>

<style lang="scss">
.home-page {
  .v-card + .v-card {
    margin-top: 32px;
  }
}
</style>
