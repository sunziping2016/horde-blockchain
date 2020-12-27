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
            <v-list-item-avatar>
              <v-icon v-if="value.config.type === 'orderer'">
                mdi-web
              </v-icon>
              <v-icon v-else>
                mdi-book
              </v-icon>
            </v-list-item-avatar>
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
      <v-card-title>客户端配置</v-card-title>
      <v-card-text>
        <v-list>
          <v-list-item
              v-for="(value, name) in this_config"
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
      <v-card-title>交易</v-card-title>
      <v-card-text>
        <v-data-table
            v-model="transaction_selected"
            :headers="transaction_headers"
            :items="transactions"
            item-key="id"
            show-select
        >
          <template #item.hash="{ item }">
            <code style="background-color: transparent">
              {{item.hash}}
            </code>
          </template>
          <template #item.signature="{ item }">
            <code style="background-color: transparent">
              {{item.signature}}
            </code>
          </template>
        </v-data-table>
        <div class="d-flex align-end">
          <v-select
              :items="orderers"
              v-model="transaction_orderer"
              label="排序节点"
              class="mr-4"
              hide-details
          ></v-select>
          <v-btn
              color="primary"
              :loading="transaction_loading"
              :disabled="!transaction_valid"
              @click="submit_transaction"
          >
            提交
          </v-btn>
        </div>
        <v-alert
            class="mt-2"
            v-if="transaction_alert"
            type="error"
        >{{transaction_alert}}</v-alert>
      </v-card-text>
    </v-card>
    <v-card v-if="this_config.type === 'admin'">
      <v-card-title>背书发钱</v-card-title>
      <v-card-text>
        <div class="d-flex align-end">
          <v-select
              :items="endorsers"
              v-model="make_money_endorser"
              label="背书节点"
              class="mr-4"
              hide-details
          ></v-select>
          <v-text-field
              v-model="make_money_amount"
              type="number"
              label="交易额"
              class="mr-4"
              hide-details
          ></v-text-field>
          <v-btn
              color="primary"
              :loading="make_money_loading"
              :disabled="!make_money_valid"
              @click="make_money"
          >
            提交
          </v-btn>
        </div>
        <v-alert
            class="mt-2"
            v-if="make_money_alert"
            type="error"
        >{{make_money_alert}}</v-alert>
      </v-card-text>
    </v-card>
  </div>
</template>

<script>
import { mapState } from 'vuex'

export default {
  name: 'Home',
  data: () => ({
    transaction_headers: [
      {text: '时间', value: 'timestamp'},
      {text: '背书节点', value: 'endorser'},
      {text: '散列值', value: 'hash', sortable: false},
      {text: '签名', value: 'signature', sortable: false},
    ],
    transaction_selected: [],
    transaction_orderer: '',
    transaction_alert: '',
    transaction_loading: false,
    make_money_endorser: '',
    make_money_amount: '',
    make_money_alert: '',
    make_money_loading: false,
  }),
  computed: {
    ...mapState(['peers', 'this_config']),
    endorsers() {
      return Object.values(this.peers)
        .filter(x => x.config.type === 'endorser')
        .map(x => x.config.id)
    },
    orderers() {
      return Object.values(this.peers)
          .filter(x => x.config.type === 'orderer')
          .map(x => x.config.id)
    },
    make_money_valid() {
      return this.make_money_endorser !== '' &&
          parseFloat(this.make_money_amount) > 0
    },
    transaction_valid() {
      return this.transaction_orderer !== '' &&
          this.transaction_selected.length > 0
    },
    transactions() {
      return Object.values(this.$store.state.transactions)
        .map(transaction => ({
          id: transaction.hash,
          timestamp: transaction.timestamp,
          endorser: transaction.endorser,
          hash: transaction.hash.slice(0, 16),
          signature: transaction.signature.slice(0, 16),
        }))
    }
  },
  methods: {
    make_money() {
      if (!this.make_money_valid)
        return
      this.make_money_loading = true
      this.$store.dispatch('make_money', {
        endorser: this.make_money_endorser,
        amount: parseFloat(this.make_money_amount),
      })
        .then(() => {
          this.make_money_alert = ''
        }, error => {
          this.make_money_alert = error.response.data.error.message
        })
        .finally(() => this.make_money_loading = false)
    },
    submit_transaction() {
      if (!this.transaction_valid)
        return
      this.transaction_loading = true
      this.$store.dispatch('submit_transaction', {
        orderer: this.transaction_orderer,
        data: this.transaction_selected.map(x => x.id),
      })
        .then(() => {
          this.transaction_alert = ''
        }, error => {
          this.transaction_alert = error.response.data.error.message
        })
        .finally(() => this.transaction_loading = false)
    }
  }
}
</script>

<style scoped lang="scss">
.home-page {
  max-width: 800px;
  margin: 16px auto;

  .v-card + .v-card {
    margin-top: 16px;
  }
}
</style>
