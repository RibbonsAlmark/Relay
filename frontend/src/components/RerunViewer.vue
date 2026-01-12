<template>
  <div class="rerun-container">
    <iframe
      ref="rerunFrame"
      :src="viewerUrl"
      frameborder="0"
      width="100%"
      height="100%"
      allow="autoplay; pwa-overlay"
    ></iframe>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  // 1. 可以是一个本地或远程的 .rrd 文件地址
  // 2. 也可以是 rrd://localhost:9876 形式的实时流地址
  source: {
    type: String,
    default: 'https://demo.rerun.io/v0.15.1/api_demo.rrd'
  }
});

// 构建 Rerun Web Viewer 的 URL
// 我们利用官方托管的 app.rerun.io，并通过 url 参数传递数据源
const viewerUrl = computed(() => {
  const baseUrl = import.meta.env.VITE_RERUN_VIEWER_BASE || 'http://localhost:9092/';
  return `${baseUrl}?url=${encodeURIComponent(props.source)}`;
});
</script>

<style scoped>
.rerun-container {
  width: 100%;
  height: 100%; /* 从 80vh 改为 100%，跟随父级 flex: 1 的高度 */
  border: none; /* 既然全屏了，可以考虑去掉边框更美观 */
  overflow: hidden;
  background-color: #111;
}

iframe {
  display: block; /* 消除 iframe 下方微小的空白间隙 */
}
</style>