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

    <RerunViewer 
      v-if="isInitialized" 
      ref="rerunViewerRef"
      :source="currentSource" 
    />
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { storeToRefs } from 'pinia';
import RerunViewer from './components/RerunViewer.vue';
import { useRerunStore } from './stores/rerun';
import { API_ENDPOINTS, RERUN_CONFIG } from './config';
import { ElNotification } from 'element-plus'; 

const rerunStore = useRerunStore();
const { recordingUuid, currentSource } = storeToRefs(rerunStore);

const selectedDB = ref('');
const selectedDataset = ref('');
const loading = ref(false);
const playing = ref(false);
const copied = ref(false);

// 流式加载状态管理
// 有效帧范围列表，元素为 [start, end)
// 例如: [[0, 100], [200, 300]]
const loadedRanges = ref([]); 
const isRangeLoading = ref(false); // 防止重复请求
const maxFrameIdx = ref(0); // 数据集最大帧数
const currentPlaybackFrame = ref(0); // 当前播放帧索引


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

isInitialized.value = true;

// 标记初始化完成
isInitialized.value = true;

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
    
    // 如果是直连模式 (URL带参数)，需要额外获取一次 Session 信息 (主要是 max_frame_idx)
    if (RERUN_CONFIG.STREAMING_MODE) {
        try {
            const res = await fetch(API_ENDPOINTS.GET_INFO(recordingUuid.value));
            if (res.ok) {
                const info = await res.json();
                if (info.max_frame_idx) {
                    maxFrameIdx.value = info.max_frame_idx;
                    console.log(`[Stream] 初始化获取最大帧数: ${maxFrameIdx.value}`);
                }
            }
        } catch (e) {
            console.warn("[Stream] 获取 Session 信息失败", e);
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
    } else {
        // 经典模式：一次性全量加载
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
    }); 
  });
};

