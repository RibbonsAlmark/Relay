<template>
  <div id="app" :class="{ 'is-dragging': isDragging }">
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

    
    <RerunViewer 
      v-if="isInitialized" 
      ref="rerunViewerRef"
      :source="currentSource" 
    />

    <!-- :on-reload="handleManualReload" -->
    <FloatingButton 
      :on-reload="handleManualReload"
      @drag-start="isDragging = true"
      @drag-end="isDragging = false"
    />

    <div v-if="isDebugMode" class="debug-panel">
      <span class="memory-tag" title="Rerun WASM 内存占用">🧠 {{ memoryUsage }} MB</span>
      <button @click="handleCacheCleanup(20)" title="保留当前帧前后20帧，删除其余数据">✂️ 裁剪(±20)</button>
      <button @click="handleDebugForceGC" title="强制触发 WASM 垃圾回收">🧹 强制GC</button>
      <button @click="handleLogRanges" title="打印当前有效帧范围">📋 帧范围</button>
      <button @click="handleDebugSentinel" title="发送哨兵帧请求">🛡️ 哨兵帧</button>
    </div>
  </div>
</template>

<style>
/* 简单补充一下样式，让显示更美观 */
.memory-tag {
  color: #4caf50;
  font-weight: bold;
  margin-right: 10px;
  background: rgba(0,0,0,0.3);
  padding: 4px 8px;
  border-radius: 4px;
}
</style>

<script setup>
import { ref, onMounted, onUnmounted, computed, watch, nextTick } from 'vue';
import { storeToRefs } from 'pinia';
import RerunViewer from './components/RerunViewer.vue';
import FloatingButton from './components/FloatingButton.vue';
import { useRerunStore } from './stores/rerun';
import { API_ENDPOINTS, RERUN_CONFIG } from './config';
import { ElNotification } from 'element-plus'; 

const rerunStore = useRerunStore();
const { recordingUuid, currentSource } = storeToRefs(rerunStore);

// --- State: UI Control ---
const playing = ref(false);
const isDragging = ref(false); // 控制 iframe 穿透
const isInitialized = ref(false);
const isCleaningUp = ref(false); // 控制紧急清理状态
const isUserInteracting = ref(false); // 用户是否正在交互 (暂停自动加载/GC)
const selectedSourceRange = ref(null); // 当前用户选中的数据源范围 { start, end }
const rerunViewerRef = ref(null); // 引用 RerunViewer 组件实例

// --- State: Streaming & Memory ---
// 有效帧范围列表，元素为 [start, end)，例如: [[0, 100], [200, 300]]
const loadedRanges = ref([]); 
const pendingRanges = ref(new Set()); // 记录正在加载中的区间字符串 "start-end"
const maxFrameIdx = ref(0); // 数据集最大帧数
const currentPlaybackFrame = ref(0); // 当前播放帧索引
const memoryUsage = ref(0); // Rerun 内存使用量 (MB)
let heartbeatTimer = null;
let memoryMonitorTimer = null;

// --- Config ---
// 仅在非生产模式下显示调试面板
const isDebugMode = import.meta.env.MODE !== 'production';

// --- Lifecycle: Initialization ---
// 直接在 setup 顶层运行，不要等到 onMounted
const params = new URLSearchParams(window.location.search);
const urlParam = params.get('rerun_url');
const uuidParam = params.get('source_uuid');

if (urlParam && uuidParam) {
  rerunStore.setRerunInfo(null, urlParam.trim().replace(/\s+/g, '+'), uuidParam);
} else {
  rerunStore.setRerunInfo(null, "", "");
}

// 标记初始化完成
isInitialized.value = true;

