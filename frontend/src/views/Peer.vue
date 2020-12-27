<template>
  <div class="peer-page">
    <v-breadcrumbs
        :items="[{
          text: '首页',
          to: '/'
        }, {
          text: peer_id,
          to: `/peer/${peer_id}`
        }]"
    />
    <v-card>
      <v-card-title>{{peer_id}}节点信息</v-card-title>
    </v-card>
  </div>
</template>

<script>
export default {
  computed: {
    peer_id() {
      return this.$route.params.peer_id
    }
  }
}
</script>

<style scoped lang="scss">
.peer-page {
  max-width: 800px;
  margin: 0 auto;
}
</style>
