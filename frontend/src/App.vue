<template>
  <div id="app">
    
    <!-- <div class="controls">
      <div class="input-group">
        <label>数据库：</label>
        <input 
          v-model="selectedDB" 
          list="db-options" 
          placeholder="点击选择"
          @focus="handleDBFocus"
          @input="onDBChange"
        >
        <datalist id="db-options">
          <option v-for="dbName in Object.keys(rerunStore.dbStructure)" :key="dbName" :value="dbName" />
        </datalist>
      </div>

      <div class="input-group">
        <label>数据集：</label>
        <input 
          v-model="selectedDataset" 
          list="dataset-options" 
          placeholder="点击选择"
          :disabled="!selectedDB"
          @focus="handleDSFocus"
        >
        <datalist id="dataset-options">
          <option v-for="ds in availableDatasets" :key="ds" :value="ds" />
        </datalist>
      </div>

      <div class="btn-group">
        <button 
          type="button"
          class="generate-btn" 
          @click.stop.prevent="handleCreateSource" 
          :disabled="loading || !selectedDB || !selectedDataset"
        >
          {{ loading ? '...' : '生成数据源URL' }}
        </button>

        <button 
          type="button"
          class="play-btn" 
          @click.stop.prevent="handlePlayData" 
          :disabled="!recordingUuid || playing"
        >
          {{ playing ? '传输中...' : '开始数据传输' }}
        </button>
      </div>

      <div v-if="currentSource" class="result-container">
        <span class="tag">Rerun URL</span>
        <div class="result-box" @click="copyToClipboard" title="点击复制 URL">
          <span class="url-text">{{ currentSource }}</span>
          <span class="copy-icon">{{ copied ? '✅' : '📋' }}</span>
        </div>
      </div>
    </div> -->

    <RerunViewer v-if="currentSource" :source="currentSource" />
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { storeToRefs } from 'pinia';
import RerunViewer from './components/RerunViewer.vue';
import { useRerunStore } from './stores/rerun';
import { API_ENDPOINTS } from './config';

const rerunStore = useRerunStore();
const { recordingUuid, currentSource } = storeToRefs(rerunStore);

const selectedDB = ref('');
const selectedDataset = ref('');
const loading = ref(false);
const playing = ref(false);
const copied = ref(false);

// 直接在 setup 顶层运行，不要等到 onMounted
const params = new URLSearchParams(window.location.search);
const urlParam = params.get('rerun_url');
const uuidParam = params.get('source_uuid');

let heartbeatTimer = null; // 用于存储定时器引用

if (urlParam && uuidParam) {
  // 在组件渲染之前就填入数据
  rerunStore.setRerunInfo(null, urlParam.trim().replace(/\s+/g, '+'), uuidParam);
}

// 核心联动：根据选中的数据库计算数据集列表
const availableDatasets = computed(() => {
  if (!selectedDB.value || !rerunStore.dbStructure) return [];
  return rerunStore.dbStructure[selectedDB.value] || [];
});

// 解决无法重选的问题：点击输入框时清空内容以弹出完整列表
const handleDBFocus = () => {
  selectedDB.value = '';
};

const handleDSFocus = () => {
  selectedDataset.value = '';
};

// 当数据库内容改变时，清空已选的数据集
const onDBChange = () => {
  selectedDataset.value = '';
};

// --- 核心函数：发送心跳 ---
const sendHeartbeat = async () => {
  if (!recordingUuid.value) return;

  try {
    // 这里的 API_ENDPOINTS.HEARTBEAT 对应后端 manager.keep_alive 的路由
    const response = await fetch(API_ENDPOINTS.HEARTBEAT(recordingUuid.value), {
      method: 'POST'
    });
    
    if (response.ok) {
      console.log(`[Heartbeat] 续命成功: ${recordingUuid.value}`);
    } else {
      console.warn("[Heartbeat] 续命失败，后端可能已回收资源");
    }
  } catch (e) {
    console.error("[Heartbeat] 网络错误:", e);
  }
};

// --- 开启心跳循环 ---
const startHeartbeatLoop = () => {
  stopHeartbeatLoop(); // 先清理旧的
  console.log("启动心跳监控...");
  // 每 60 秒发送一次心跳 (过期时间 180s，60s 非常安全)
  heartbeatTimer = setInterval(sendHeartbeat, 60000);
};

// --- 停止心跳循环 ---
const stopHeartbeatLoop = () => {
  if (heartbeatTimer) {
    clearInterval(heartbeatTimer);
    heartbeatTimer = null;
  }
};

// --- 监听 recordingUuid 的变化 ---
// 当获取到新的录制 ID 时，立即发送一次心跳并开启循环
watch(recordingUuid, (newId) => {
  if (newId) {
    sendHeartbeat(); // 立即执行一次
    startHeartbeatLoop();
  } else {
    stopHeartbeatLoop();
  }
});