// --- Logic: Heartbeat ---
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
  if (heartbeatTimer) {let memoryMonitorTimer = null;
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

// [新增] 检查并恢复自动模式 (当播放超出选中范围时)
const checkAndRestoreAutoMode = (currentFrame) => {
    if (!isUserInteracting.value || !selectedSourceRange.value) return;

    const { start, end } = selectedSourceRange.value;
    // 如果当前帧超出了选中范围 (允许一定的误差 buffer，例如 5 帧)
    const buffer = 5;
    if (currentFrame < start - buffer || currentFrame > end + buffer) {
        console.log(`[Stream] 当前帧 (${currentFrame}) 超出选中范围 [${start}, ${end}]，恢复自动模式`);
        isUserInteracting.value = false;
        selectedSourceRange.value = null;
    }
};

// [新增] 处理数据源选择逻辑
const handleDataSourceSelection = async (source_id, start_time, end_time) => {
    console.log(`[Rerun Selection] Source: ${source_id}, Range: ${start_time} - ${end_time}`);
      
    // 1. 发送清空发送队列请求
    await clearBackendQueues();

    // 2. 设置信号量，暂停到达阈值之后的数据获取触发 + 暂停 GC
    isUserInteracting.value = true;
    selectedSourceRange.value = { start: start_time, end: end_time };
    console.log("[Stream] 用户交互模式已激活 (暂停自动加载与GC)");

    // 3. 获取数据请求 (获取该 source 的范围 + 向右 10 帧)
    const fetchStart = Math.floor(start_time);
    const fetchEnd = Math.ceil(end_time);
    const extraFrames = 10;
    const count = (fetchEnd - fetchStart) + extraFrames;
    
    await handleLoadRange(fetchStart, count);
};

// --- Logic: Iframe Communication ---
const handleRerunMessage = (event) => {
 
  // 处理内存报告

  const usageBytes = data.usage;
  const usageMB = (usageBytes / 1024 / 1024).toFixed(2);
  memoryUsage.value = usageMB;

  // [Auto GC] 如果内存超过阈值，且当前未在清理，触发紧急清理
  if (usageMB > RERUN_CONFIG.STREAMING_MEMORY_LIMIT_MB && !isCleaningUp.value) {
    console.warn(`[AutoGC] 内存占用 (${usageMB} MB) > 阈值，触发清理...`);
    performEmergencyCleanup();
  }
};

onUnmounted(() => {
  stopHeartbeatLoop();
  stopMemoryMonitor();
  // window.removeEventListener('message', handleRerunMessage);
  window.removeEventListener('message', handleGlobalMessage);
});

const handleGlobalMessage = async (event) => {
  // 1. 监听自定义内存报告 (Legacy support if needed)
  if (event.data?.type === "rerun_memory_usage") {
      handleRerunMessage(event.data);
  }

  // 2. 监听打分完成消息
  if (event.data?.type === "RERUN_RATING_COMPLETE") {
    // 校验 UUID 匹配后刷新 UI
    if (event.data.recording_uuid === recordingUuid.value) {
      try {
        const payload = {
          recording_uuid: recordingUuid.value,
          loaded_ranges: loadedRanges.value
        };

        const res = await fetch(API_ENDPOINTS.REFRESH_UI(recordingUuid.value), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        if (res.ok) {
          ElNotification({ title: '评分同步', message: '评分已更新', type: 'success' });
        }
      } catch (e) {
        console.error("[UI Refresh] 网络异常", e);
      }
    }
  }

  // 3. 监听数据源选择消息 (Rerun Data Source Selected)
  if (event.data?.type === "rerun_datasource_selected") {
      const { source_id, start_time, end_time } = event.data;
      handleDataSourceSelection(source_id, start_time, end_time);
  }
};

// --- Lifecycle: Main Initialization ---
onMounted(async () => {
  // 注册全局消息监听 (Rating, Ready, etc.)
  window.addEventListener('message', handleGlobalMessage);

  // 1. 解析 URL 参数
  const params = new URLSearchParams(window.location.search);
  const urlParam = params.get('rerun_url');
  const uuidParam = params.get('source_uuid');

  // 2. 初始化 Store
  if (urlParam || uuidParam) {
    rerunStore.setRerunInfo(null, urlParam, uuidParam);
  }

  // 3. 启动心跳
  if (recordingUuid.value) {
    sendHeartbeat();
    startHeartbeatLoop();
  }

  // 4. 初始化 Rerun Session & Streaming
  if (recordingUuid.value) {
    if (RERUN_CONFIG.STREAMING_MODE) {
        try {
            // 获取 Session 元数据
            const res = await fetch(API_ENDPOINTS.GET_INFO(recordingUuid.value));
            if (res.ok) {
                const info = await res.json();
                if (info.max_frame_idx) maxFrameIdx.value = info.max_frame_idx;
            }
            // 激活流式模式与对齐模式
            await fetch(API_ENDPOINTS.ENABLE_STREAMING(recordingUuid.value), { method: 'POST' });
            await fetch(API_ENDPOINTS.ENABLE_ALIGNMENT(recordingUuid.value), { method: 'POST' });
        } catch (e) {
            console.warn("[Stream] Session 初始化警告", e);
        }
    }
    
    // 等待 Viewer 就绪
    await waitForRerunReady(); 
    
    ElNotification({ title: '加载成功', message: 'Rerun Viewer 已就绪', type: 'success', duration: 3000 });

    if (RERUN_CONFIG.STREAMING_MODE) {
        // 流式模式：预加载首批数据
        await handleLoadRange(0, RERUN_CONFIG.STREAMING_BATCH_SIZE);
        jumpToTime("frame_idx", 0);
        startMemoryMonitor();
    } else {
        // 经典模式：全量加载
        await handlePlayData(); 
    }
  }
});

const waitForRerunReady = () => {
  return new Promise((resolve) => {
    window.addEventListener("message", (event) => { 
        // 安全起见，建议检查 event.origin 
        const data = event.data;

        // 1. 监听 Rerun 就绪信号
        if (data && data.type === "rerun_ready") { 
            console.log("Rerun viewer 已准备好接收数据！"); 
            resolve();
        } 
        
        // 2. 监听时间轴更新信号
        if (data && data.type === "rerun_time_update") { 
            onTimeUpdate(data);
        }
        
        // [新增] 监听行数报告
        if (data && data.type === "rerun_row_count_report") {
             console.log(`[Stream] Rerun 内存行数报告: ${data.count}`);
        }
    }); 
  });
};

// 辅助函数：获取 iframe window
const getRerunWindow = () => {
    // 通过组件 ref 获取，比 querySelector 更安全
    return rerunViewerRef.value?.getWindow();
};

// 让 Rerun Viewer 跳转到指定时间点
const jumpToTime = (timeline, timeVal) => {
    const win = getRerunWindow();
    if (win) {
        console.log(`[Stream] 调用 Rerun Jump: ${timeline} -> ${timeVal}`);
        win.postMessage({
            type: "rerun_set_time",
            recording_id: recordingUuid.value,
            timeline: timeline,
            time: timeVal
        }, "*");
    } else {
        console.warn("[Stream] 无法获取 iframe window，跳转失败");
    }
};

// 调用 Rerun 内部接口清理数据
const callRerunDrop = (start, end) => {
    const win = getRerunWindow();
    if (win) {
        console.log(`[Stream] 调用 Rerun Drop: [${start}, ${end})`);
        
        // 使用 postMessage 发送指令，绕过跨域限制
        win.postMessage({
            type: "rerun_drop_time_range", // 固定指令类型
            recording_id: recordingUuid.value, // 必须匹配
            timeline: "frame_idx", // 时间轴名称
            start: start,
            end: end
        }, "*"); // 允许发送给任意源
    } else {
        console.warn("[Stream] 无法获取 iframe window，数据清理失败");
    }
};

// [新增] 显式触发 Rerun GC
const callRerunForceGC = () => {
    // 由于 Rerun Viewer 运行在 iframe 中，且 force_gc 是 WASM 句柄上的方法
    // 我们无法直接从父页面调用 iframe 内部的 WASM 对象 (跨域隔离/封装)
    // 因此，我们需要发送一个特殊的消息给 iframe，由 iframe 内部的 JS 监听并调用 WASM
    // 假设 Rerun Viewer 的 HTML 宿主代码已经集成了监听 "rerun_force_gc" 消息的逻辑
    const win = getRerunWindow();
    if (win) {
        console.log("[Stream] 发送 GC 指令...");

        // 根据用户指示：postMessage 接口只支持传入一个保护区间
        // 选取当前帧所在的节点窗口为保护帧范围（即当前帧及向前[保护半径]帧）
        const currentFrame = Math.max(0, Math.floor(currentPlaybackFrame.value || 0));
        const radius = RERUN_CONFIG.STREAMING_SAFE_WINDOW_RADIUS || 500;

        const protectedMap = {
            "frame_idx": { // 直接传对象，不要用数组
                min: BigInt(currentFrame),
                max: BigInt(currentFrame + radius)
            }
        };

        win.postMessage({
            type: "rerun_force_gc_everything",
            protected_time_ranges: protectedMap
        }, "*");
    }
};

// [新增] 请求 Rerun 报告行数 (用于验证)
const requestRerunRowCount = () => {
    const win = getRerunWindow();
    if (win) {
        win.postMessage({
            type: "rerun_get_row_count"
        }, "*");
    }
};

// [新增] 调试用的哨兵帧按钮处理
const handleDebugSentinel = async () => {
    if (!recordingUuid.value) return;
    const currentFrame = Math.max(0, Math.floor(currentPlaybackFrame.value || 0));
    console.log(`[Debug] 手动触发哨兵帧请求: frame=${currentFrame}`);
    try {
        await fetch(API_ENDPOINTS.SEND_SENTINEL(recordingUuid.value) + `?frame_idx=${currentFrame}`, { method: 'POST' });
        ElNotification({
            title: '调试',
            message: `已发送哨兵帧 (Frame ${currentFrame})`,
            type: 'success',
            duration: 2000
        });
    } catch (e) {
        console.error("[Debug] 发送哨兵帧失败:", e);
        ElNotification({
            title: '调试失败',
            message: '发送哨兵帧请求失败',
            type: 'error',
            duration: 2000
        });
    }
};

// [新增] 调试用的强制 GC 按钮处理
const handleDebugForceGC = async () => {
    console.log("[Debug] 手动触发强制 GC (执行完整清理流程)");
    await performEmergencyCleanup();
    requestRerunRowCount();
    ElNotification({
        title: '调试',
        message: '已执行完整清理流程',
        type: 'success',
        duration: 2000
    });
};

// [新增] 清空后端发送队列 (通用函数)
const clearBackendQueues = async () => {
    try {
        await fetch(API_ENDPOINTS.CLEAR_QUEUES(recordingUuid.value), { method: 'POST' });
        console.log("[Stream] 后端发送队列已清空");
    } catch (e) {
        console.error("[Stream] 清空发送队列失败:", e);
    }
};

// [新增] 执行紧急清理流程 (封装通用逻辑)
const performEmergencyCleanup = async () => {
    if (isCleaningUp.value) return; // 防止重入
    
    isCleaningUp.value = true;

    console.warn(`[Stream] 执行紧急清理流程...`);

    try {
        // 1. 记录当前帧序号
        const currentFrame = Math.max(0, Math.floor(currentPlaybackFrame.value || 0));
        const radius = RERUN_CONFIG.STREAMING_SAFE_WINDOW_RADIUS || 500;

        // 2. 暂停触发数据请求 (通过 isCleaningUp 标志位控制)
        // 同时清空前端的 pending 队列，避免旧请求回来后干扰状态
        pendingRanges.value.clear();

        // 3. 发送清空发送队列请求
        await clearBackendQueues();

        // 4. 触发强制 GC (callRerunForceGC 内部会保护 [current, current+radius])
        callRerunForceGC();

        // [Fix] 给 Rerun Viewer 一点时间处理 GC 消息，防止哨兵帧请求在 Viewer 繁忙/冻结时被丢弃或忽略
        await new Promise(resolve => setTimeout(resolve, 1000));

        // [Updated] GC 后状态重置逻辑
        // 1. 清空当前有效帧列表
        loadedRanges.value = [];
        
        // 2. (逻辑上) 哨兵帧通常对应当前帧 [currentFrame, currentFrame + 1]
        // 3. (逻辑上) 后续加载的 N 帧 [currentFrame, currentFrame + batchSize]
        // 实际上这两个区间是重叠的，我们直接合并为一个连续区间
        const batchSize = RERUN_CONFIG.STREAMING_BATCH_SIZE;
        let safeEnd = currentFrame + batchSize;
        if (maxFrameIdx.value > 0 && safeEnd > maxFrameIdx.value) {
            safeEnd = maxFrameIdx.value;
        }
        
        // 更新 loadedRanges
        loadedRanges.value.push([currentFrame, safeEnd]);
        console.log(`[Stream] GC后状态重置: loadedRanges=[[${currentFrame}, ${safeEnd}]]`);

        // 5. 请求哨兵帧
        await fetch(API_ENDPOINTS.SEND_SENTINEL(recordingUuid.value) + `?frame_idx=${currentFrame}`, { method: 'POST' });
        console.log("[Stream] 哨兵帧已发送");

        // 6. 向后请求数据
        // 重新启动数据流，确保后续播放流畅
        await handleLoadRange(currentFrame, batchSize);

        await new Promise(resolve => setTimeout(resolve, 1000));
        
        // 7. 跳转到当前帧
        await jumpToTime(currentFrame);
        console.log("[Stream] 已跳转到当前帧");
        
    } catch (e) {
        console.error("[Stream] 紧急清理流程异常:", e);
    } finally {
        isCleaningUp.value = false;
    }
};

// [新增] 打印当前有效帧范围
const handleLogRanges = () => {
    console.log("[Debug] 当前有效帧范围 (loadedRanges):", JSON.parse(JSON.stringify(loadedRanges.value)));
    let totalCached = 0;
    for (const range of loadedRanges.value) {
        totalCached += (range[1] - range[0]);
    }
    console.log(`[Debug] 总缓存帧数: ${totalCached}`);
    ElNotification({
        title: '调试信息',
        message: `当前缓存 ${totalCached} 帧，详情请看控制台`,
        type: 'info',
        duration: 2000
    });
};

const startMemoryMonitor = () => {
    stopMemoryMonitor();
    // 每 2 秒检查一次内存
    memoryMonitorTimer = setInterval(checkMemoryUsage, 2000);
    console.log("[Stream] 内存监控已启动");
};

const stopMemoryMonitor = () => {
    if (memoryMonitorTimer) {
        clearInterval(memoryMonitorTimer);
        memoryMonitorTimer = null;
    }
};

const requestRerunMemory = () => {
    const win = getRerunWindow();
    if (win) {
        win.postMessage({
            type: "rerun_get_memory_usage"
        }, "*");
    }
    // console.log("[Stream] 内存查询请求已发送");
};

const checkMemoryUsage = async () => {
    // 如果正在清理中，跳过检查
    if (isCleaningUp.value) return;
    
    // 如果用户正在交互，暂停定时的内存检查
    if (isUserInteracting.value) return;

    // 向 Rerun Viewer 发起内存查询请求
    // 实际的清理逻辑将在 handleGlobalMessage 的 rerun_memory_report 分支中触发
    requestRerunMemory();
};

// --- Logic: Cache Cleanup (GC) ---
// handleCacheCleanup: 基于内存压力或强制半径进行缓存裁剪
const handleCacheCleanup = async (forceRadius = null) => {
    // 1. 计算当前总缓存帧数
    let totalCached = 0;
    for (const range of loadedRanges.value) totalCached += (range[1] - range[0]);

    // 2. 决定是否触发清理 (目前仅在 forceRadius 不为空时触发，内存监控由 performEmergencyCleanup 负责)
    let shouldCleanup = false;
    let windowRadius = 0;

    if (forceRadius !== null) {
        shouldCleanup = true;
        windowRadius = forceRadius;
        console.warn(`[Stream] 调试触发强制清理: Radius=${windowRadius}`);
    } 
    
    if (!shouldCleanup) return;
    
    // 3. 执行裁剪逻辑
    requestRerunRowCount();
    const currentFrame = currentPlaybackFrame.value;
    const SAFE_WINDOW_RADIUS = windowRadius;
    const keepStart = Math.max(0, currentFrame - 10);
    const keepEnd = currentFrame + SAFE_WINDOW_RADIUS;

    let newRanges = [];
    let hasDropped = false;
    const maxFrame = Number(maxFrameIdx.value);

    // 遍历区间，只保留窗口内部分
    for (const range of loadedRanges.value) {
        let [start, end] = range;
        const originallyContainsFirstFrame = (start === 0);
        const originallyContainsLastFrame = (maxFrame > 0 && end >= maxFrame);
        
        // 裁剪头部
        if (start < keepStart) {
            let dropEnd = Math.min(end, keepStart);
            if (originallyContainsFirstFrame) {
                 if (dropEnd > 1) {
                     callRerunDrop(1, dropEnd);
                     start = dropEnd;
                     hasDropped = true;
                 }
            } else {
                if (start < dropEnd) {
                    callRerunDrop(start, dropEnd);
                    start = dropEnd;
                    hasDropped = true;
                }
            }
        }
        
        // 裁剪尾部
        if (end > keepEnd) {
            const dropStart = Math.max(start, keepEnd);
            if (originallyContainsLastFrame) {
                const protectedStart = maxFrame - 1;
                if (dropStart < protectedStart) {
                    callRerunDrop(dropStart, protectedStart);
                    end = protectedStart;
                    hasDropped = true;
                }
            } else {
                if (dropStart < end) {
                    callRerunDrop(dropStart, end);
                    end = dropStart;
                    hasDropped = true;
                }
            }
        }
        
        // 保留有效部分
        if (start < end) newRanges.push([start, end]);
        
        // 补回保护帧 (首帧/尾帧)
        if (originallyContainsFirstFrame && start > 0) newRanges.push([0, 1]);
        if (originallyContainsLastFrame && end <= maxFrame - 1) newRanges.push([maxFrame - 1, maxFrame]);
    }
    
    newRanges.sort((a, b) => a[0] - b[0]);
    loadedRanges.value = newRanges;
    
    if (hasDropped) {
        console.log("[Stream] 触发显式 GC (因数据裁剪)");
        callRerunForceGC();
    }
    
    requestRerunRowCount();
};

const handleLoadRange = async (startIndex, count) => {
  if (!recordingUuid.value) return;
  
  // 越界检查
  if (maxFrameIdx.value > 0 && startIndex >= maxFrameIdx.value) {
      // console.log(`[Stream] 请求起始点 ${startIndex} 超出最大帧数 ${maxFrameIdx.value}，停止加载`);
      return;
  }
  
  let endIndex = startIndex + count;
  
  // 截断 EndIndex
  if (maxFrameIdx.value > 0 && endIndex > maxFrameIdx.value) {
      endIndex = maxFrameIdx.value;
      // console.log(`[Stream] 截断加载范围至末尾: ${endIndex}`);
  }
  
  // 检查是否与正在进行的请求重叠
  // 简单策略：如果请求完全一致，或者已经被包含在 pending 中，则跳过
  // 为了简化，我们用 "start-end" 字符串作为 key
  const requestKey = `${startIndex}-${endIndex}`;
  if (pendingRanges.value.has(requestKey)) {
      console.log(`[Stream] 请求 ${requestKey} 已在队列中，跳过`);
      return;
  }
  
  pendingRanges.value.add(requestKey);
  
  try {
    console.log(`[Stream] 请求加载范围: [${startIndex}, ${endIndex})`);
    
    const response = await fetch(API_ENDPOINTS.LOAD_RANGE(recordingUuid.value), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        start_index: startIndex, 
        end_index: endIndex 
      })
    });

    if (response.ok) {
      console.log(`[Stream] 范围 [${startIndex}, ${endIndex}) 请求成功`);
      
      // 更新有效帧范围列表 (合并重叠区间)
      const newRange = [startIndex, endIndex];
      const ranges = [...loadedRanges.value, newRange];
      
      // 按起始位置排序
      ranges.sort((a, b) => a[0] - b[0]);
      
      const merged = [];
      if (ranges.length > 0) {
        let current = ranges[0];
        for (let i = 1; i < ranges.length; i++) {
          const next = ranges[i];
          // 如果当前区间与下一个区间重叠或相邻 (例如 [0,100] 和 [100,200])，则合并
          if (current[1] >= next[0]) {
            current[1] = Math.max(current[1], next[1]);
          } else {
            merged.push(current);
            current = next;
          }
        }
        merged.push(current);
      }
      
      loadedRanges.value = merged;
      console.log("[Stream] 当前有效帧范围:", loadedRanges.value);
      
      // 触发缓存清理检查
      handleCacheCleanup();
      
    } else {
      console.warn(`[Stream] 范围加载请求失败: ${response.status}`);
    }
  } catch (e) {
    console.error(`[Stream] 网络错误:`, e);
  } finally {
    pendingRanges.value.delete(requestKey);
  }
};

