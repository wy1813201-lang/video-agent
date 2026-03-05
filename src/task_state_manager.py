#!/usr/bin/env python3
"""
任务状态管理模块
功能：保存/恢复任务状态，实现断点续传

用法：
    task_state = TaskStateManager(project_id)
    task_state.save_stage_status("script", "completed", data={...})
    task_state.get_stage_status("script")
    task_state.can_resume()  # 是否可以续传
"""

import json
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class TaskStage(str, Enum):
    """任务阶段"""
    SCRIPT = "script"           # 剧本
    CHARACTER = "character"     # 角色
    STORYBOARD = "storyboard"   # 分镜
    KEYFRAME = "keyframe"      # 关键帧
    VIDEO = "video"            # 视频
    VOICE = "voice"           # 配音
    SUBTITLE = "subtitle"      # 字幕
    COMPOSE = "compose"        # 合成
    FINAL = "final"            # 成片


class StageStatus(str, Enum):
    """阶段状态"""
    PENDING = "pending"        # 待处理
    IN_PROGRESS = "in_progress"  # 进行中
    COMPLETED = "completed"     # 已完成
    FAILED = "failed"          # 失败
    SKIPPED = "skipped"        # 跳过


@dataclass
class StageRecord:
    """阶段记录"""
    stage: str
    status: str
    started_at: str = ""
    completed_at: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    retry_count: int = 0


@dataclass
class TaskState:
    """任务状态"""
    project_id: str
    topic: str
    total_episodes: int
    current_episode: int = 1
    current_stage: str = TaskStage.SCRIPT.value
    
    # 各阶段状态
    stages: Dict[str, StageRecord] = field(default_factory=dict)
    
    # 时间信息
    created_at: str = ""
    updated_at: str = ""
    last_run_at: str = ""
    
    # 统计
    total_duration: float = 0
    completed_count: int = 0
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
        self.last_run_at = datetime.now().isoformat()
        
        # 初始化各阶段
        for stage in TaskStage:
            if stage.value not in self.stages:
                self.stages[stage.value] = StageRecord(
                    stage=stage.value,
                    status=StageStatus.PENDING.value
                )


