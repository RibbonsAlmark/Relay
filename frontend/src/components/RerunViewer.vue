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
  const baseUrl = 'http://192.168.18.104:9092/';
  return `${baseUrl}?url=${encodeURIComponent(props.source)}`;
});
</script>

<style scoped>
.rerun-container {
  width: 100%;
  height: 80vh; /* 根据需求调整高度 */
  border: 1px solid #444;
  border-radius: 8px;
  overflow: hidden;
  background-color: #111;
}
</style>