// --- 流式加载核心逻辑 ---
const onTimeUpdate = (data) => {
    // 这里实现流式加载的触发逻辑
    let currentTime = data.time; // 当前播放时间 (秒)
    let isPlaying = data.is_playing;
    
    // Rerun 的时间可能是秒，也可能是帧索引。
    // 假设这里的 time 对应 frame_idx，如果不确定单位，需要根据 time_str 或业务逻辑转换。
    // 如果 currentTime 是秒，需要根据 FPS 转换为 frame_idx。
    // 这里暂且假设 currentTime 就是 frame_idx (因为我们在后端用 set_time("frame_idx", ...))
    const currentFrameIdx = Math.floor(currentTime);
    
    // 更新全局状态，供清理逻辑使用
    currentPlaybackFrame.value = currentFrameIdx;

    // [新增] 检查是否需要恢复自动模式
    checkAndRestoreAutoMode(currentFrameIdx);

    // console.log(`[StreamDebug] TimeUpdate: frame=${currentFrameIdx}, playing=${isPlaying}`);

    if (isPlaying) {
      handleStreamingPlayback(currentFrameIdx, true);
    } else {
      // 即使暂停了，也要检查是否是因为缺数据导致的暂停
      // 如果当前帧处于已加载区间的末尾，且后面还有数据未加载，则尝试加载
      handleStreamingPlayback(currentFrameIdx, false);
      handleStreamingJump(currentFrameIdx);
    }
};

