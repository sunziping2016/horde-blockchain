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
