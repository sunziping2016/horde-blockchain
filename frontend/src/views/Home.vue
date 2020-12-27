<script src="../store/index.js"></script>
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
      <v-card-text >
          <div style="display:flex; flex-direction: column; align-items:center">
            <svg id="node-topo-svg" :width="width" :height="height" :viewBox="min_x+' '+min_y + ' ' + width+' '+height" >
              <g>
                <router-link v-for="node in Object.values(nodes_layout)" :to="`/peer/${node.id}`" :key="node.id">
                  <foreignObject :x=node.x-node_r :y=node.y-node_r :width=node_r*2 :height=node_r*2>
                    <i v-if="node.config.type === 'orderer'" data-v-fae5bece="" aria-hidden="true" class="v-icon notranslate mdi mdi-web theme--light" v-on:mouseenter="node_onmouseenter(node.id)" v-on:mouseleave="node_onmouseleave(node.id)"></i>
                    <i v-else data-v-fae5bece="" aria-hidden="true" class="v-icon notranslate mdi mdi-book theme--light"  v-on:mouseenter="node_onmouseenter(node.id)" v-on:mouseleave="node_onmouseleave(node.id)"></i>
                  </foreignObject>
                </router-link>
              </g>
              <g>
                <path v-for="edge in edges_layout" :key="edge.source+','+edge.target" class="svg-edge" :d="one_edge(edge.points)"></path>
              </g>
            </svg>
          </div>
        <v-list>
          <v-list-item
              v-for="(value, name) in peers"
              :key="name"
              two-line
              :to="`/peer/${name}`"
              :ref="name+'-list'"
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
          <v-btn text :disabled="transaction_selected.length === 0"
                 @click="remove_selected_transactions">
            <v-icon>mdi-delete</v-icon>
            删除选中的交易
          </v-btn>
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
    <v-card>
      <v-card-title>背书转帐</v-card-title>
      <v-card-text>
        <v-data-table
            :headers="transfer_money_headers"
            :items="transfer_money_items"
        >
          <template v-slot:item.actions="{ item }">
            <v-icon
                small
                @click="delete_transfer_money_item(item)"
            >
              mdi-delete
            </v-icon>
          </template>
        </v-data-table>
        <div class="d-flex align-end">
          <v-text-field
              v-model="transfer_money_item_target"
              label="转帐对方"
              class="mr-4"
              hide-details
          ></v-text-field>
          <v-text-field
              v-model="transfer_money_item_amount"
              type="number"
              label="转帐交易"
              class="mr-4"
              hide-details
          ></v-text-field>
          <v-btn
              color="primary"
              :disabled="!transfer_money_item_valid"
              @click="add_transfer_money_item"
          >
            添加
          </v-btn>
        </div>
        <div class="d-flex align-end">
          <v-select
              :items="endorsers"
              v-model="transfer_money_endorser"
              label="背书节点"
              class="mr-4"
              hide-details
          ></v-select>
          <v-btn
              color="primary"
              :loading="transfer_money_loading"
              :disabled="!transfer_money_valid"
              @click="transfer_money"
          >
            提交
          </v-btn>
        </div>
        <v-alert
            class="mt-2"
            v-if="transfer_money_alert"
            type="error"
        >{{transfer_money_alert}}</v-alert>
      </v-card-text>
    </v-card>
  </div>
</template>