// 场景 1: 正常播放中的流式加载 (也包括暂停时的缺数据检查)
const handleStreamingPlayback = (currentFrameIdx, isRerunPlaying = false) => {
    // 如果正在进行紧急清理或用户交互，暂停一切数据请求
    if (isCleaningUp.value || isUserInteracting.value) return;

    // 0. 如果已经到达整个数据集的末尾，则不再请求
    // 注意 maxFrameIdx 是开区间上限，所以有效最大帧是 maxFrameIdx - 1
    if (maxFrameIdx.value > 0 && currentFrameIdx >= maxFrameIdx.value - 1) {
        return;
    }

    // 策略：不再只看最后一个区间，而是关注“当前播放区间”的剩余量
    // 动态阈值：暂停时使用更大的阈值，以便在"数据不足导致暂停"的情况下能触发加载
    const BUFFER_THRESHOLD = RERUN_CONFIG.getStreamingThreshold(isRerunPlaying);
    
    // 1. 找到包含当前帧的区间
    let activeRangeIndex = -1;
    for (let i = 0; i < loadedRanges.value.length; i++) {
        const range = loadedRanges.value[i];
        if (currentFrameIdx >= range[0] && currentFrameIdx < range[1]) {
            activeRangeIndex = i;
            break;
        }
    }
    
    if (activeRangeIndex !== -1) {
        // 我们在某个区间内
        const currentRange = loadedRanges.value[activeRangeIndex];
        const currentRangeEnd = currentRange[1];
        const remaining = currentRangeEnd - currentFrameIdx;
        
        // console.log(`[StreamDebug] InRange: [${currentRange}], remaining=${remaining}, threshold=${BUFFER_THRESHOLD}`);

        // 检查是否接近当前区间的末尾
        if (remaining < BUFFER_THRESHOLD) {
            // 准备加载的位置是当前区间的末尾
            const loadStart = currentRangeEnd;
            
            // 检查后面是否还有区间 (处理空隙)
            const nextRange = loadedRanges.value[activeRangeIndex + 1];
            let loadCount = RERUN_CONFIG.STREAMING_BATCH_SIZE;
            
            // 检查是否已经在加载这个位置了 (避免重复触发)
            // 我们检查 [loadStart, loadStart + 1] 是否在 pending 队列的某个请求范围内
            // 由于 pending key 是 "start-end"，我们需要遍历 check
            let isAlreadyLoading = false;
            for (const key of pendingRanges.value) {
                const [pStart, pEnd] = key.split('-').map(Number);
                if (loadStart >= pStart && loadStart < pEnd) {
                    isAlreadyLoading = true;
                    break;
                }
            }
            
            if (isAlreadyLoading) {
                // console.log(`[Stream] 位置 ${loadStart} 正在加载中，跳过`);
                return;
            }

            if (nextRange) {
                // 如果后面还有区间，计算空隙大小
                if (loadStart < nextRange[0]) {
                    const gapSize = nextRange[0] - loadStart;
                    // 如果空隙比标准块小，就只加载空隙大小，避免重复加载下一块的数据
                    if (gapSize < loadCount) {
                        loadCount = gapSize;
                    }
                    console.log(`[StreamDebug] Gap detected: size=${gapSize}, triggering load [${loadStart}, ${loadStart + loadCount})`);
                    // 触发加载
                    handleLoadRange(loadStart, loadCount);
                } else {
                    // console.log(`[StreamDebug] Continuous data (next=${nextRange[0]}), no load needed`);
                }
                // 如果没有空隙 (loadStart == nextRange[0])，说明数据连续，无需加载，自然播放过去即可
            } else if(loadStart != maxFrameIdx.value - 1)  {
                console.log(`[StreamDebug] End of range, no next range. Triggering load [${loadStart}, ${loadStart + loadCount})`);
                // 后面没有区间了，正常往后加载
                handleLoadRange(loadStart, loadCount);
            }
        }
    } else {
        console.log(`[StreamDebug] Out of range: frame=${currentFrameIdx}, triggering immediate load`);
        // 当前帧不在任何已加载区间内
        // 这通常发生在播放指针刚跳出区间，或者处于空隙中
        // 尝试立即加载当前位置
        handleLoadRange(currentFrameIdx, RERUN_CONFIG.STREAMING_BATCH_SIZE);
    }
};