// 辅助函数：获取 iframe window
const getRerunWindow = () => {
    // 通过组件 ref 获取，比 querySelector 更安全
    return rerunViewerRef.value?.getWindow();
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

// --- 缓存清理逻辑 (基于距离的最远驱逐策略) ---
const handleCacheCleanup = () => {
    let totalCached = 0;
    for (const range of loadedRanges.value) {
        totalCached += (range[1] - range[0]);
    }
    
    const MAX_CACHED = RERUN_CONFIG.STREAMING_MAX_CACHED_FRAMES || 1000;
    if (totalCached <= MAX_CACHED) return;
    
    console.log(`[Stream] 缓存超标 (${totalCached} > ${MAX_CACHED})，执行清理...`);
    
    let framesToDrop = RERUN_CONFIG.STREAMING_DROP_CHUNK_SIZE || 100;
    let newRanges = [...loadedRanges.value];
    
    // 策略：找到距离 currentPlaybackFrame 最远的区间进行清理
    // 保护规则：绝对不删除 0 帧和 maxFrameIdx (最后一帧) 所在的区间片段
    // 简化实现：我们寻找“候选删除区间”，计算它们到当前帧的距离，然后删除最远的一个
    
    while (framesToDrop > 0 && newRanges.length > 0) {
        let bestCandidateIdx = -1;
        let maxDistance = -1;
        let isHeadTruncate = false; // true: 删头部, false: 删尾部
        
        const currentFrame = currentPlaybackFrame.value;
        
        for (let i = 0; i < newRanges.length; i++) {
            const range = newRanges[i];
            const start = range[0];
            const end = range[1]; // exclusive
            
            // 保护首尾帧 (如果是包含首尾的区间，我们只允许从“非首尾”那一端进行缩减)
            // 如果区间非常小且包含了首或尾，可能直接跳过不删
            const containsStart = (start === 0);
            const containsEnd = (maxFrameIdx.value > 0 && end >= maxFrameIdx.value);
            
            // 如果一个区间既包含头又包含尾（也就是全量数据），且包含当前帧，那只能暂不处理或切分
            // 修正：即使包含当前帧，如果它足够长，我们也应该允许清理远离当前帧的部分
            const BUFFER_ZONE = 100; // 保留当前帧前后 100 帧不被清理
            
            // 检查区间是否“完全”在安全区内（即整个区间都离当前帧太近，无法清理）
            // 如果区间包含当前帧，我们需要确保至少有一端延伸到了安全区之外
            if (currentFrame >= start && currentFrame < end) {
                const distToStart = currentFrame - start;
                const distToEnd = end - currentFrame;
                if (distToStart < BUFFER_ZONE && distToEnd < BUFFER_ZONE) {
                    continue; // 整个区间都在安全区内，跳过
                }
            }
            
            // 计算距离：区间中心点到当前帧的距离
            const center = (start + end) / 2;
            const distance = Math.abs(center - currentFrame);
            
            // 检查是否受保护导致无法删除
            // 如果包含 0 帧，只能删尾部；如果包含 max 帧，只能删头部
            
            if (distance > maxDistance) {
                // 候选资格检查
                // 确定删除方向
                let canTruncateHead = true;
                let canTruncateTail = true;
                
                if (containsStart) canTruncateHead = false;
                if (containsEnd) canTruncateTail = false;
                
                // 如果包含当前帧，方向受限：只能删离当前帧远的那一端
                if (currentFrame >= start && currentFrame < end) {
                    if (currentFrame - start < BUFFER_ZONE) canTruncateHead = false; // 左边太近，不能删头
                    if (end - currentFrame < BUFFER_ZONE) canTruncateTail = false;   // 右边太近，不能删尾
                }
                
                // 最终决策
                if (canTruncateHead && canTruncateTail) {
                    // 两头都能删，删离得远的那头
                    // 简单判断：如果区间在左边，删头；在右边，删尾
                    // 如果包含当前帧，看哪边长删哪边
                    if (currentFrame >= start && currentFrame < end) {
                         if ((currentFrame - start) > (end - currentFrame)) isHeadTruncate = true; // 左边长，删左边(头)
                         else isHeadTruncate = false;
                    } else {
                        if (end <= currentFrame) isHeadTruncate = true;
                        else isHeadTruncate = false;
                    }
                } else if (canTruncateHead) {
                    isHeadTruncate = true;
                } else if (canTruncateTail) {
                    isHeadTruncate = false;
                } else {
                    continue; // 两头都锁死，跳过
                }
                
                maxDistance = distance;
                bestCandidateIdx = i;
            }
        }
        
        if (bestCandidateIdx === -1) {
            console.warn("[Stream] 无法找到可清理的帧区间（所有区间均受保护或包含当前帧）");
            break;
        }
        
        // 执行删除
        const targetRange = newRanges[bestCandidateIdx];
        const rangeLen = targetRange[1] - targetRange[0];
        
        // 实际删除量：取 需求量 和 区间长度-1 (至少留1帧以防空) 的较小值
        // 关键修改：如果是受保护区间，我们要确保至少保留受保护的那一帧
        
        let dropCount = Math.min(framesToDrop, rangeLen);
        
        // 安全区保护：不能删到 currentFrame 附近的 BUFFER_ZONE
        // 如果包含当前帧，我们需要限制 dropCount
        if (currentFrame >= targetRange[0] && currentFrame < targetRange[1]) {
            const BUFFER_ZONE = 100;
            let maxDroppable = 0;
            
            if (isHeadTruncate) {
                // 删头：只能删到 currentFrame - BUFFER_ZONE
                maxDroppable = Math.max(0, (currentFrame - BUFFER_ZONE) - targetRange[0]);
            } else {
                // 删尾：只能删到 currentFrame + BUFFER_ZONE
                maxDroppable = Math.max(0, targetRange[1] - (currentFrame + BUFFER_ZONE));
            }
            
            dropCount = Math.min(dropCount, maxDroppable);
            
            if (dropCount <= 0) {
                console.log("[Stream] 当前区间虽被选中，但受安全区保护无法删除，尝试下一个");
                // 临时从列表移除避免死循环，或者直接退出
                newRanges.splice(bestCandidateIdx, 1); 
                continue;
            }
        }
        
        // 如果删完会导致区间消失，但它又是受保护的，那我们至少留1帧
        const containsStart = (targetRange[0] === 0);
        const containsEnd = (maxFrameIdx.value > 0 && targetRange[1] >= maxFrameIdx.value);
        
        if ((containsStart || containsEnd) && dropCount >= rangeLen) {
             dropCount = rangeLen - 1; // 至少留1帧
             if (dropCount <= 0) {
                 // 如果只剩1帧了，没法再删了，放弃这个区间，找下一个
                 // 为了防止死循环，我们应该从 newRanges 里临时排除这个区间再试，或者直接 break
                 // 这里简单处理：直接 break，等待下次触发
                 console.log("[Stream] 受保护区间已压缩至最小，停止清理");
                 break;
             }
        }
        
        // 执行 Drop API
        if (isHeadTruncate) {
            // 删头部: [start, end) -> [start + drop, end)
            // 删除范围: [start, start + drop)
            const dropStart = targetRange[0];
            const dropEnd = targetRange[0] + dropCount;
            
            callRerunDrop(dropStart, dropEnd);
            targetRange[0] += dropCount;
        } else {
            // 删尾部: [start, end) -> [start, end - drop)
            // 删除范围: [end - drop, end)
            const dropStart = targetRange[1] - dropCount;
            const dropEnd = targetRange[1];
            
            callRerunDrop(dropStart, dropEnd);
            targetRange[1] -= dropCount;
        }
        
        framesToDrop -= dropCount;
        
        // 如果区间空了或非法，移除它
        if (targetRange[0] >= targetRange[1]) {
            newRanges.splice(bestCandidateIdx, 1);
        }
    }
    
    loadedRanges.value = newRanges;
};

const handleLoadRange = async (startIndex, count) => {
  if (!recordingUuid.value || isRangeLoading.value) return;
  
  // 越界检查
  if (maxFrameIdx.value > 0 && startIndex >= maxFrameIdx.value) {
      console.log(`[Stream] 请求起始点 ${startIndex} 超出最大帧数 ${maxFrameIdx.value}，停止加载`);
      return;
  }
  
  isRangeLoading.value = true;
  try {
    let endIndex = startIndex + count;
    
    // 截断 EndIndex
    if (maxFrameIdx.value > 0 && endIndex > maxFrameIdx.value) {
        endIndex = maxFrameIdx.value;
        console.log(`[Stream] 截断加载范围至末尾: ${endIndex}`);
    }
    
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
    isRangeLoading.value = false;
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

    if (isPlaying) {
      handleStreamingPlayback(currentFrameIdx);
    } else {
      handleStreamingJump(currentFrameIdx);
    }
};

// 场景 1: 正常播放中的流式加载
const handleStreamingPlayback = (currentFrameIdx) => {
    // 策略：检查当前帧是否接近已加载范围的末尾
    // 如果 (MaxLoaded - Current) < Threshold，则预加载下一批
    if (loadedRanges.value.length === 0) return;
    
    // 找到包含当前帧的区间，或者最后一个区间
    // 简单起见，我们关注最后一个区间的末尾
    const lastRange = loadedRanges.value[loadedRanges.value.length - 1];
    const maxLoadedIdx = lastRange[1]; // 区间是 [start, end)，所以 end 就是下一帧
    
    // 剩余多少帧时触发加载
    const BUFFER_THRESHOLD = RERUN_CONFIG.STREAMING_BUFFER_THRESHOLD || 50; 
    
    if (maxLoadedIdx - currentFrameIdx < BUFFER_THRESHOLD) {
        // 触发加载，从 maxLoadedIdx 开始
        handleLoadRange(maxLoadedIdx, RERUN_CONFIG.STREAMING_BATCH_SIZE);
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
        console.log(`[Stream] 检测到跳转至未加载区域: ${currentFrameIdx}`);
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