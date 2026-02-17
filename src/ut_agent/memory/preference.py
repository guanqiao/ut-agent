"""偏好学习器."""

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class PreferenceSample:
    """偏好样本."""
    action: str
    outcome: str
    feedback: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class PreferenceLearner:
    """偏好学习器 - 从用户行为学习偏好."""
    
    def __init__(self, memory_manager: Optional[Any] = None) -> None:
        self._memory = memory_manager
        self._samples: Dict[str, List[PreferenceSample]] = defaultdict(list)
        self._learned_preferences: Dict[str, Any] = {}
        self._preference_weights: Dict[str, float] = defaultdict(float)
    
    def collect_preference(
        self,
        action: str,
        outcome: str,
        feedback: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        sample = PreferenceSample(
            action=action,
            outcome=outcome,
            feedback=feedback,
            metadata=metadata or {},
        )
        
        self._samples[action].append(sample)
        
        if len(self._samples[action]) > 100:
            self._samples[action] = self._samples[action][-100:]
        
        self._update_preference(action, outcome, feedback)
    
    def _update_preference(
        self,
        action: str,
        outcome: str,
        feedback: str,
    ) -> None:
        feedback_score = self._parse_feedback(feedback)
        
        current_weight = self._preference_weights.get(action, 0.5)
        learning_rate = 0.1
        
        if outcome == "success":
            new_weight = current_weight + learning_rate * feedback_score
        else:
            new_weight = current_weight - learning_rate * abs(feedback_score)
        
        self._preference_weights[action] = max(0.0, min(1.0, new_weight))
        
        if action not in self._learned_preferences:
            self._learned_preferences[action] = {
                "preferred": feedback_score > 0,
                "confidence": abs(feedback_score),
                "sample_count": 1,
            }
        else:
            pref = self._learned_preferences[action]
            pref["sample_count"] += 1
            pref["confidence"] = min(1.0, pref["confidence"] + 0.05)
    
    def _parse_feedback(self, feedback: str) -> float:
        feedback_lower = feedback.lower()
        
        positive_words = ["good", "great", "excellent", "perfect", "like", "yes", "accept", "approve"]
        negative_words = ["bad", "poor", "wrong", "incorrect", "no", "reject", "dislike"]
        
        score = 0.0
        
        for word in positive_words:
            if word in feedback_lower:
                score += 0.5
        
        for word in negative_words:
            if word in feedback_lower:
                score -= 0.5
        
        if feedback.isdigit():
            rating = int(feedback)
            if 1 <= rating <= 5:
                score = (rating - 3) / 2
        
        return max(-1.0, min(1.0, score))
    
    def analyze_preferences(self) -> Dict[str, Any]:
        analysis = {
            "total_actions": len(self._samples),
            "total_samples": sum(len(s) for s in self._samples.values()),
            "preferences": {},
            "recommendations": [],
        }
        
        for action, samples in self._samples.items():
            if not samples:
                continue
            
            success_count = sum(1 for s in samples if s.outcome == "success")
            success_rate = success_count / len(samples)
            
            avg_feedback = sum(
                self._parse_feedback(s.feedback)
                for s in samples
            ) / len(samples)
            
            analysis["preferences"][action] = {
                "sample_count": len(samples),
                "success_rate": success_rate,
                "avg_feedback": avg_feedback,
                "weight": self._preference_weights.get(action, 0.5),
                "preferred": self._learned_preferences.get(action, {}).get("preferred", False),
            }
        
        sorted_actions = sorted(
            analysis["preferences"].items(),
            key=lambda x: x[1]["weight"],
            reverse=True,
        )
        
        for action, data in sorted_actions[:5]:
            if data["weight"] > 0.6:
                analysis["recommendations"].append({
                    "action": action,
                    "recommendation": f"优先使用 {action}",
                    "confidence": data["weight"],
                })
        
        return analysis
    
    def apply_preferences(
        self,
        context: Dict[str, Any],
        actions: List[str],
    ) -> Dict[str, Any]:
        scored_actions = []
        
        for action in actions:
            weight = self._preference_weights.get(action, 0.5)
            pref = self._learned_preferences.get(action, {})
            
            score = weight
            if pref.get("preferred"):
                score += 0.2
            
            scored_actions.append({
                "action": action,
                "score": score,
                "preferred": pref.get("preferred", False),
            })
        
        scored_actions.sort(key=lambda x: x["score"], reverse=True)
        
        result = context.copy()
        result["_preference_scores"] = scored_actions
        
        if scored_actions:
            result["_recommended_action"] = scored_actions[0]["action"]
        
        return result
    
    def get_preference(self, action: str) -> Optional[Dict[str, Any]]:
        return self._learned_preferences.get(action)
    
    def get_weight(self, action: str) -> float:
        return self._preference_weights.get(action, 0.5)
    
    def get_samples(self, action: str, limit: int = 10) -> List[Dict[str, Any]]:
        samples = self._samples.get(action, [])[-limit:]
        return [
            {
                "action": s.action,
                "outcome": s.outcome,
                "feedback": s.feedback,
                "timestamp": s.timestamp.isoformat(),
            }
            for s in samples
        ]
    
    def clear_samples(self, action: Optional[str] = None) -> None:
        if action:
            self._samples[action] = []
        else:
            self._samples.clear()
    
    def export_preferences(self) -> Dict[str, Any]:
        return {
            "learned_preferences": self._learned_preferences,
            "preference_weights": dict(self._preference_weights),
            "sample_counts": {
                action: len(samples)
                for action, samples in self._samples.items()
            },
        }
    
    def import_preferences(self, data: Dict[str, Any]) -> None:
        if "learned_preferences" in data:
            self._learned_preferences.update(data["learned_preferences"])
        
        if "preference_weights" in data:
            self._preference_weights.update(data["preference_weights"])
