<template>
  <div class="blockchain-page">
    <v-breadcrumbs
        :items="[{
          text: '首页',
          to: '/',
        }, {
          text: `节点 ${this_id}`,
          to: `/peer/${this_id}`,
        }, {
          text: `区块 ${this_number}`,
          to: `/peer/${this_id}/blockchain/${this_number}`,
        }]"
    />
    <v-card>
      <v-card-title>区块信息</v-card-title>
      <v-card-text v-if="blockchain !== null">
        <v-list>
          <v-list-item two-line>
            <v-list-item-content>
              <v-list-item-title>序号</v-list-item-title>
              <v-list-item-subtitle>{{blockchain.number}}</v-list-item-subtitle>
            </v-list-item-content>
          </v-list-item>
          <v-list-item two-line>
            <v-list-item-content>
              <v-list-item-title>上一区块散列值</v-list-item-title>
              <v-list-item-subtitle>
                <code
                    v-if="blockchain.number <= 1"
                    style="background-color: transparent"
                >
                  {{blockchain.prev_hash}}
                </code>
                <router-link
                    v-else
                    :to="`/peer/${this_id}/blockchain/${blockchain.number - 1}`"
                    tag="div" style="cursor: pointer"
                >
                  <code style="background-color: transparent">
                    {{blockchain.prev_hash}}
                  </code>
                </router-link>
              </v-list-item-subtitle>
            </v-list-item-content>
          </v-list-item>
          <v-list-item two-line>
            <v-list-item-content>
              <v-list-item-title>当前前区块散列值</v-list-item-title>
              <v-list-item-subtitle>
                <code style="background-color: transparent">
                  {{blockchain.hash}}
                </code>
              </v-list-item-subtitle>
            </v-list-item-content>
          </v-list-item>
          <v-list-item two-line>
            <v-list-item-content>
              <v-list-item-title>时间</v-list-item-title>
              <v-list-item-subtitle>{{blockchain.timestamp}}</v-list-item-subtitle>
            </v-list-item-content>
          </v-list-item>
          <v-list-group
              :value="true"
          >
            <template v-slot:activator>
              <v-list-item-content>
                <v-list-item-title>交易</v-list-item-title>
              </v-list-item-content>
            </template>
            <div
                v-for="(transaction, index) in blockchain.transactions"
                :key="transaction.hash"
            >
              <v-divider v-if="index !== 0"></v-divider>
              <v-subheader>交易 {{index + 1}}</v-subheader>
              <v-list-item two-line>
                <v-list-item-content>
                  <v-list-item-title>背书节点</v-list-item-title>
                  <v-list-item-subtitle>{{transaction.endorser}}</v-list-item-subtitle>
                </v-list-item-content>
              </v-list-item>
              <v-list-item two-line>
                <v-list-item-content>
                  <v-list-item-title>时间</v-list-item-title>
                  <v-list-item-subtitle>{{transaction.timestamp}}</v-list-item-subtitle>
                </v-list-item-content>
              </v-list-item>
              <v-list-item two-line>
                <v-list-item-content>
                  <v-list-item-title>交易签名</v-list-item-title>
                  <v-list-item-subtitle>
                    <code style="background-color: transparent">
                      {{transaction.signature}}
                    </code>
                  </v-list-item-subtitle>
                </v-list-item-content>
              </v-list-item>
              <v-list-group
                  :value="true"
              >
                <template v-slot:activator>
                  <v-list-item-content>
                    <v-list-item-title>更改</v-list-item-title>
                  </v-list-item-content>
                </template>
                <div
                    v-for="(mutation, index) in transaction.mutations"
                    :key="mutation.hash"
                >
                  <v-divider v-if="index !== 0"></v-divider>
                  <v-subheader>更改 {{index + 1}}</v-subheader>
                  <v-list-item two-line>
                    <v-list-item-content>
                      <v-list-item-title>账户</v-list-item-title>
                      <v-list-item-subtitle>{{mutation.account}}</v-list-item-subtitle>
                    </v-list-item-content>
                  </v-list-item>
                  <v-list-item two-line>
                    <v-list-item-content>
                      <v-list-item-title>旧状态</v-list-item-title>
                      <v-list-item-subtitle>
                        版本 {{mutation.prev_account_state.version}}：
                        金额 {{mutation.prev_account_state.value}}
                      </v-list-item-subtitle>
                    </v-list-item-content>
                  </v-list-item>
                  <v-list-item two-line>
                    <v-list-item-content>
                      <v-list-item-title>新状态</v-list-item-title>
                      <v-list-item-subtitle>
                        版本 {{mutation.next_account_state.version}}：
                        金额 {{mutation.next_account_state.value}}
                      </v-list-item-subtitle>
                     </v-list-item-content>
                  </v-list-item>
                </div>
              </v-list-group>
            </div>
          </v-list-group>
        </v-list>
      </v-card-text>
      <v-card-text v-else class="d-flex justify-center">
        <v-progress-circular
            indeterminate
            color="primary"
        ></v-progress-circular>
      </v-card-text>
    </v-card>
  </div>
</template>

<script>
import axios from '@/axios'

export default {
  computed: {
    this_id() {
      return this.$route.params.peer_id
    },
    this_number() {
      return this.$route.params.blockchain_number
    },
  },
  watch: {
    this_number: 'fetch_blockchain',
  },
  data: () => ({
    blockchain: null,
  }),
  methods: {
    fetch_blockchain() {
      this.blockchain = null
      axios.get(`/${this.this_id}/blockchains/${this.this_number}`)
        .then(result => {
          this.blockchain = result.data.result
        })
    }
  },
  mounted() {
    this.fetch_blockchain()
  }
}
</script>

<style scoped lang="scss">
.blockchain-page {
  max-width: 800px;
  margin: 16px auto;

  .v-card + .v-card {
    margin-top: 16px;
  }
}
</style>
