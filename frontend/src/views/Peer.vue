<script src="../router/index.js"></script>
<template>
  <div class="peer-page">
    <v-breadcrumbs
        :items="[{
          text: '首页',
          to: '/'
        }, {
          text: `节点 ${this_id}`,
          to: `/peer/${this_id}`
        }]"
    />
    <v-card>
      <v-card-title>节点配置</v-card-title>
      <v-card-text>
        <v-list>
          <v-list-item
              v-for="(value, name) in config"
              :key="name"
              two-line
          >
            <v-list-item-content>
              <v-list-item-title >{{name}}</v-list-item-title>
              <v-list-item-subtitle>{{value}}</v-list-item-subtitle>
            </v-list-item-content>
          </v-list-item>
        </v-list>
      </v-card-text>
    </v-card>
    <v-card>
      <v-card-title>连接</v-card-title>
      <v-card-text>
        <v-list>
          <v-list-item
              v-for="connection in connections"
              :key="connection.peer"
              two-line
              :to="`/peer/${connection.peer}`"
          >
            <v-list-item-avatar>
              <v-icon v-if="connection.direction === 'out'">
                mdi-upload
              </v-icon>
              <v-icon v-else>
                mdi-download
              </v-icon>
            </v-list-item-avatar>
            <v-list-item-content>
              <v-list-item-title >{{connection.peer}}</v-list-item-title>
              <v-list-item-subtitle>
                <span >类型：{{peers[connection.peer].config['type']}}</span>
              </v-list-item-subtitle>
            </v-list-item-content>
          </v-list-item>
        </v-list>
      </v-card-text>
    </v-card>
    <v-card>
      <v-card-title>
        <span>账户信息</span>
        <v-spacer />
        <v-btn
            icon
            color="primary"
            @click="fetch_accounts"
        >
          <v-icon>mdi-refresh</v-icon>
        </v-btn>
        <v-switch
            v-model="account_latest"
            label="只显示最新账户"
        ></v-switch>
      </v-card-title>
      <v-card-text>
        <v-data-table
            :loading="account_loading"
            :items-per-page.sync="account_items_per_page"
            :page.sync="account_page"
            :headers="account_headers"
            :items="account_data"
            :server-items-length="account_total"
            :footer-props="{
              'items-per-page-options': [5, 10, 15, 20, 25]
            }"
        ></v-data-table>
      </v-card-text>
    </v-card>
    <v-card>
      <v-card-title>
        <span>区块信息</span>
        <v-spacer />
        <v-btn
            icon
            color="primary"
            @click="fetch_blockchains"
        >
          <v-icon>mdi-refresh</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text>
        <v-data-table
            :loading="blockchains_loading"
            :items-per-page.sync="blockchains_items_per_page"
            :page.sync="blockchains_page"
            :headers="blockchains_headers"
            :items="blockchains_data"
            :server-items-length="blockchains_total"
            :footer-props="{
              'items-per-page-options': [5, 10, 15, 20, 25]
            }"
        >
          <template #item.number="{ item }">
            <router-link
                :to="`/peer/${this_id}/blockchain/${item.number}`"
                tag="span" style="cursor: pointer"
            >
              {{ item.number }}
            </router-link>
          </template>
          <template #item.hash="{ item }">
            <router-link
                :to="`/peer/${this_id}/blockchain/${item.number}`"
                tag="span" style="cursor: pointer"
            >
              <code style="background-color: transparent">
                {{item.hash}}
              </code>
            </router-link>
          </template>
        </v-data-table>
      </v-card-text>
    </v-card>
  </div>
</template>

<script>
import { mapState } from 'vuex'
import axios from '@/axios'

export default {
  data: () => ({
    account_loading: true,
    account_latest: true,
    account_items_per_page: 5,
    account_page: 1,
    account_headers: [
      {text: '账户', value: 'account', sortable: false},
      {text: '版本', value: 'version', sortable: false},
      {text: '余额', value: 'value', sortable: false},
    ],
    account_data: [],
    account_total: 0,
    blockchains_loading: true,
    blockchains_items_per_page: 5,
    blockchains_page: 1,
    blockchains_headers: [
      {text: '序号', value: 'number', sortable: false},
      {text: '散列值', value: 'hash', sortable: false},
    ],
    blockchains_data: [],
    blockchains_total: 0,
  }),
  computed: {
    ...mapState(['peers']),
    this_id() {
      return this.$route.params.peer_id
    },
    config() {
      return this.peers[this.this_id].config
    },
    connections() {
      return this.peers[this.this_id].connections.map(x => ({
            direction: 'out',
            peer: x,
      })).concat(Object.keys(this.peers)
          .filter(peer_id => this.peers[peer_id].connections
              .indexOf(this.this_id) !== -1)
          .map(x => ({
            direction: 'in',
            peer: x,
          }))
      )
    }
  },
  watch: {
    account_latest: 'fetch_accounts',
    account_items_per_page: 'fetch_accounts',
    account_page: 'fetch_accounts',
    blockchains_items_per_page: 'fetch_accounts',
    blockchains_page: 'fetch_accounts',
  },
  methods: {
    fetch_accounts() {
      this.account_loading = true
      axios.get(`/${this.this_id}/accounts`, {
        params: {
          'lateset-version': this.account_latest,
          'offset': this.account_items_per_page * (this.account_page - 1),
          'limit': this.account_items_per_page,
        }
      })
        .then(result => {
          this.account_data = result.data.result.data
          this.account_data.forEach(x => x.value = x.value.toFixed(3))
          this.account_total = result.data.result.total
          this.account_loading = false
        })
    },
    fetch_blockchains() {
      this.blockchains_loading = true
      axios.get(`/${this.this_id}/blockchains`, {
        params: {
          'offset': this.blockchains_items_per_page * (this.blockchains_page - 1),
          'limit': this.blockchains_items_per_page,
        }
      })
          .then(result => {
            this.blockchains_data = result.data.result.data
            this.blockchains_total = result.data.result.total
            this.blockchains_loading = false
          })
    }
  },
  mounted() {
    this.fetch_accounts()
    this.fetch_blockchains()
  }
}
</script>

<style scoped lang="scss">
.peer-page {
  max-width: 800px;
  margin: 16px auto;

  .v-card + .v-card {
    margin-top: 16px;
  }
}
</style>
