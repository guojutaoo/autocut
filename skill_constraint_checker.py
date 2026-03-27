#!/usr/bin/env python3
"""
Skill约束检查器
用于验证生成的剧本是否100%遵守video-script-expert.md中的硬性约束
"""

import json
import re
import sys
from typing import Dict, List, Tuple

class SkillConstraintChecker:
    """Skill约束检查器"""
    
    def __init__(self, script_path: str, transcript_path: str):
        self.script_path = script_path
        self.transcript_path = transcript_path
        self.total_duration = 0
        self.violations = []
        
    def load_data(self) -> bool:
        """加载剧本和字幕数据"""
        try:
            # 加载剧本
            with open(self.script_path, 'r', encoding='utf-8') as f:
                self.script_data = json.load(f)
            
            # 加载字幕并计算总时长
            with open(self.transcript_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if lines:
                    # 提取最后一行的时间戳
                    last_line = lines[-1].strip()
                    match = re.search(r'\[([\d:,\.]+) - ([\d:,\.]+)\]', last_line)
                    if match:
                        end_time_str = match.group(2)
                        # 将时间字符串转换为秒数
                        self.total_duration = self._time_str_to_seconds(end_time_str)
                        print(f"✅ 视频总时长: {self.total_duration:.1f}秒 ({self.total_duration/60:.1f}分钟)")
                        return True
            
            print("❌ 无法计算视频总时长")
            return False
            
        except Exception as e:
            print(f"❌ 数据加载失败: {e}")
            return False
    
    def _time_str_to_seconds(self, time_str: str) -> float:
        """将时间字符串转换为秒数"""
        # 格式: 00:44:30,820
        parts = time_str.split(':')
        if len(parts) == 3:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds_millis = parts[2].split(',')
            seconds = int(seconds_millis[0])
            millis = int(seconds_millis[1]) if len(seconds_millis) > 1 else 0
            return hours * 3600 + minutes * 60 + seconds + millis / 1000
        return 0
    
    def check_global_story_vision(self) -> bool:
        """检查全局故事视野约束"""
        print("\n🔍 检查全局故事视野约束...")
        
        if not self.script_data.get('segments'):
            self.violations.append("剧本中没有segments字段")
            return False
        
        segments = self.script_data['segments']
        
        # 1. 检查结尾段位置 (必须在进度条80%-100%处)
        last_segment = segments[-1]
        last_segment_end = last_segment['end']
        
        progress_percentage = (last_segment_end / self.total_duration) * 100
        
        print(f"  最后一个片段结束时间: {last_segment_end:.1f}秒")
        print(f"  进度条位置: {progress_percentage:.1f}%")
        
        if progress_percentage < 80:
            self.violations.append(
                f"结尾段位置违规: 进度条{progress_percentage:.1f}% < 80% (应在80%-100%处)"
            )
        
        # 2. 检查时间轴覆盖 (必须贯穿全片)
        time_coverage = self._calculate_time_coverage(segments)
        print(f"  时间轴覆盖度: {time_coverage:.1f}%")
        
        if time_coverage < 80:
            self.violations.append(
                f"时间轴覆盖不足: {time_coverage:.1f}% < 80% (应贯穿全片)"
            )
        
        # 3. 检查剧情跳跃 (必须大跨度跳跃)
        jump_analysis = self._analyze_jumps(segments)
        print(f"  剧情跳跃分析: {jump_analysis}")
        
        if jump_analysis["max_jump"] < self.total_duration * 0.2:  # 最大跳跃小于总时长20%
            self.violations.append(
                f"剧情跳跃不足: 最大跳跃{jump_analysis['max_jump']:.1f}秒 < 总时长20%"
            )
        
        return len(self.violations) == 0
    
    def _calculate_time_coverage(self, segments: List[Dict]) -> float:
        """计算时间轴覆盖度"""
        if not segments:
            return 0
        
        # 计算所有片段覆盖的时间范围
        covered_ranges = []
        for seg in segments:
            covered_ranges.append((seg['start'], seg['end']))
        
        # 合并重叠的时间范围
        merged_ranges = self._merge_ranges(covered_ranges)
        
        # 计算总覆盖时长
        total_covered = sum(end - start for start, end in merged_ranges)
        
        return (total_covered / self.total_duration) * 100
    
    def _merge_ranges(self, ranges: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """合并重叠的时间范围"""
        if not ranges:
            return []
        
        ranges.sort(key=lambda x: x[0])
        merged = [ranges[0]]
        
        for current in ranges[1:]:
            last = merged[-1]
            if current[0] <= last[1]:
                merged[-1] = (last[0], max(last[1], current[1]))
            else:
                merged.append(current)
        
        return merged
    
    def _analyze_jumps(self, segments: List[Dict]) -> Dict:
        """分析剧情跳跃情况"""
        if len(segments) < 2:
            return {"max_jump": 0, "avg_jump": 0}
        
        jumps = []
        for i in range(1, len(segments)):
            jump = segments[i]['start'] - segments[i-1]['end']
            jumps.append(jump)
        
        return {
            "max_jump": max(jumps) if jumps else 0,
            "avg_jump": sum(jumps) / len(jumps) if jumps else 0
        }
    
    def check_narration_length(self) -> bool:
        """检查解说词长度约束"""
        print("\n🔍 检查解说词长度约束...")
        
        segments = self.script_data.get('segments', [])
        
        for i, seg in enumerate(segments):
            text = seg.get('narration_text', '')
            char_count = len(text)
            
            # Skill要求: 建议50-100字，拒绝流水账
            if char_count < 30:
                self.violations.append(
                    f"片段{i}解说词过短: {char_count}字 < 30字 (建议50-100字)"
                )
            elif char_count > 200:
                self.violations.append(
                    f"片段{i}解说词过长: {char_count}字 > 200字 (建议50-100字)"
                )
        
        return len(self.violations) == 0
    
    def check_segment_duration(self) -> bool:
        """检查片段时长约束"""
        print("\n🔍 检查片段时长约束...")
        
        segments = self.script_data.get('segments', [])
        
        for i, seg in enumerate(segments):
            duration = seg['end'] - seg['start']
            
            # Skill要求: 建议10-20秒，严禁数分钟的单段
            if duration > 60:  # 超过1分钟
                self.violations.append(
                    f"片段{i}时长过长: {duration:.1f}秒 > 60秒 (建议10-20秒)"
                )
            elif duration < 5:  # 过短
                self.violations.append(
                    f"片段{i}时长过短: {duration:.1f}秒 < 5秒 (建议10-20秒)"
                )
        
        return len(self.violations) == 0
    
    def run_all_checks(self) -> bool:
        """运行所有检查"""
        print("🚀 开始Skill约束检查...")
        print("=" * 50)
        
        if not self.load_data():
            return False
        
        # 运行各项检查
        checks = [
            ("全局故事视野", self.check_global_story_vision),
            ("解说词长度", self.check_narration_length),
            ("片段时长", self.check_segment_duration)
        ]
        
        all_passed = True
        for check_name, check_func in checks:
            if not check_func():
                all_passed = False
        
        # 输出检查结果
        print("\n" + "=" * 50)
        if all_passed:
            print("✅ 所有Skill约束检查通过！")
        else:
            print("❌ Skill约束检查失败！")
            print("\n违规项:")
            for i, violation in enumerate(self.violations, 1):
                print(f"  {i}. {violation}")
        
        return all_passed

def main():
    """主函数"""
    if len(sys.argv) != 3:
        print("用法: python skill_constraint_checker.py <剧本文件> <字幕文件>")
        sys.exit(1)
    
    script_path = sys.argv[1]
    transcript_path = sys.argv[2]
    
    checker = SkillConstraintChecker(script_path, transcript_path)
    success = checker.run_all_checks()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()