<script>
import { mapState } from 'vuex';
import dagre from 'dagre';

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
    node_r: 12,
    dagre_config: {
      rankdir: "LR",
      nodesep:5,
      ranksep:90,
      acyclicer: "greedy",
      ranker: "tight-tree",
      edgesep: 30
    },
    nodes_layout: [],
    edges_layout: [],
    width:0,
    height:0,
    min_x:Number.MAX_SAFE_INTEGER,
    min_y:Number.MAX_SAFE_INTEGER,
    transfer_money_endorser: '',
    transfer_money_headers: [
      {text: '转帐对象', value: 'target'},
      {text: '转帐金额', value: 'amount'},
      {text: '动作', value: 'actions', sortable: false},
    ],
    transfer_money_item_target: '',
    transfer_money_item_amount: '',
    transfer_money_items: [],
    transfer_money_alert: '',
    transfer_money_loading: false,
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
    transfer_money_valid() {
      return this.transfer_money_endorser !== '' &&
          this.transfer_money_items.length > 0
    },
    transfer_money_item_valid() {
      for (const item of this.transfer_money_items) {
        if (item.target === this.transfer_money_item_target) {
          return false
        }
      }
      return this.transfer_money_item_target !== '' &&
        parseFloat(this.transfer_money_item_amount) > 0
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
  mounted() {
    let that = this;
    // init dagre layout
    let dagre_graph = new dagre.graphlib.Graph();
    dagre_graph.setGraph(that.dagre_config);
    dagre_graph.setDefaultEdgeLabel(function() { return {}; });

    // set nodes:
    for(let peer of Object.values(that.peers)) {
      let npeer = JSON.parse(JSON.stringify(peer));
      npeer.height = npeer.width = that.node_r*2;
      npeer.id = npeer.config.id;
      dagre_graph.setNode(npeer.id, npeer);
      that.nodes_layout.push(npeer);
    }

    // set edges:
    for(let node of that.nodes_layout) {
      for(let target of node.connections) {
        dagre_graph.setEdge(node.id, target);
        that.edges_layout.push([node.id, target]);
      }
    }
    // layout
    dagre.layout(dagre_graph);

    let min_x = Number.MAX_SAFE_INTEGER;
    let min_y = Number.MAX_SAFE_INTEGER;
    let max_x = Number.MIN_SAFE_INTEGER;
    let max_y = Number.MIN_SAFE_INTEGER;
    that.nodes_layout = {};
    dagre_graph.nodes().forEach(n => {
      let nnode = dagre_graph.node(n);
      that.nodes_layout[n] = nnode;
      min_x = Math.min(min_x, nnode.x);
      min_y = Math.min(min_y, nnode.y);
      max_x = Math.max(max_x, nnode.x);
      max_y = Math.max(max_y, nnode.y);
    });

    that.edges_layout = [];
    dagre_graph.edges().forEach(e => {
      let nedge = dagre_graph.edge(e);
      let edge_points = nedge.points;
      nedge.source = e.v;
      nedge.target = e.w;
      that.edges_layout.push(nedge);
      for(let point of edge_points){
        min_x = Math.min(min_x, point.x);
        min_y = Math.min(min_y, point.y);
        max_x = Math.max(max_x, point.x);
        max_y = Math.max(max_y, point.y);
      }
      that.width = max_x-min_x+that.node_r*4;
      that.height = max_y-min_y+that.node_r*4;
      that.min_x = min_x-that.node_r*2;
      that.min_y = min_y-that.node_r*2;
    });
  },
  methods: {
    one_edge : function (points) {
        // const movePoint = (p, x, y, s) => {
        //     return { x: p.x * s + x, y: p.y * s + y }
        // };
        // points = points.map(p => movePoint(p, transX, transY, scale))


        let len = points.length;
        if (len === 0) { return "" }
        let start = `M ${points[0].x} ${points[0].y}`,
            vias = [];

        const getInter = (p1, p2, n) => {
            return `${p1.x * n + p2.x * (1 - n)} ${p1.y * n + p2.y * (1 - n)}`
        };

        const getCurve = (points) => {
            let vias = [],
                len = points.length;
            const ratio = 0.5;
            for (let i = 0; i < len - 2; i++) {
                let p1, p2, p3, p4, p5;
                if (i === 0) {
                    p1 = `${points[i].x} ${points[i].y}`
                } else {
                    p1 = getInter(points[i], points[i + 1], ratio)
                }
                p2 = getInter(points[i], points[i + 1], 1 - ratio);
                p3 = `${points[i + 1].x} ${points[i + 1].y}`;
                p4 = getInter(points[i + 1], points[i + 2], ratio);
                if (i === len - 3) {
                    p5 = `${points[i + 2].x} ${points[i + 2].y}`
                } else {
                    p5 = getInter(points[i + 1], points[i + 2], 1 - ratio)
                }
                let cPath = `M ${p1} L${p2} Q${p3} ${p4} L${p5}`;
                vias.push(cPath);
            }
            return vias
        };
        vias = getCurve(points);
        let pathData = `${start}  ${vias.join(' ')}`;
        return pathData;
    },
    node_onmouseenter: function (nodeid) {
        let that = this;
        that.$refs[nodeid+"-list"][0].$el.focus();
    },
    node_onmouseleave: function (nodeid) {
        let that = this;
        that.$refs[nodeid+"-list"][0].$el.blur();
    },
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
    transfer_money() {
      if (!this.transfer_money_valid)
        return
      this.transfer_money_loading = true
      this.$store.dispatch('transfer_money', {
        endorser: this.transfer_money_endorser,
        data: this.transfer_money_items.map(x => ({
          target: x.target,
          amount: parseFloat(x.amount),
        })),
      })
          .then(() => {
            this.transfer_money_alert = ''
          }, error => {
            this.transfer_money_alert = error.response.data.error.message
          })
          .finally(() => this.transfer_money_loading = false)
    },
    remove_selected_transactions() {
      this.$store.commit('remove_transactions', this.transaction_selected.map(x => x.id))
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
        .finally(() => {
          this.transaction_loading = false
          this.transaction_selected = []
        })
    },
    add_transfer_money_item() {
      if (!this.transfer_money_item_valid)
        return
      this.transfer_money_items.push({
        target: this.transfer_money_item_target,
        amount: parseFloat(this.transfer_money_item_amount).toFixed(3),
      })
    },
    delete_transfer_money_item(item) {
      const index = this.transfer_money_items.findIndex(x =>
        x.target === item.target && x.amount === item.amount
      )
      if (index !== -1) {
        this.transfer_money_items.splice(index, 1)
      }
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

<style lang="scss">
  .svg-node {
    stroke: gainsboro;
    stroke-width: 0.5;
    fill: gainsboro;
  };
  .svg-edge {
    stroke: rgb(127, 127, 127);
    opacity: 1;
    stroke-width: 1;
    fill: None;
  }
</style>