// 场景 2: 用户拖拽/跳转导致的流式加载
const handleStreamingJump = (currentFrameIdx) => {
    // 策略：检查当前帧是否落在任何已加载的区间内
    // 如果不在，说明用户跳到了未加载区域，立即加载
    
    const isCovered = loadedRanges.value.some(range => 
        currentFrameIdx >= range[0] && currentFrameIdx < range[1]
    );
    
    if (!isCovered) {
        // console.log(`[Stream] 检测到跳转至未加载区域: ${currentFrameIdx}`);
        // 从跳转点开始加载
        handleLoadRange(currentFrameIdx, RERUN_CONFIG.STREAMING_BATCH_SIZE);
    }
};

// const handleCreateSource = async () => {
//   loading.value = true;
//   try {
//     const response = await fetch(API_ENDPOINTS.CREATE_SOURCE, {
//       method: 'POST',
//       headers: { 'Content-Type': 'application/json' },
//       body: JSON.stringify({ 
//         dataset: selectedDB.value, 
//         collection: selectedDataset.value,
//         alignment_mode: true // 强制开启对齐模式 (保证同一帧数据打包)
//       })
//     });
//     const data = await response.json();
//     if (data.connect_url) {
//       rerunStore.setRerunInfo(data.app_id, data.connect_url, data.recording_uuid);
//     }
    
