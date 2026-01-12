import time
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Request
from fastapi.responses import HTMLResponse
from bson import ObjectId
from loguru import logger
from ..schemas import RateFrameConfig, RateCollectionConfig, RateRangeConfig, RateSourceConfig
from ..data_provider import DataManager
from ..logic.tagger import TaggerLogic
from fastapi.templating import Jinja2Templates
from ..service.rating_service import RatingService
from typing import Optional
from ..service import session_service

router = APIRouter()

templates = Jinja2Templates(directory="app/templates")

def _try_ui_refresh(uuid: str):
    if uuid:
        logger.info(f"评分完成，尝试触发 UI 刷新: {uuid}")
        session_service.trigger_ui_refresh(uuid)

# --- 1. 单帧打分 (JSON 接口) ---
@router.post("/rate_frame")
async def rate_frame(config: RateFrameConfig):
    client = DataManager.get_client() 
    try:
        results = client.find(config.src_database, config.src_collection, {"_id": config.frame_id})
        if not results:
            logger.warning(f"未找到 ID 为 {config.frame_id} 的帧")
            raise HTTPException(status_code=404, detail="未找到对应数据帧")
            
        frame = results[0]
        frame["tag"] = TaggerLogic.update_rating(frame.get("tag"), config.score)
        frame["relabel_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
        if config.comment:
            frame["comment"] = config.comment
            
        client.write(config.dst_database, config.dst_collection, [frame])
        logger.info(f"成功迁移并评分: {config.frame_id} -> rating:{config.score}")
        return {"status": "success", "frame_id": config.frame_id}
    except Exception as e:
        logger.error(f"rate_frame 异常: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# --- 2. 区间打分 (JSON 接口) ---
@router.post("/rate_range")
async def rate_range(config: RateRangeConfig):
    client = DataManager.get_client()
    try:
        all_frames = client.find(config.src_database, config.src_collection, {})
        if not all_frames:
            raise HTTPException(status_code=404, detail="源数据集为空")
            
        try:
            t_min = min(float(config.start_timestamp), float(config.end_timestamp))
            t_max = max(float(config.start_timestamp), float(config.end_timestamp))
        except ValueError:
            logger.error("输入的时间戳格式无法转换为数字")
            raise HTTPException(status_code=400, detail="Timestamp must be numeric strings")

        processed = []
        for frame in all_frames:
            # 兼容不同层级的 timestamp 路径
            raw_ts = frame.get("info", {}).get("timestamp") or frame.get("timestamp")
            
            if raw_ts is not None:
                try:
                    # 将当前帧的时间戳也转为 float
                    current_ts = float(raw_ts)
                    if t_min <= current_ts <= t_max:
                        frame["tag"] = TaggerLogic.update_rating(frame.get("tag"), config.score)
                        frame["relabel_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
                        if config.comment:
                            frame["comment"] = config.comment
                        processed.append(frame)
                except (ValueError, TypeError):
                    continue # 跳过无法转换的异常数据

        # 3. 批量写入目标
        if processed:
            batch_size = 100
            for i in range(0, len(processed), batch_size):
                client.write(config.dst_database, config.dst_collection, processed[i : i + batch_size])
        
        logger.success(f"区间打分完成: 匹配到 {len(processed)} 帧")
        return {"status": "success", "processed_count": len(processed), "range": [t_min, t_max]}
    except Exception as e:
        logger.error(f"rate_range 异常: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# --- 3. 全量打分 (JSON 接口) ---
@router.post("/rate_collection")
async def rate_collection(config: RateCollectionConfig, background_tasks: BackgroundTasks):
    client = DataManager.get_client()
    try:
        all_frames = client.find(config.src_database, config.src_collection, {})
        if not all_frames:
            return {"status": "error", "message": "源集合为空或不存在"}

        processed_count = 0
        batch_size = 100
        current_batch = []

        for frame in all_frames:
            frame["tag"] = TaggerLogic.update_rating(frame.get("tag"), config.score)
            frame["relabel_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
            if config.comment:
                frame["comment"] = config.comment
            current_batch.append(frame)
            processed_count += 1
            if len(current_batch) >= batch_size:
                client.write(config.dst_database, config.dst_collection, current_batch)
                current_batch = []

        if current_batch:
            client.write(config.dst_database, config.dst_collection, current_batch)
        
        return {"status": "success", "processed_count": processed_count, "rating": config.score}
    except Exception as e:
        logger.error(f"全量处理异常: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# --- 6. 序列打分 (JSON 接口) ---
@router.post("/rate_source")
async def rate_source(config: RateSourceConfig):
    """供外部或前端异步调用的 JSON 接口"""
    try:
        count = await RatingService.rate_by_source(
            db=config.src_database,
            col=config.src_collection,
            source_name=config.source_name,
            score=config.score,
            comment=config.comment
        )
        return {"status": "success", "processed_count": count, "source": config.source_name}
    except Exception as e:
        logger.error(f"rate_source 异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- 4. Rerun 单帧快速打分 (HTML 接口) ---
@router.get("/quick_rate")
async def quick_rate(
    request: Request,
    frame_id: str = Query(...), 
    score: str = Query(...),
    db: str = Query("db_prod"), 
    col: str = Query("db_dev"),
    recording_uuid: Optional[str] = None
):
    client = DataManager.get_client()
    try:
        results = client.find(db, col, {"_id": frame_id})
        if not results and ObjectId.is_valid(frame_id):
            results = client.find(db, col, {"_id": ObjectId(frame_id)})

        if not results:
            return HTMLResponse(content="<h3>❌ 找不到数据</h3>", status_code=404)

        frame = results[0]
        frame["tag"] = TaggerLogic.update_rating(frame.get("tag"), score)
        frame["relabel_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
        client.write(db, col, [frame])

        _try_ui_refresh(recording_uuid)
        
        return templates.TemplateResponse("rate_single.html", {
            "request": request,
            "frame_id": frame_id,
            "score": score,
            "db": db,
            "col": col,
            "color": "#2ecc71",
            "countdown": 15
        })
    except Exception as e:
        return HTMLResponse(content=f"<h3>错误: {str(e)}</h3>", status_code=500)

# --- 5. Rerun 全量快速打分 (HTML 接口) ---
@router.get("/quick_rate_collection")
async def quick_rate_collection(
    request: Request,            # 必须加上 request 参数
    score: str = Query(...), 
    db: str = Query(...), 
    col: str = Query(...),
    recording_uuid: Optional[str] = None
):
    try:
        # 1. 构造配置并调用逻辑
        config = RateCollectionConfig(
            src_database=db, 
            src_collection=col, 
            dst_database=db, 
            dst_collection=col, 
            score=score, 
            comment="Batch rated via Rerun UI"
        )
        result = await rate_collection(config, None)
        processed_count = result.get("processed_count", 0)

        _try_ui_refresh(recording_uuid)

        # 2. 使用 Jinja2 模板返回
        # 这里的 key 名（如 "db", "col"）要和 html 模板里的 {{ db }} 一一对应
        return templates.TemplateResponse("rate_batch.html", {
            "request": request,
            "title": "全量评级任务完成",
            "db": db,
            "col": col,
            "score": score,
            "processed_count": processed_count,
            "color": "#16a085",  # 成功的主题色
            "countdown": 10      # 倒计时秒数
        })
    except Exception as e:
        return HTMLResponse(content=f"<h3>全量打分失败: {str(e)}</h3>", status_code=500)

@router.get("/set_range_local")
async def set_range_local(
    request: Request,
    key: str = Query(...), 
    value: str = Query(...), 
    label: str = Query(...)
):
    """
    通过 Jinja2 模板执行 LocalStorage 写入操作
    """
    return templates.TemplateResponse("set_local_storage.html", {
        "request": request,
        "key": key,
        "value": value,
        "label": label
    })

@router.get("/quick_confirm_range")
async def quick_confirm_range(
    request: Request,
    db: str = Query(...),
    col: str = Query(...),
    recording_uuid: Optional[str] = None  # 接收来自 Rerun 面板的 UUID
):
    return templates.TemplateResponse("rate_range_confirm.html", {
        "request": request,
        "db": db,
        "col": col,
        "recording_uuid": recording_uuid  # 传给 HTML 模板
    })

@router.get("/quick_rate_source")
async def quick_rate_source(
    request: Request,
    db: str = Query(...),
    col: str = Query(...),
    source: str = Query(...),
    score: str = Query(...),
    recording_uuid: Optional[str] = None
):
    """供 Rerun Markdown 面板直接点击跳转的 HTML 接口"""
    try:
        # 调用 Service 处理逻辑
        processed_count = await RatingService.rate_by_source(
            db=db, 
            col=col, 
            source_name=source, 
            score=score,
            comment="Rated via Rerun Source Action"
        )

        _try_ui_refresh(recording_uuid)

        return templates.TemplateResponse("rate_batch.html", {
            "request": request,
            "title": "序列评级完成",
            "db": db,
            "col": col,
            "score": score,
            "processed_count": processed_count,
            "extra_info": f"Source: {source}",
            "color": "#9b59b6", # 专属紫色
            "countdown": 10
        })
    except Exception as e:
        logger.error(f"quick_rate_source 异常: {e}")
        return HTMLResponse(content=f"<h3>序列打分失败: {str(e)}</h3>", status_code=500)