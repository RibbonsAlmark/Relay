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

// const selectedDB = ref('');
// const selectedDataset = ref('');
// const loading = ref(false);
const playing = ref(false);
// const copied = ref(false);

// 流式加载状态管理
// 有效帧范围列表，元素为 [start, end)
// 例如: [[0, 100], [200, 300]]
const loadedRanges = ref([]); 
const pendingRanges = ref(new Set()); // 记录正在加载中的区间字符串 "start-end"
const maxFrameIdx = ref(0); // 数据集最大帧数
const currentPlaybackFrame = ref(0); // 当前播放帧索引
const isDragging = ref(false); // 控制 iframe 穿透
const isCleaningUp = ref(false); // 控制紧急清理状态
const memoryUsage = ref(0); // Rerun 内存使用量 (MB)

// 仅在开发模式下显示调试面板
const isDebugMode = import.meta.env.DEV;

// 直接在 setup 顶层运行，不要等到 onMounted
const params = new URLSearchParams(window.location.search);
const urlParam = params.get('rerun_url');
const uuidParam = params.get('source_uuid');

const isInitialized = ref(false);
const rerunViewerRef = ref(null); // 引用 RerunViewer 组件实例

let heartbeatTimer = null; // 用于存储定时器引用

if (urlParam && uuidParam) {
  rerunStore.setRerunInfo(null, urlParam.trim().replace(/\s+/g, '+'), uuidParam);
} else {
  // 如果没有参数，也给 Store 塞个空值，防止组件内部报错
  rerunStore.setRerunInfo(null, "", "");
}

// 标记初始化完成
isInitialized.value = true;

// // 核心联动：根据选中的数据库计算数据集列表
// const availableDatasets = computed(() => {
//   if (!selectedDB.value || !rerunStore.dbStructure) return [];
//   return rerunStore.dbStructure[selectedDB.value] || [];
// });

// // 解决无法重选的问题：点击输入框时清空内容以弹出完整列表
// const handleDBFocus = () => {
//   selectedDB.value = '';
// };

// const handleDSFocus = () => {
//   selectedDataset.value = '';
// };

// // 当数据库内容改变时，清空已选的数据集
// const onDBChange = () => {
//   selectedDataset.value = '';
// };

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

// --- 全局消息监听处理 ---
const handleRerunMessage = (event) => {
  const data = event.data;
  // console.log("[Rerun Message]", data);
  // 过滤消息，只处理 rerun_memory_usage 类型
  if (data && data.type === 'rerun_memory_usage') {
    const usageBytes = data.usage;
    // 转换为 MB
    const usageMB = (usageBytes / 1024 / 1024).toFixed(2);
    memoryUsage.value = usageMB;
    // console.log("[Stream] Rerun 内存使用量:", usageMB, "MB");

    // --- 自动 GC 触发逻辑 ---
    // 如果内存超过阈值，且当前没有正在执行清理
    if (usageMB > RERUN_CONFIG.STREAMING_MEMORY_LIMIT_MB && !isCleaningUp.value) {
      console.warn(`[AutoGC] 内存占用 (${usageMB} MB) 超过阈值 (${RERUN_CONFIG.STREAMING_MEMORY_LIMIT_MB} MB)，触发紧急清理...`);
      performEmergencyCleanup();
    }
  }
};

onMounted(() => {
  window.addEventListener('message', handleRerunMessage);
});

