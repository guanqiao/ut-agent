"""偏好学习器测试"""

from datetime import datetime
from unittest import mock

import pytest

from ut_agent.memory.preference import PreferenceSample, PreferenceLearner


class TestPreferenceSample:
    """测试偏好样本"""
    
    def test_creation(self):
        """测试创建"""
        sample = PreferenceSample(
            action="use_template",
            outcome="success",
            feedback="good",
        )
        
        assert sample.action == "use_template"
        assert sample.outcome == "success"
        assert sample.feedback == "good"
        assert isinstance(sample.timestamp, datetime)
        assert sample.metadata == {}
    
    def test_with_metadata(self):
        """测试带元数据创建"""
        metadata = {"template": "basic", "language": "java"}
        sample = PreferenceSample(
            action="use_template",
            outcome="success",
            feedback="excellent",
            metadata=metadata,
        )
        
        assert sample.metadata == metadata


class TestPreferenceLearner:
    """测试偏好学习器"""
    
    def test_initialization(self):
        """测试初始化"""
        learner = PreferenceLearner()
        assert learner._memory is None
        assert learner._samples == {}
        assert learner._learned_preferences == {}
    
    def test_collect_preference(self):
        """测试收集偏好"""
        learner = PreferenceLearner()
        
        learner.collect_preference(
            action="use_template",
            outcome="success",
            feedback="good",
        )
        
        assert "use_template" in learner._samples
        assert len(learner._samples["use_template"]) == 1
    
    def test_max_samples_limit(self):
        """测试最大样本限制"""
        learner = PreferenceLearner()
        
        # 添加超过 100 个样本
        for i in range(110):
            learner.collect_preference(
                action="use_template",
                outcome="success",
                feedback="good",
            )
        
        # 应该只保留最后 100 个
        assert len(learner._samples["use_template"]) == 100
    
    def test_parse_feedback_positive(self):
        """测试解析正面反馈"""
        learner = PreferenceLearner()
        
        assert learner._parse_feedback("good") > 0
        assert learner._parse_feedback("excellent") > 0
        assert learner._parse_feedback("perfect") > 0
        assert learner._parse_feedback("I like it") > 0
    
    def test_parse_feedback_negative(self):
        """测试解析负面反馈"""
        learner = PreferenceLearner()
        
        assert learner._parse_feedback("bad") < 0
        assert learner._parse_feedback("poor") < 0
        assert learner._parse_feedback("wrong") < 0
        assert learner._parse_feedback("no") < 0
        assert learner._parse_feedback("reject") < 0
    
    def test_parse_feedback_numeric(self):
        """测试解析数字反馈"""
        learner = PreferenceLearner()
        
        # 5 星评分
        assert learner._parse_feedback("5") == 1.0
        assert learner._parse_feedback("4") == 0.5
        assert learner._parse_feedback("3") == 0.0
        assert learner._parse_feedback("2") == -0.5
        assert learner._parse_feedback("1") == -1.0
    
    def test_update_preference_success(self):
        """测试成功时更新偏好"""
        learner = PreferenceLearner()
        
        learner.collect_preference(
            action="use_template",
            outcome="success",
            feedback="good",
        )
        
        weight = learner.get_weight("use_template")
        assert weight > 0.5  # 应该增加权重
    
    def test_update_preference_failure(self):
        """测试失败时更新偏好"""
        learner = PreferenceLearner()
        
        learner.collect_preference(
            action="use_template",
            outcome="failure",
            feedback="bad",
        )
        
        weight = learner.get_weight("use_template")
        assert weight < 0.5  # 应该减少权重
    
    def test_analyze_preferences(self):
        """测试分析偏好"""
        learner = PreferenceLearner()
        
        # 添加一些样本
        learner.collect_preference("action1", "success", "good")
        learner.collect_preference("action1", "success", "excellent")
        learner.collect_preference("action2", "failure", "bad")
        
        analysis = learner.analyze_preferences()
        
        assert analysis["total_actions"] == 2
        assert analysis["total_samples"] == 3
        assert "action1" in analysis["preferences"]
        assert "action2" in analysis["preferences"]
    
    def test_analyze_preferences_recommendations(self):
        """测试分析偏好推荐"""
        learner = PreferenceLearner()
        
        # 添加多个成功样本以提高权重
        for _ in range(10):
            learner.collect_preference("good_action", "success", "excellent")
        
        analysis = learner.analyze_preferences()
        
        # 应该有推荐
        assert len(analysis["recommendations"]) > 0
    
    def test_apply_preferences(self):
        """测试应用偏好"""
        learner = PreferenceLearner()
        
        # 添加一些偏好
        learner.collect_preference("action1", "success", "good")
        learner.collect_preference("action2", "failure", "bad")
        
        context = {"test": "value"}
        actions = ["action1", "action2", "action3"]
        
        result = learner.apply_preferences(context, actions)
        
        assert "_preference_scores" in result
        assert "_recommended_action" in result
        assert len(result["_preference_scores"]) == 3
    
    def test_get_preference(self):
        """测试获取偏好"""
        learner = PreferenceLearner()
        
        learner.collect_preference("test_action", "success", "good")
        
        pref = learner.get_preference("test_action")
        assert pref is not None
        assert pref["preferred"] is True
        
        # 不存在的偏好
        assert learner.get_preference("nonexistent") is None
    
    def test_get_weight(self):
        """测试获取权重"""
        learner = PreferenceLearner()
        
        # 默认权重
        assert learner.get_weight("nonexistent") == 0.5
        
        learner.collect_preference("test_action", "success", "good")
        weight = learner.get_weight("test_action")
        assert weight != 0.5
    
    def test_get_samples(self):
        """测试获取样本"""
        learner = PreferenceLearner()
        
        learner.collect_preference("action1", "success", "good")
        learner.collect_preference("action1", "failure", "bad")
        
        samples = learner.get_samples("action1")
        assert len(samples) == 2
        assert samples[0]["action"] == "action1"
        assert "timestamp" in samples[0]
    
    def test_get_samples_limit(self):
        """测试获取样本限制"""
        learner = PreferenceLearner()
        
        for i in range(20):
            learner.collect_preference("action1", "success", "good")
        
        samples = learner.get_samples("action1", limit=5)
        assert len(samples) == 5
    
    def test_clear_samples_single_action(self):
        """测试清除单个动作样本"""
        learner = PreferenceLearner()
        
        learner.collect_preference("action1", "success", "good")
        learner.collect_preference("action2", "success", "good")
        
        learner.clear_samples("action1")
        
        assert learner._samples.get("action1", []) == []
        assert len(learner._samples["action2"]) == 1
    
    def test_clear_samples_all(self):
        """测试清除所有样本"""
        learner = PreferenceLearner()
        
        learner.collect_preference("action1", "success", "good")
        learner.collect_preference("action2", "success", "good")
        
        learner.clear_samples()
        
        assert learner._samples == {}
    
    def test_export_preferences(self):
        """测试导出偏好"""
        learner = PreferenceLearner()
        
        learner.collect_preference("action1", "success", "good")
        learner.collect_preference("action2", "failure", "bad")
        
        exported = learner.export_preferences()
        
        assert "learned_preferences" in exported
        assert "preference_weights" in exported
        assert "sample_counts" in exported
        assert exported["sample_counts"]["action1"] == 1
        assert exported["sample_counts"]["action2"] == 1
    
    def test_import_preferences(self):
        """测试导入偏好"""
        learner = PreferenceLearner()
        
        data = {
            "learned_preferences": {
                "imported_action": {
                    "preferred": True,
                    "confidence": 0.8,
                    "sample_count": 5,
                }
            },
            "preference_weights": {
                "imported_action": 0.9,
            },
        }
        
        learner.import_preferences(data)
        
        assert learner.get_preference("imported_action") is not None
        assert learner.get_weight("imported_action") == 0.9
    
    def test_with_memory_manager(self):
        """测试带记忆管理器"""
        mock_memory = mock.MagicMock()
        learner = PreferenceLearner(memory_manager=mock_memory)
        
        assert learner._memory == mock_memory


if __name__ == "__main__":
    pytest.main([__file__])