class TaskStateManager:
    """任务状态管理器"""
    
    def __init__(self, project_id: str, output_dir: str = "output"):
        self.project_id = project_id
        self.output_dir = Path(output_dir)
        self.state_dir = self.output_dir / "states"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.state_dir / f"task_{project_id}.json"
        self.state: Optional[TaskState] = None
        self._load()
    
    def _load(self):
        """加载状态"""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # 反序列化
                stages = {}
                for k, v in data.get("stages", {}).items():
                    stages[k] = StageRecord(**v)
                
                data["stages"] = stages
                self.state = TaskState(**data)
            except Exception as e:
                print(f"加载任务状态失败: {e}")
                self.state = None
    
    def _save(self):
        """保存状态"""
        if not self.state:
            return
        
        self.state.updated_at = datetime.now().isoformat()
        
        # 序列化
        data = {
            "project_id": self.state.project_id,
            "topic": self.state.topic,
            "total_episodes": self.state.total_episodes,
            "current_episode": self.state.current_episode,
            "current_stage": self.state.current_stage,
            "stages": {k: asdict(v) for k, v in self.state.stages.items()},
            "created_at": self.state.created_at,
            "updated_at": self.state.updated_at,
            "last_run_at": self.state.last_run_at,
            "total_duration": self.state.total_duration,
            "completed_count": self.state.completed_count,
        }
        
        # 原子写入
        tmp_file = str(self.state_file) + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_file, self.state_file)
    
    def init(self, topic: str, total_episodes: int):
        """初始化新任务"""
        self.state = TaskState(
            project_id=self.project_id,
            topic=topic,
            total_episodes=total_episodes
        )
        self._save()
    
    def start_episode(self, episode: int):
        """开始新一集"""
        if not self.state:
            return
        
        self.state.current_episode = episode
        self.state.last_run_at = datetime.now().isoformat()
        self._save()
    
    def start_stage(self, stage: str):
        """开始一个阶段"""
        if not self.state:
            return
        
        self.state.current_stage = stage
        
        if stage not in self.state.stages:
            self.state.stages[stage] = StageRecord(
                stage=stage,
                status=StageStatus.IN_PROGRESS.value,
                started_at=datetime.now().isoformat()
            )
        else:
            self.state.stages[stage].status = StageStatus.IN_PROGRESS.value
            self.state.stages[stage].started_at = datetime.now().isoformat()
        
        self._save()
    
    def complete_stage(self, stage: str, data: Dict[str, Any] = None, episode: int = None):
        """完成一个阶段"""
        if not self.state:
            return
        
        if stage in self.state.stages:
            self.state.stages[stage].status = StageStatus.COMPLETED.value
            self.state.stages[stage].completed_at = datetime.now().isoformat()
            if data:
                self.state.stages[stage].data.update(data)
            
            # 更新统计
            self.state.completed_count += 1
        
        # 更新当前阶段为下一个
        self._advance_stage(episode)
        self._save()
    
    def fail_stage(self, stage: str, error: str):
        """标记阶段失败"""
        if not self.state:
            return
        
        if stage in self.state.stages:
            self.state.stages[stage].status = StageStatus.FAILED.value
            self.state.stages[stage].error = error
            self.state.stages[stage].retry_count += 1
        
        self._save()
    
    def skip_stage(self, stage: str):
        """跳过阶段"""
        if not self.state:
            return
        
        if stage in self.state.stages:
            self.state.stages[stage].status = StageStatus.SKIPPED.value
            self.state.stages[stage].completed_at = datetime.now().isoformat()
        
        self._advance_stage()
        self._save()
    
    def _advance_stage(self, episode: int = None):
        """推进到下一阶段"""
        if not self.state:
            return
        
        stages_order = [s.value for s in TaskStage]
        
        try:
            current_idx = stages_order.index(self.state.current_stage)
        except ValueError:
            current_idx = 0
        
        # 尝试下一个阶段
        if current_idx + 1 < len(stages_order):
            self.state.current_stage = stages_order[current_idx + 1]
    
    def get_stage_status(self, stage: str) -> Optional[StageRecord]:
        """获取阶段状态"""
        if not self.state:
            return None
        return self.state.stages.get(stage)
    
    def is_stage_completed(self, stage: str) -> bool:
        """检查阶段是否完成"""
        record = self.get_stage_status(stage)
        return record and record.status == StageStatus.COMPLETED.value
    
    def can_resume(self) -> bool:
        """是否可以续传"""
        if not self.state:
            return False
        
        # 有未完成的阶段
        for stage in TaskStage:
            record = self.state.stages.get(stage.value)
            if record and record.status in [StageStatus.PENDING.value, StageStatus.IN_PROGRESS.value]:
                return True
        
        return False
    
    def get_resume_point(self) -> Dict[str, Any]:
        """获取续传点"""
        if not self.state:
            return {}
        
        # 找到第一个未完成的阶段
        for stage in TaskStage:
            record = self.state.stages.get(stage.value)
            if not record or record.status != StageStatus.COMPLETED.value:
                return {
                    "episode": self.state.current_episode,
                    "stage": stage.value,
                    "status": record.status if record else StageStatus.PENDING.value,
                    "data": record.data if record else {}
                }
        
        # 全部完成
        return {"episode": self.state.current_episode + 1, "stage": TaskStage.SCRIPT.value}
    
    def get_progress(self) -> Dict[str, Any]:
        """获取进度"""
        if not self.state:
            return {}
        
        total = len(TaskStage)
        completed = sum(1 for r in self.state.stages.values() if r.status == StageStatus.COMPLETED.value)
        
        return {
            "project_id": self.project_id,
            "topic": self.state.topic,
            "episode": self.state.current_episode,
            "total_episodes": self.state.total_episodes,
            "current_stage": self.state.current_stage,
            "progress": f"{completed}/{total}",
            "percentage": int(completed / total * 100) if total > 0 else 0,
            "last_run": self.state.last_run_at,
        }
    
    def reset(self):
        """重置任务"""
        if self.state_file.exists():
            # 备份
            backup = str(self.state_file) + f".backup_{int(time.time())}"
            os.rename(self.state_file, backup)
        self.state = None
    
    def export_summary(self) -> str:
        """导出摘要"""
        if not self.state:
            return "No task state"
        
        lines = [
            f"# 任务状态: {self.state.topic}",
            f"",
            f"- 项目ID: {self.state.project_id}",
            f"- 集数: {self.state.current_episode}/{self.state.total_episodes}",
            f"- 当前阶段: {self.state.current_stage}",
            f"- 进度: {self.state.completed_count}/{len(TaskStage)}",
            f"- 最后运行: {self.state.last_run_at}",
            f"",
            f"## 各阶段状态",
        ]
        
        for stage in TaskStage:
            record = self.state.stages.get(stage.value)
            if record:
                status_icon = {
                    StageStatus.COMPLETED.value: "✅",
                    StageStatus.IN_PROGRESS.value: "🔄",
                    StageStatus.FAILED.value: "❌",
                    StageStatus.PENDING.value: "⏳",
                    StageStatus.SKIPPED.value: "⏭",
                }.get(record.status, "❓")
                lines.append(f"- {status_icon} {stage.value}: {record.status}")
        
        return "\n".join(lines)


# 便捷函数
def create_task_state(project_id: str, topic: str, episodes: int) -> TaskStateManager:
    """创建新任务状态"""
    manager = TaskStateManager(project_id)
    manager.init(topic, episodes)
    return manager


def load_task_state(project_id: str) -> Optional[TaskStateManager]:
    """加载任务状态"""
    manager = TaskStateManager(project_id)
    if manager.state:
        return manager
    return None


if __name__ == "__main__":
    # 测试
    import sys
    
    if len(sys.argv) > 1:
        project_id = sys.argv[1]
        
        # 测试创建
        mgr = create_task_state(project_id, "测试短剧", 3)
        print(f"Created: {mgr.state_file}")
        
        # 测试更新
        mgr.start_stage(TaskStage.SCRIPT.value)
        mgr.complete_stage(TaskStage.SCRIPT.value, data={"script": "剧本内容"})
        
        # 测试获取进度
        print(mgr.get_progress())
        
        # 测试能否续传
        print(f"Can resume: {mgr.can_resume()}")
        
        # 测试摘要
        print(mgr.export_summary())
    else:
        print("Usage: python task_state_manager.py <project_id>")