onUnmounted(() => {
  stopHeartbeatLoop();
  window.removeEventListener('message', handleRerunMessage);
});
const handleGlobalMessage = async (event) => {
  // 监听 Rerun 内存报告 (用户自定义接口)
  if (event.data?.type === "rerun_memory_report") {
      const memoryUsageBytes = event.data.usageBytes;
      const memoryUsedMB = memoryUsageBytes / (1024 * 1024);
      const MEMORY_LIMIT = RERUN_CONFIG.STREAMING_MEMORY_LIMIT_MB || 1500;

      console.log(`[Stream] Rerun 内存报告: ${memoryUsedMB.toFixed(1)} MB`);

      if (memoryUsedMB > MEMORY_LIMIT) {
          console.warn(`[Stream] Rerun 内存超标 (${memoryUsedMB.toFixed(1)}MB > ${MEMORY_LIMIT}MB), 触发紧急清理流程...`);
          await performEmergencyCleanup();
      }
      return;
  }

  // 监听打分完成消息
  if (event.data?.type === "RERUN_RATING_COMPLETE") {
    console.log("收到打分完成消息:", event.data);
    
    // 1. 校验 UUID 是否匹配当前会话
    if (event.data.recording_uuid === recordingUuid.value) {
      console.log("UUID 匹配，正在请求刷新 UI...");
      
      try {
        // 2. 构造刷新请求，附带当前已加载的区间
        // 注意：loadedRanges 是 Ref 对象，需要取 .value
        const payload = {
          recording_uuid: recordingUuid.value,
          loaded_ranges: loadedRanges.value
        };

        const res = await fetch(API_ENDPOINTS.REFRESH_UI(recordingUuid.value), {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(payload)
        });

        if (res.ok) {
          console.log("[UI Refresh] 刷新请求发送成功");
          ElNotification({
            title: '评分同步',
            message: '评分已更新，正在刷新界面...',
            type: 'success',
            duration: 2000
          });
        } else {
          console.warn("[UI Refresh] 刷新请求失败", res.status);
        }
      } catch (e) {
        console.error("[UI Refresh] 网络异常", e);
      }
    } else {
      console.log(`UUID 不匹配 (期望: ${recordingUuid.value}, 收到: ${event.data.recording_uuid})，忽略消息`);
    }
  }
};

// 页面初始化
onMounted(async () => {
  // 注册全局消息监听
  window.addEventListener('message', handleGlobalMessage);

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
    
    // 如果是直连模式 (URL带参数)，需要额外获取一次 Session 信息 (主要是 max_frame_idx)
    if (RERUN_CONFIG.STREAMING_MODE) {
        try {
            // 1. 获取 Session 信息
            const res = await fetch(API_ENDPOINTS.GET_INFO(recordingUuid.value));
            if (res.ok) {
                const info = await res.json();
                if (info.max_frame_idx) {
                    maxFrameIdx.value = info.max_frame_idx;
                    console.log(`[Stream] 初始化获取最大帧数: ${maxFrameIdx.value}`);
                }
            }
            
            // 2. 显式通知后端开启流式模式 (以防 Session 不是通过 create_source 创建的)
            await fetch(API_ENDPOINTS.ENABLE_STREAMING(recordingUuid.value), { method: 'POST' });
            
            // 3. 显式通知后端开启对齐模式 (推荐流式模式下开启以减少抖动)
            await fetch(API_ENDPOINTS.ENABLE_ALIGNMENT(recordingUuid.value), { method: 'POST' });
            
            console.log("[Stream] 已通知后端开启流式模式 & 对齐模式");
            
        } catch (e) {
            console.warn("[Stream] 初始化 Session 失败", e);
        }
    }
    
    // 关键改变：等资源下载完，而不是等固定秒数
    await waitForRerunReady(); 
    
    console.log("检测到 Viewer 已就绪，正在启动数据流...");

    ElNotification({
      title: '加载成功',
      message: 'Rerun Viewer 已就绪，正在启动数据传输流...',
      type: 'success',
      position: 'bottom-right',
      duration: 3000 // 3秒后自动关闭
    });

    if (RERUN_CONFIG.STREAMING_MODE) {
        // 如果开启了流式模式，这里不再自动调用 handlePlayData
        // 而是通过监听 rerun_time_update 事件，在后续逻辑中动态触发 load_range
        console.log("【流式模式】已就绪，正在预加载初始数据...");
        // 预加载第一批数据
        await handleLoadRange(0, RERUN_CONFIG.STREAMING_BATCH_SIZE);
        
        // 强制跳转到第0帧，确保播放器指针归位
        jumpToTime("frame_idx", 0);

        // [新增] 启动内存监控
        startMemoryMonitor();
    } else {
        // 经典模式：一次性全量加载
        await handlePlayData(); 
    }
  }
});