// 页面初始化：加载后端数据库结构
onMounted(async () => {
  // 1. 解析 URL 参数 (例如: ?rerun_url=rrd://localhost:9876&source_uuid=123-456)
  const params = new URLSearchParams(window.location.search);
  const urlParam = params.get('rerun_url'); // 对应你说的 rerun url
  const uuidParam = params.get('source_uuid'); // 对应你说的 source uuid

  // 2. 如果存在参数，直接存入 Store
  // 这会自动触发 RerunViewer 的更新，因为 currentSource 是响应式的
  if (urlParam || uuidParam) {
    rerunStore.setRerunInfo(
      null,        // app_id (如果没有就不传)
      urlParam,    // connect_url -> 对应 currentSource
      uuidParam    // recording_uuid
    );
    console.log('Detected params:', { urlParam, uuidParam });
  }

  // // 3. 数据库结构加载逻辑
  // try {
  //   const response = await fetch(API_ENDPOINTS.LIST_ALL);
  //   const result = await response.json();
  //   if (result.status === 'success') {
  //     rerunStore.setDbStructure(result.data);
  //   }
  // } catch (e) {
  //   console.error('API Error:', e);
  // }

  // 如果 URL 里直接带了 UUID，触发心跳
  if (recordingUuid.value) {
    sendHeartbeat();
    startHeartbeatLoop();
  }

  if (recordingUuid.value) {
    console.log("正在监控 Rerun 加载进度...");
    
    // 关键改变：等资源下载完，而不是等固定秒数
    await waitForRerunReady(); 
    
    console.log("检测到 Viewer 已就绪，正在启动数据流...");
    await handlePlayData(); 
  }
});

const waitForRerunReady = () => {
  return new Promise((resolve) => {
    const checkInterval = setInterval(() => {
      // 获取所有已加载的资源
      const resources = performance.getEntriesByType('resource');
      
      // 寻找 rerun 的核心 Wasm 文件
      const wasmResource = resources.find(r => 
        r.name.includes('wasm') || r.name.includes('rerun_viewer')
      );

      if (wasmResource) {
        // 只要这个资源出现了，说明下载阶段已完成
        console.log(`✅ 检测到 Rerun 核心束下载完成: ${wasmResource.name}`);
        console.log(`耗时: ${(wasmResource.duration / 1000).toFixed(2)}s`);
        
        clearInterval(checkInterval);
        
        // 下载完后给 1.5s 的“解压与启动”缓冲时间，然后返回
        setTimeout(resolve, 1500); 
      }
    }, 500); // 每 500ms 检查一次
    
    // 设置一个 30 秒的极长超时，防止死循环
    setTimeout(() => {
      clearInterval(checkInterval);
      resolve();
    }, 30000);
  });
};

const handleCreateSource = async () => {
  loading.value = true;
  try {
    const response = await fetch(API_ENDPOINTS.CREATE_SOURCE, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dataset: selectedDB.value, collection: selectedDataset.value })
    });
    const data = await response.json();
    if (data.connect_url) {
      rerunStore.setRerunInfo(data.app_id, data.connect_url, data.recording_uuid);
    }
  } catch (e) {
    alert('请求失败，请检查后端');
  } finally {
    loading.value = false;
  }
};

const handlePlayData = async () => {
  if (!recordingUuid.value) return;
  playing.value = true;
  try {
    await await fetch(API_ENDPOINTS.PLAY_DATA(recordingUuid.value), {method: 'POST'});
  } catch (e) {
    alert('数据传输启动失败');
  } finally {
    playing.value = false;
  }
};

const copyToClipboard = async () => {
  if (!currentSource.value) return;
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(currentSource.value);
    } else {
      const textArea = document.createElement("textarea");
      textArea.value = currentSource.value;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand('copy');
      document.body.removeChild(textArea);
    }
    copied.value = true;
    setTimeout(() => copied.value = false, 2000);
  } catch (err) {
    console.error('Copy failed');
  }
};
</script>

<style scoped>
#app { 
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; 
  color: white; 
  background: #1a1a1a; 
  
  /* 关键修改：让 #app 撑满视口高度 */
  height: 100vh; 
  display: flex;
  flex-direction: column;
  overflow: hidden; /* 防止出现双滚动条 */
}

:deep(.rerun-container) {
  flex: 1; /* 占据剩余全部高度 */
}

.controls { 
  display: flex; 
  align-items: center; 
  gap: 15px; 
  background: #252525; padding: 12px 18px; border-radius: 8px; border: 1px solid #333;
}

.input-group { display: flex; align-items: center; gap: 8px; }
.input-group label { font-size: 13px; color: #999; white-space: nowrap; }

/* 保持你喜欢的扁平化 input 样式 */
input { 
  background: #333; 
  color: #fff; 
  border: 1px solid #444; 
  padding: 8px 12px; 
  border-radius: 4px; 
  width: 160px; 
  outline: none; 
  transition: border-color 0.2s;
}
input:focus { border-color: #4CAF50; }
input:disabled { opacity: 0.4; cursor: not-allowed; }

.btn-group { display: flex; gap: 10px; }
.generate-btn, .play-btn { 
  padding: 8px 16px; border: none; border-radius: 4px; 
  cursor: pointer; font-weight: 600; font-size: 13px; transition: 0.2s;
}

.generate-btn { background: #4CAF50; color: white; }
.generate-btn:hover { background: #45a049; }
.generate-btn:disabled { background: #2a2a2a; color: #666; cursor: not-allowed; }

.play-btn { background: #2196F3; color: white; }
.play-btn:hover { background: #1e88e5; }
.play-btn:disabled { background: #2a2a2a; color: #666; cursor: not-allowed; border: 1px solid #444; }

.result-container { margin-left: auto; display: flex; align-items: center; gap: 10px; }
.tag { font-size: 10px; background: rgba(76, 175, 80, 0.1); color: #4CAF50; padding: 2px 8px; border: 1px solid rgba(76, 175, 80, 0.3); border-radius: 4px; }
.result-box { display: flex; align-items: center; gap: 12px; background: #111; padding: 6px 12px; border-radius: 4px; border: 1px solid #333; cursor: pointer; }
.url-text { font-family: 'Fira Code', monospace; font-size: 12px; color: #888; }
.copy-icon { font-size: 12px; }
</style>