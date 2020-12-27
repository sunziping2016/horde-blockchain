module.exports = {
  "devServer": {
    "proxy": {
      "^/api": {
        "target": "http://127.0.0.1:16489",
        "ws": true,
        "changeOrigin": true
      }
    }
  },
  "transpileDependencies": [
    "vuetify"
  ]
}