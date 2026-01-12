# app/rerun_ui_utils.py
import json
from typing import Any, Dict, List
from urllib.parse import quote, quote_plus
from .config import BACKEND_HOST
from .logic.tagger import TaggerLogic

class RerunInterfaceHelper:
    LS_KEY_START = "dp_tagger_range_start"
    LS_KEY_END = "dp_tagger_range_end"

    @staticmethod
    def generate_frame_panel(
        doc: Dict[str, Any], 
        frame_idx: int, 
        backend_host: str = None,
        src_db: str = "",
        src_col: str = "",
        recording_uuid: str = ""
    ) -> str:
        actual_host = backend_host or BACKEND_HOST
        
        minimal_rating_interface_md = RerunInterfaceHelper._minimal_rating_interface(doc, actual_host, src_db, src_col, recording_uuid)

        parts = [
            minimal_rating_interface_md,
        ]
        return "\n\n".join(parts)

    @staticmethod
    def generate_frame_panel_pro(
        doc: Dict[str, Any], 
        frame_idx: int, 
        backend_host: str = None,
        src_db: str = "",
        src_col: str = "",
        recording_uuid: str = ""
    ) -> str:
        actual_host = backend_host or BACKEND_HOST
        ts = str(doc.get("info", {}).get("timestamp") or doc.get("timestamp", "0"))
        
        status_md = RerunInterfaceHelper._build_status_section(doc, frame_idx)
        batch_md = RerunInterfaceHelper._build_batch_section(actual_host, src_db, src_col, recording_uuid)
        source_md = RerunInterfaceHelper._build_source_section(doc, actual_host, src_db, src_col, recording_uuid)
        range_md = RerunInterfaceHelper._build_range_section(ts, actual_host, src_db, src_col, recording_uuid)
        single_md = RerunInterfaceHelper._build_single_section(doc, actual_host, src_db, src_col, recording_uuid)
        meta_md = RerunInterfaceHelper._build_meta_section(doc, src_db, src_col)

        parts = [
            status_md,
            "---",
            batch_md,
            "---",
            source_md,
            "---",
            range_md,
            "---",
            single_md,
            "---",
            meta_md
        ]
        return "\n\n".join(parts)

    @staticmethod
    def _minimal_rating_interface(doc: Dict[str, Any], host: str, db: str, col: str, uuid: str) -> str:
        source_name = doc.get("info", {}).get("source")
        current_rating = TaggerLogic.get_current_rating(doc.get("tag"))
        rating_display = f"## `{current_rating}`" if current_rating != "Unrated" else "*Unrated*"
        url = f"http://{host}/quick_rate_collection"
        links = [f"[{s}]({url}?score={s}&db={db}&col={col}&recording_uuid={uuid})" for s in sorted(list(TaggerLogic.VALID_RATINGS))]
        rating_btn = " &nbsp; | &nbsp; ".join(links)
        return (
            "## Data Quality\n\n"
            f"**Current Status:**\n{rating_display}\n\n"
            "---\n"
            "## Batch Rate\n\n"
            "> **Tip:** After clicking the rating button, the same score will be applied to all data originating from the same data source. \n\n"
            f"#### {rating_btn} \n\n"
            "---\n"
            "## Data Info\n\n"
            f"**Database:** `{db}`\n\n"
            f"**Collection:** `{col}`\n\n"
            f"**Source:** `{source_name}`\n\n"
        )

    @staticmethod
    def _build_status_section(doc: Dict[str, Any], frame_idx: int) -> str:
        current_rating = TaggerLogic.get_current_rating(doc.get("tag"))
        rating_display = f"## `{current_rating}`" if current_rating != "Unrated" else "*Unrated*"
        return f"### Quality Grading (Frame {frame_idx})\n**Current Status:**\n{rating_display}"

    @staticmethod
    def _build_batch_section(host: str, db: str, col: str, uuid: str) -> str:
        """L1: Collection Level"""
        url = f"http://{host}/quick_rate_collection"
        links = [f"[{s}]({url}?score={s}&db={db}&col={col}&recording_uuid={uuid})" for s in sorted(list(TaggerLogic.VALID_RATINGS))]
        return "### 📦 Batch Rate (All Frames)\n" + " &nbsp; | &nbsp; ".join(links)

    @staticmethod
    def _build_source_section(doc: Dict[str, Any], host: str, db: str, col: str, uuid: str) -> str:
        """L2: Source/Sequence Level"""
        source_name = doc.get("info", {}).get("source")
        if not source_name:
            return "### 🎞 Source Action (Same Sequence)\n*No source metadata found*"
        
        url = f"http://{host}/quick_rate_source"
        safe_source = quote(str(source_name))
        links = [f"[{s}]({url}?score={s}&db={db}&col={col}&source={safe_source}&recording_uuid={uuid})" for s in sorted(list(TaggerLogic.VALID_RATINGS))]
        return f"### 🎞 Sequence Rate (Same Source)\n**Source:** `{source_name}`\n\n" + " &nbsp; | &nbsp; ".join(links)

    @staticmethod
    def _build_range_section(ts: str, host: str, db: str, col: str, uuid: str) -> str:
        """L3: Range Level"""

        base_url = f"http://{host}/set_range_local"
        
        # 构造标准 URL
        from urllib.parse import quote_plus
        
        # 使用 quote_plus 处理 label 的特殊字符
        start_label = quote_plus("🚩 Range Start")
        end_label = quote_plus("🏁 Range End")

        link_start = f"{base_url}?key={RerunInterfaceHelper.LS_KEY_START}&value={ts}&label={start_label}"
        link_end = f"{base_url}?key={RerunInterfaceHelper.LS_KEY_END}&value={ts}&label={end_label}"
        
        # 执行按钮：跳转到确认页
        link_exec = f"http://{host}/quick_confirm_range?db={db}&col={col}&recording_uuid={uuid}"

        lines = [
            "### 🛠 Range Rate (Selected Interval)",
            f"[ 🚩 Set as Range Start ]({link_start})",
            f" &nbsp; | &nbsp; [ 🏁 Set as Range End ]({link_end})",
            "",
            f"[ ⚡ **Execute Range Rating (Confirm)** ]({link_exec})",
            "",
            "> **Tip:** Click Start/End to mark frames. They will be saved in your browser."
        ]
        
        return "\n".join(lines)

    @staticmethod
    def _build_single_section(doc: Dict[str, Any], host: str, db: str, col: str, uuid: str) -> str:
        """L4: Single Frame Level"""
        url = f"http://{host}/quick_rate"
        fid = quote(str(doc.get("_id", "unknown")))
        links = [f"[{s}]({url}?frame_id={fid}&score={s}&db={db}&col={col}&recording_uuid={uuid})" for s in sorted(list(TaggerLogic.VALID_RATINGS))]
        return "### 🎯 Single Rate (Current Frame)\n" + " &nbsp; | &nbsp; ".join(links)

    @staticmethod
    def _build_meta_section(doc: Dict[str, Any], db: str, col: str) -> str:
        fid_raw = str(doc.get("_id", "unknown"))
        json_str = json.dumps(doc, indent=2, ensure_ascii=False)
        return (
            f"### Frame ID\n`{fid_raw}`\n\n"
            "---\n"
            f"### Info\n**DB:** `{db}` | **Col:** `{col}`\n\n"
            "---\n"
            f"### Data Preview\n```json\n{json_str}\n```"
        )