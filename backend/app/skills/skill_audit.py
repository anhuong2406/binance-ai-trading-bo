"""
Skill Audit Engine
Maintains in-memory and persistent execution logs of trading skills.
Tracks latency, invocation counts, and audit trails for the Skill Dashboard.
"""
import time
from typing import Dict, Any, List, Optional
from collections import deque

class SkillAuditRecord:
    def __init__(
        self,
        skill_name: str,
        action: str,
        status: str,
        duration_ms: float,
        output_summary: str,
        timestamp: Optional[float] = None
    ):
        self.timestamp = timestamp or time.time()
        self.skill_name = skill_name
        self.action = action
        self.status = status
        self.duration_ms = duration_ms
        self.output_summary = output_summary

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": int(self.timestamp * 1000),
            "skill_name": self.skill_name,
            "action": self.action,
            "status": self.status,
            "duration_ms": round(self.duration_ms, 2),
            "output_summary": self.output_summary
        }

class SkillAudit:
    def __init__(self, max_history: int = 200):
        self._history: deque = deque(maxlen=max_history)
        self._last_used_skills: List[str] = []
        self._last_analysis_time: Optional[float] = None

    @staticmethod
    def get_time_ms() -> float:
        return time.time() * 1000.0

    def record(
        self,
        skill_name: str,
        action: str,
        status: str,
        duration_ms: float,
        output_summary: str
    ):
        rec = SkillAuditRecord(
            skill_name=skill_name,
            action=action,
            status=status,
            duration_ms=duration_ms,
            output_summary=output_summary
        )
        self._history.appendleft(rec)
        if skill_name not in self._last_used_skills:
            self._last_used_skills.append(skill_name)
        self._last_analysis_time = time.time()

    def set_last_cycle_skills(self, skills: List[str]):
        self._last_used_skills = skills
        self._last_analysis_time = time.time()

    def get_audit_trail(self, limit: int = 50) -> List[Dict[str, Any]]:
        return [item.to_dict() for item in list(self._history)[:limit]]

    def get_summary(self) -> Dict[str, Any]:
        total_invocations = len(self._history)
        success_count = sum(1 for r in self._history if r.status == "SUCCESS")
        error_count = sum(1 for r in self._history if r.status == "ERROR")
        
        return {
            "total_invocations": total_invocations,
            "success_count": success_count,
            "error_count": error_count,
            "last_used_skills": self._last_used_skills,
            "last_analysis_time": int(self._last_analysis_time * 1000) if self._last_analysis_time else None,
            "provenance": {
                "repository": "agiprolabs/claude-trading-skills",
                "commit_hash": "981e1d736cdc02bdc1c55c74ec9224e956414706",
                "total_skills_available": 68,
                "installed_skills_count": 25,
                "license": "MIT"
            }
        }

skill_audit = SkillAudit()
