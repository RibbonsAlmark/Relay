<template>
  <div id="app">
    <header>
      <h1>Data Discovery Platform</h1>
    </header>
    
    <div class="controls">
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
    </div>

    <RerunViewer :source="currentSource" />
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue';
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

// 页面初始化：加载后端数据库结构
onMounted(async () => {
  try {
    const response = await fetch(API_ENDPOINTS.LIST_ALL);
    const result = await response.json();
    if (result.status === 'success') {
      rerunStore.setDbStructure(result.data);
    }
  } catch (e) {
    console.error('API Error:', e);
  }
});

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
#app { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; padding: 20px; color: white; background: #1a1a1a; min-height: 100vh; }
header h1 { font-size: 1.2rem; color: #888; margin-bottom: 20px; }

.controls { 
  margin-bottom: 20px; display: flex; align-items: center; gap: 15px; 
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