onUnmounted(() => {
  stopHeartbeatLoop();
  stopMemoryMonitor();
  window.removeEventListener('message', handleGlobalMessage);
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
        await fetch(API_ENDPOINTS.CLEAR_QUEUES(recordingUuid.value), { method: 'POST' });
        console.log("[Stream] 后端发送队列已清空");

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

// --- 内存监控 ---
let memoryMonitorTimer = null;

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

    // 向 Rerun Viewer 发起内存查询请求
    // 实际的清理逻辑将在 handleGlobalMessage 的 rerun_memory_report 分支中触发
    requestRerunMemory();
};

// --- 缓存清理逻辑 (基于内存压力的动态窗口策略) ---
// forceRadius: 如果传入数字，则忽略内存检查，强制使用该半径进行裁剪
const handleCacheCleanup = async (forceRadius = null) => {
    // 1. 检查内存使用情况 (仅 Chrome/Edge 支持 performance.memory)
    // 注意：内存超标检查已移至独立监控 (checkMemoryUsage)
    // 此处主要处理 forceRadius 带来的手动裁剪，或者保留原有的窗口裁剪逻辑作为辅助
    
    // 计算当前总缓存帧数
    let totalCached = 0;
    for (const range of loadedRanges.value) {
        totalCached += (range[1] - range[0]);
    }

    // 2. 决定是否触发清理
    let shouldCleanup = false;
    let windowRadius = 0;

    if (forceRadius !== null) {
        // 调试模式：强制清理
        shouldCleanup = true;
        windowRadius = forceRadius;
        console.warn(`[Stream] 调试触发强制清理: Radius=${windowRadius}`);
    } 
    
    // 如果既不是强制清理，内存监控也会负责紧急清理，这里可以只做常规维护
    // 但如果用户希望在内存没满但 range 太长时也修剪一下，可以保留逻辑。
    // 不过按照指令 "直接添加对内存用量的监听，达到阈值直接触发performEmergencyCleanup"，
    // 这里的内存检查可以移除了。
    
    if (!shouldCleanup) return;
    
    // [调试] 清理前记录行数
    requestRerunRowCount();
    
    const currentFrame = currentPlaybackFrame.value;
    const SAFE_WINDOW_RADIUS = windowRadius;
    
    // 计算保留窗口范围 [keepStart, keepEnd]
    // 策略修改：只保留当前播放点往后的数据 (和极少量的回头缓冲)
    // keepStart = currentFrame - 小缓冲 (例如 10 帧，防止手滑拖动时立刻黑屏)
    // keepEnd = currentFrame + SAFE_WINDOW_RADIUS
    const keepStart = Math.max(0, currentFrame - 10);
    const keepEnd = currentFrame + SAFE_WINDOW_RADIUS;

    let newRanges = [];
    let hasDropped = false;

    // 遍历所有区间，只保留在窗口内的部分
    for (const range of loadedRanges.value) {
        let [start, end] = range;
        
        // 标记该区间是否原本包含第0帧
        const originallyContainsFirstFrame = (start === 0);
        // 标记该区间是否原本包含最后一帧
        // 关键修复: 确保类型一致 (Number) 且使用 >= 容错
        const maxFrame = Number(maxFrameIdx.value);
        const originallyContainsLastFrame = (maxFrame > 0 && end >= maxFrame);
        
        // 1. 裁剪头部：[start, keepStart)
        if (start < keepStart) {
            let dropEnd = Math.min(end, keepStart);
            
            // 保护第0帧 [0, 1]
            if (originallyContainsFirstFrame) {
                 if (dropEnd > 1) {
                     // 删掉 [1, dropEnd)
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
        
        // 2. 裁剪尾部：[keepEnd, end)
        if (end > keepEnd) {
            const dropStart = Math.max(start, keepEnd);
            
            // 保护最后一帧 [max-1, max]
            if (originallyContainsLastFrame) {
                const protectedStart = maxFrame - 1;
                // 只有当删除范围确实会覆盖到保护帧时，才限制删除
                // 修正：只要 dropStart 小于 maxFrame，就有可能误删
                // 我们必须保证 drop 范围不能触碰 [protectedStart, maxFrame]
                
                // 如果建议的删除起点在保护区之前
                if (dropStart < protectedStart) {
                    // 安全删除范围是 [dropStart, protectedStart)
                    callRerunDrop(dropStart, protectedStart);
                    // 更新 end 为 protectedStart，意味着保留了 [protectedStart, end] 即 [protectedStart, maxFrame]
                    end = protectedStart;
                    hasDropped = true;
                } else {
                    // 如果建议的删除起点已经在保护区内（或之后），则完全不删
                    // 例如 dropStart=4473, protectedStart=4473 -> 不删
                    // 这样就保护了尾部
                }
            } else {
                if (dropStart < end) {
                    callRerunDrop(dropStart, end);
                    end = dropStart;
                    hasDropped = true;
                }
            }
        }
        
        // 3. 保留有效部分
        if (start < end) {
            newRanges.push([start, end]);
        }
        
        // 4. 补回第0帧
        // 修正: 当 start 被裁剪到 > 0 时（哪怕是 1），也需要补回 [0, 1]，否则 [0, 1] 就会丢失
        if (originallyContainsFirstFrame && start > 0) {
            console.log(`[Stream] 触发首帧保护: 恢复 [0, 1)`);
            newRanges.push([0, 1]);
        }

        // 5. 补回最后一帧
        if (originallyContainsLastFrame) {
             const lastFrameStart = maxFrame - 1;
             // 检查当前 range 是否还包含尾帧
             // 如果 end 被裁剪到了 protectedStart (maxFrame-1) 或更小，说明尾帧部分不在当前的 [start, end) 里了
             // (因为上面步骤2里，如果原本包含尾帧，我们强制把 end 设为了 protectedStart，保留下来的区间变成了 [start, protectedStart])
             // 等等，这里的逻辑有点绕。
             // 如果步骤2保护生效，end 变成了 protectedStart。那么 [start, end) 确实不包含尾帧了。
             // 所以这里必须补回 [protectedStart, maxFrame]。
             
             // 之前的逻辑：if (end <= lastFrameStart)
             // 如果保护生效，end === lastFrameStart，满足条件 -> 补回。
             // 如果保护没生效（比如原本就不包含尾帧），则 originallyContainsLastFrame 为 false，不进这里。
             // 如果原本包含尾帧，且 keepEnd 很大，涵盖了尾帧 -> end 没变 (maxFrame) -> end > lastFrameStart -> 不进这里 -> [start, maxFrame] 被加入 newRanges -> 尾帧在 newRanges 里。
             
             // 综上，逻辑似乎是对的。但为了保险，我们显式判断：
             // 只要 originallyContainsLastFrame 为真，我们就要确保 newRanges 里有 [lastFrameStart, maxFrame]
             // 我们可以简单粗暴地把 [lastFrameStart, maxFrame] 作为一个独立的区间 push 进去
             // 然后让后续的 sort 和 merge 去处理（但这里没有 merge 步骤，只是 sort）
             // 所以还是得小心。
             
             if (end <= lastFrameStart) {
                 console.log(`[Stream] 触发尾帧保护: 恢复 [${lastFrameStart}, ${maxFrame})`);
                 newRanges.push([lastFrameStart, maxFrame]);
             }
        }
    }
    
    newRanges.sort((a, b) => a[0] - b[0]);
    loadedRanges.value = newRanges;
    
    // [新增] 触发显式 GC
    // 只有在真正发生了 drop 操作时才触发 GC，避免无效调用
    if (hasDropped) {
        console.log("[Stream] 触发显式 GC (因数据裁剪)");
        callRerunForceGC();
    } else {
        // console.log("[Stream] 无数据裁剪，跳过 GC");
    }
    
    // [调试] 请求行数报告，验证清理效果
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
    // 如果正在进行紧急清理，暂停一切数据请求
    if (isCleaningUp.value) return;

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

// 临时调试：输出状态
const handleDebugDump = () => {
    console.group("=== Rerun State Dump ===");
    console.log("loadedRanges:", JSON.parse(JSON.stringify(loadedRanges.value)));
    console.log("pendingRanges:", [...pendingRanges.value]);
    console.log("currentPlaybackFrame:", currentPlaybackFrame.value);
    
    // Check if current frame is being loaded
    const isLoadingCurrent = [...pendingRanges.value].some(range => {
        const [start, end] = range.split('-').map(Number);
        return currentPlaybackFrame.value >= start && currentPlaybackFrame.value < end;
    });
    console.log("isLoadingCurrentFrame:", isLoadingCurrent);
    
    console.log("maxFrameIdx:", maxFrameIdx.value);
    console.log("isPlaying:", playing.value); // Added isPlaying state
    
    // [调试] 手动触发一次行数检查
    requestRerunRowCount();
    
    console.groupEnd();
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