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
import { computed, ref } from 'vue';
import { RERUN_CONFIG } from '../config';

const rerunFrame = ref(null);

const props = defineProps({
  // 1. 可以是一个本地或远程的 .rrd 文件地址
  // 2. 也可以是 rrd://localhost:9876 形式的实时流地址
  source: {
    type: String,
    default: 'https://demo.rerun.io/v0.15.1/api_demo.rrd'
  }
});

// 向父组件暴露获取 window 的方法
const getWindow = () => {
  return rerunFrame.value?.contentWindow;
};

defineExpose({
  getWindow
});

// 构建 Rerun Web Viewer 的 URL
// 我们利用官方托管的 app.rerun.io，并通过 url 参数传递数据源
const viewerUrl = computed(() => {
  let url = `${RERUN_CONFIG.VIEWER_BASE}?url=${encodeURIComponent(props.source)}`;
  
  // 启用流式控制参数：
  // streaming_enabled=true: 开启时间广播 postMessage 和手动 drop_time_range 接口
  // pause_on_no_data=true: 开启无数据/断档自动暂停保护
  if (RERUN_CONFIG.STREAMING_MODE) {
    url += '&streaming_enabled=true&pause_on_no_data=true';
  }
  
  return url;
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