//     // 保存最大帧数
//     if (data.max_frame_idx) {
//         maxFrameIdx.value = data.max_frame_idx;
//         console.log(`[Stream] 数据集最大帧数: ${maxFrameIdx.value}`);
//     }
    
//   } catch (e) {
//     alert('请求失败，请检查后端');
//   } finally {
//     loading.value = false;
//   }
// };

const handlePlayData = async () => {
  if (!recordingUuid.value) return;
  playing.value = true;
  try {
    const response = await fetch(API_ENDPOINTS.PLAY_DATA(recordingUuid.value), { method: 'POST' });
    if (response.ok) {
        // 数据真正开始流动的反馈
        ElNotification({
          title: '传输中',
          message: '数据流已连接，正在同步 Frame 序列',
          type: 'info',
          position: 'bottom-right',
          duration: 2000
        });
    }
  } catch (e) {
    ElNotification({
      title: '传输失败',
      message: '无法启动后端数据传输，请检查网络或后端状态',
      type: 'error',
      position: 'bottom-right'
    });
  } finally {
    playing.value = false;
  }
};

// const copyToClipboard = async () => {
//   if (!currentSource.value) return;
//   try {
//     if (navigator.clipboard && window.isSecureContext) {
//       await navigator.clipboard.writeText(currentSource.value);
//     } else {
//       const textArea = document.createElement("textarea");
//       textArea.value = currentSource.value;
//       document.body.appendChild(textArea);
//       textArea.select();
//       document.execCommand('copy');
//       document.body.removeChild(textArea);
//     }
//     copied.value = true;
//     setTimeout(() => copied.value = false, 2000);
//   } catch (err) {
//     console.error('Copy failed');
//   }
// };

