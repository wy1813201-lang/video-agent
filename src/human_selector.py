#!/usr/bin/env python3
"""
Human Selector - 人工选择界面

用于从多个实验版本中选择最佳版本
"""

import os
from typing import List, Dict, Any, Optional


class HumanSelector:
    """人工选择器（CLI版本）"""

    @staticmethod
    def select_best_script(versions: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        让用户从多个剧本版本中选择最佳版本

        Args:
            versions: 版本列表，每个版本包含 version_id, params, content

        Returns:
            选中的版本字典，包含 version_id, reason
        """
        if not versions:
            return None

        print("\n" + "=" * 60)
        print("🧪 实验版本选择")
        print("=" * 60)

        # 显示所有版本
        for idx, version in enumerate(versions, 1):
            print(f"\n【版本 {idx}】{version['version_id']}")
            print(f"参数: {version['params'].get('name', 'unknown')}")
            print(f"特点:")
            params = version['params']
            if params.get('conflict_timing'):
                print(f"  - 冲突时间: {params['conflict_timing']}")
            if params.get('reversal_count'):
                print(f"  - 反转次数: {params['reversal_count']}")
            if params.get('emotion_intensity'):
                print(f"  - 情绪强度: {params['emotion_intensity']}")
            if params.get('hook_style'):
                print(f"  - Hook风格: {params['hook_style']}")

            # 显示剧本预览（前200字）
            content = str(version.get('content', ''))
            preview = content[:200] + "..." if len(content) > 200 else content
            print(f"\n预览:\n{preview}\n")

        # 用户选择
        while True:
            try:
                choice = input(f"\n请选择最佳版本 (1-{len(versions)}) 或输入 0 跳过: ")
                choice_num = int(choice)

                if choice_num == 0:
                    print("跳过选择")
                    return None

                if 1 <= choice_num <= len(versions):
                    selected = versions[choice_num - 1]
                    reason = input("请说明选择理由: ").strip()

                    if not reason:
                        reason = "未提供理由"

                    return {
                        "version_id": selected['version_id'],
                        "reason": reason,
                        "content": selected['content']
                    }
                else:
                    print(f"❌ 请输入 0-{len(versions)} 之间的数字")

            except ValueError:
                print("❌ 请输入有效的数字")
            except KeyboardInterrupt:
                print("\n\n取消选择")
                return None

    @staticmethod
    def select_best_storyboard(versions: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        让用户从多个分镜版本中选择最佳版本

        Args:
            versions: 版本列表

        Returns:
            选中的版本字典
        """
        if not versions:
            return None

        print("\n" + "=" * 60)
        print("🧪 分镜版本选择")
        print("=" * 60)

        # 显示所有版本
        for idx, version in enumerate(versions, 1):
            print(f"\n【版本 {idx}】{version['version_id']}")
            print(f"参数: {version['params'].get('name', 'unknown')}")
            print(f"特点:")
            params = version['params']
            if params.get('shot_count_multiplier'):
                print(f"  - 镜头数量调整: {params['shot_count_multiplier']}")
            if params.get('closeup_ratio'):
                print(f"  - 特写比例: {params['closeup_ratio']}")
            if params.get('camera_motion'):
                print(f"  - 运镜风格: {params['camera_motion']}")
            if params.get('cut_speed'):
                print(f"  - 剪辑速度: {params['cut_speed']}")

            # 显示镜头统计
            content = version.get('content', {})
            shots = content.get('film_storyboard', [])
            print(f"\n镜头数量: {len(shots)}")

        # 用户选择
        while True:
            try:
                choice = input(f"\n请选择最佳版本 (1-{len(versions)}) 或输入 0 跳过: ")
                choice_num = int(choice)

                if choice_num == 0:
                    print("跳过选择")
                    return None

                if 1 <= choice_num <= len(versions):
                    selected = versions[choice_num - 1]
                    reason = input("请说明选择理由: ").strip()

                    if not reason:
                        reason = "未提供理由"

                    return {
                        "version_id": selected['version_id'],
                        "reason": reason,
                        "content": selected['content']
                    }
                else:
                    print(f"❌ 请输入 0-{len(versions)} 之间的数字")

            except ValueError:
                print("❌ 请输入有效的数字")
            except KeyboardInterrupt:
                print("\n\n取消选择")
                return None

    @staticmethod
    def confirm_action(message: str, default: bool = True) -> bool:
        """
        确认操作

        Args:
            message: 确认消息
            default: 默认值

        Returns:
            True/False
        """
        suffix = " [Y/n]: " if default else " [y/N]: "
        try:
            response = input(message + suffix).strip().lower()

            if not response:
                return default

            return response in ['y', 'yes', '是']

        except KeyboardInterrupt:
            print("\n")
            return False