// 手动触发重新加载
const handleManualReload = () => {
  if (!recordingUuid.value) return;
  
  const startFrame = currentPlaybackFrame.value;
  const count = RERUN_CONFIG.STREAMING_BATCH_SIZE || 100;
  
  console.log(`[Manual Reload] 用户手动触发加载: Start=${startFrame}, Count=${count}`);
  
  handleLoadRange(startFrame, count);

  // [新增] 显式把手动重载的范围标记为有效
  // 这样可以防止 UI 认为这里没数据而反复触发自动加载
  let endFrame = startFrame + count;
  if (maxFrameIdx.value > 0 && endFrame > maxFrameIdx.value) {
    endFrame = maxFrameIdx.value;
  }
  loadedRanges.value.push([startFrame, endFrame]);
  console.log(`[Manual Reload] 已手动添加有效帧范围: [${startFrame}, ${endFrame}]`);
  
  ElNotification({
    title: '重新加载',
    message: `正在尝试重新加载帧 ${startFrame} 及其后续数据...`,
    type: 'info',
    position: 'bottom-left',
    duration: 2000
  });

  fetch(API_ENDPOINTS.SEND_SENTINEL(recordingUuid.value) + `?frame_idx=${startFrame}`, { method: 'POST' });
  console.log("[Stream] 哨兵帧已发送");
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

/* 扁平化 input 样式 */
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

/* 关键修复：拖拽时禁用 iframe 响应，防止鼠标事件被吞噬 */
.is-dragging :deep(iframe) {
  pointer-events: none;
}

.debug-panel {
  position: absolute;
  top: 10px;
  right: 10px;
  display: flex;
  gap: 8px;
  z-index: 9999;
}

.debug-panel button {
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  border: 1px solid #555;
  padding: 5px 10px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  transition: background 0.2s;
}

.debug-panel button:hover {
  background: rgba(0, 0, 0, 0.8);
  border-color: #777;
}
</style>