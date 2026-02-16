"""模板引擎模块."""

import os
import re
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from jinja2 import Environment, BaseLoader, Template as JinjaTemplate, TemplateSyntaxError

from ut_agent.exceptions import TemplateNotFoundError, TemplateRenderError


@dataclass
class UnitTestTemplate:
    """测试模板."""
    name: str
    description: str
    language: str  # java, typescript, vue
    framework: str  # junit5, junit4, vitest, jest
    template_content: str
    variables: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    author: str = ""
    version: str = "1.0.0"


class TemplateEngine:
    """模板引擎."""

    def __init__(self):
        self.env = Environment(loader=BaseLoader())
        self._templates: Dict[str, UnitTestTemplate] = {}
        self.env.filters['lower_first'] = lower_first

    def register_template(self, template: UnitTestTemplate) -> None:
        """注册模板."""
        self._templates[template.name] = template

    def get_template(self, name: str) -> Optional[UnitTestTemplate]:
        """获取模板."""
        return self._templates.get(name)

    def list_templates(
        self,
        language: Optional[str] = None,
        framework: Optional[str] = None
    ) -> List[UnitTestTemplate]:
        """列出模板."""
        templates = list(self._templates.values())

        if language:
            templates = [t for t in templates if t.language == language]

        if framework:
            templates = [t for t in templates if t.framework == framework]

        return templates

    def render(self, template_name: str, context: Dict[str, Any]) -> str:
        """渲染模板."""
        template = self.get_template(template_name)
        if not template:
            raise TemplateNotFoundError(
                f"Template not found: {template_name}",
                template_name=template_name
            )

        try:
            jinja_template = self.env.from_string(template.template_content)
            return jinja_template.render(**context)
        except TemplateSyntaxError as e:
            raise TemplateRenderError(
                f"Template syntax error: {e}",
                template_name=template_name,
                context=context
            )
        except Exception as e:
            raise TemplateRenderError(
                f"Failed to render template: {e}",
                template_name=template_name,
                context=context
            )

    def render_string(self, template_string: str, context: Dict[str, Any]) -> str:
        """渲染字符串模板."""
        try:
            template = self.env.from_string(template_string)
            return template.render(**context)
        except TemplateSyntaxError as e:
            raise TemplateRenderError(
                f"Template syntax error in string template: {e}",
                template_name=None,
                context=context
            )
        except Exception as e:
            raise TemplateRenderError(
                f"Failed to render string template: {e}",
                template_name=None,
                context=context
            )


class TemplateManager:
    """模板管理器."""

    def __init__(self, custom_templates_dir: Optional[str] = None):
        self.engine = TemplateEngine()
        self.custom_templates_dir = custom_templates_dir
        self._load_builtin_templates()
        self._load_custom_templates()

    def _load_builtin_templates(self) -> None:
        """加载内置模板."""
        # Java JUnit 5 Controller 模板
        self.engine.register_template(UnitTestTemplate(
            name="java-spring-controller",
            description="Spring Boot Controller 测试模板",
            language="java",
            framework="junit5",
            tags=["spring", "controller", "web"],
            template_content="""package {{ package }};

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.BeforeEach;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.http.MediaType;

import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@WebMvcTest({{ class_name }}.class)
class {{ class_name }}Test {

    @Autowired
    private MockMvc mockMvc;

    {% for mock in mocks %}
    @MockBean
    private {{ mock.type }} {{ mock.name }};
    {% endfor %}

    @BeforeEach
    void setUp() {
        // 初始化测试数据
    }

    {% for method in methods %}
    @Test
    @DisplayName("{{ method.description | default('测试 ' + method.name) }}")
    void {{ method.name }}_shouldReturnSuccess() throws Exception {
        // Arrange
        {% for mock in method.mocks %}
        when({{ mock.name }}.{{ mock.method }}({{ mock.args }})).thenReturn({{ mock.return_value }});
        {% endfor %}

        // Act & Assert
        mockMvc.perform({{ method.http_method }}("{{ method.endpoint }}")
                .contentType(MediaType.APPLICATION_JSON))
            .andExpect(status().isOk());
    }

    @Test
    @DisplayName("{{ method.description | default('测试 ' + method.name) }} - 异常场景")
    void {{ method.name }}_shouldHandleException() throws Exception {
        // Arrange
        {% for mock in method.mocks %}
        when({{ mock.name }}.{{ mock.method }}(any())).thenThrow(new RuntimeException("模拟异常"));
        {% endfor %}

        // Act & Assert
        mockMvc.perform({{ method.http_method }}("{{ method.endpoint }}")
                .contentType(MediaType.APPLICATION_JSON))
            .andExpect(status().isInternalServerError());
    }
    {% endfor %}
}"""
        ))

        # Java JUnit 5 Service 模板
        self.engine.register_template(UnitTestTemplate(
            name="java-spring-service",
            description="Spring Boot Service 测试模板",
            language="java",
            framework="junit5",
            tags=["spring", "service", "business"],
            template_content="""package {{ package }};

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class {{ class_name }}Test {

    @InjectMocks
    private {{ class_name }} {{ class_name | lower_first }};

    {% for mock in mocks %}
    @Mock
    private {{ mock.type }} {{ mock.name }};
    {% endfor %}

    @BeforeEach
    void setUp() {
        // 初始化测试数据
    }

    {% for method in methods %}
    @Test
    @DisplayName("{{ method.description | default(method.name) }} - 正常场景")
    void {{ method.name }}_withValidInput_shouldReturnSuccess() {
        // Arrange
        {% for param in method.parameters %}
        {{ param.type }} {{ param.name }} = {{ param.test_value }};
        {% endfor %}

        {% for mock in method.mocks %}
        when({{ mock.name }}.{{ mock.method }}({{ mock.args }})).thenReturn({{ mock.return_value }});
        {% endfor %}

        // Act
        {{ method.return_type }} result = {{ class_name | lower_first }}.{{ method.name }}({{ method.param_names }});

        // Assert
        assertNotNull(result);
        {% for assertion in method.assertions %}
        assert{{ assertion.type }}({{ assertion.actual }}, {{ assertion.expected }});
        {% endfor %}
        verify({{ method.mocks[0].name }}).{{ method.mocks[0].method }}(any());
    }

    @Test
    @DisplayName("{{ method.description | default(method.name) }} - 空输入")
    void {{ method.name }}_withNullInput_shouldThrowException() {
        // Act & Assert
        assertThrows(IllegalArgumentException.class, () -> {
            {{ class_name | lower_first }}.{{ method.name }}(null);
        });
    }

    @Test
    @DisplayName("{{ method.description | default(method.name) }} - 边界条件")
    void {{ method.name }}_withBoundaryValues_shouldHandleCorrectly() {
        // Arrange
        {% for param in method.boundary_params %}
        {{ param.type }} {{ param.name }} = {{ param.value }};
        {% endfor %}

        // Act
        {{ method.return_type }} result = {{ class_name | lower_first }}.{{ method.name }}({{ method.param_names }});

        // Assert
        assertNotNull(result);
    }
    {% endfor %}
}"""
        ))

        # Java JUnit 5 Repository 模板
        self.engine.register_template(UnitTestTemplate(
            name="java-spring-repository",
            description="Spring Boot Repository 测试模板",
            language="java",
            framework="junit5",
            tags=["spring", "repository", "data"],
            template_content="""package {{ package }};

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.DisplayName;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.test.context.ActiveProfiles;

import java.util.Optional;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

@DataJpaTest
@ActiveProfiles("test")
class {{ class_name }}Test {

    @Autowired
    private {{ class_name }} {{ class_name | lower_first }};

    @Test
    @DisplayName("保存实体 - 正常场景")
    void save_withValidEntity_shouldPersist() {
        // Arrange
        {{ entity_name }} entity = createTestEntity();

        // Act
        {{ entity_name }} saved = {{ class_name | lower_first }}.save(entity);

        // Assert
        assertNotNull(saved.getId());
        assertEquals(entity.getName(), saved.getName());
    }

    @Test
    @DisplayName("根据ID查询 - 存在的实体")
    void findById_withExistingId_shouldReturnEntity() {
        // Arrange
        {{ entity_name }} entity = createAndSaveEntity();
        Long id = entity.getId();

        // Act
        Optional<{{ entity_name }}> result = {{ class_name | lower_first }}.findById(id);

        // Assert
        assertTrue(result.isPresent());
        assertEquals(entity.getName(), result.get().getName());
    }

    @Test
    @DisplayName("根据ID查询 - 不存在的实体")
    void findById_withNonExistingId_shouldReturnEmpty() {
        // Act
        Optional<{{ entity_name }}> result = {{ class_name | lower_first }}.findById(999L);

        // Assert
        assertFalse(result.isPresent());
    }

    @Test
    @DisplayName("删除实体 - 正常场景")
    void delete_withExistingEntity_shouldRemove() {
        // Arrange
        {{ entity_name }} entity = createAndSaveEntity();
        Long id = entity.getId();

        // Act
        {{ class_name | lower_first }}.delete(entity);

        // Assert
        Optional<{{ entity_name }}> result = {{ class_name | lower_first }}.findById(id);
        assertFalse(result.isPresent());
    }

    private {{ entity_name }} createTestEntity() {
        {{ entity_name }} entity = new {{ entity_name }}();
        // 设置测试数据
        return entity;
    }

    private {{ entity_name }} createAndSaveEntity() {
        return {{ class_name | lower_first }}.save(createTestEntity());
    }
}"""
        ))

        # Vue Vitest 组件模板
        self.engine.register_template(UnitTestTemplate(
            name="vue-component",
            description="Vue 组件测试模板",
            language="typescript",
            framework="vitest",
            tags=["vue", "component", "frontend"],
            template_content="""import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import {{ component_name }} from './{{ component_file }}'

// Mock 依赖
{% for mock in mocks %}
vi.mock('{{ mock.source }}', () => ({
  {{ mock.name }}: vi.fn(() => {{ mock.return_value }})
}))
{% endfor %}

describe('{{ component_name }}', () => {
  let wrapper

  beforeEach(() => {
    wrapper = null
  })

  const createWrapper = (props = {}, options = {}) => {
    return mount({{ component_name }}, {
      props: {
        {% for prop in props %}
        {{ prop.name }}: {{ prop.default_value }},
        {% endfor %}
        ...props
      },
      global: {
        stubs: {
          // 子组件桩
        },
        mocks: {
          // 全局 mock
        }
      },
      ...options
    })
  }

  describe('渲染', () => {
    it('应该正确渲染组件', () => {
      wrapper = createWrapper()
      expect(wrapper.exists()).toBe(true)
    })

    it('应该渲染正确的标题', () => {
      wrapper = createWrapper()
      expect(wrapper.find('.title').exists()).toBe(true)
    })
  })

  describe('Props', () => {
    {% for prop in props %}
    it('应该正确接收 {{ prop.name }} prop', () => {
      const {{ prop.name }} = {{ prop.test_value }}
      wrapper = createWrapper({ {{ prop.name }} })
      expect(wrapper.props('{{ prop.name }}')).toBe({{ prop.name }})
    })
    {% endfor %}
  })

  describe('事件', () => {
    it('应该正确触发点击事件', async () => {
      wrapper = createWrapper()
      await wrapper.find('button').trigger('click')
      expect(wrapper.emitted()).toHaveProperty('click')
    })

    it('应该传递正确的数据到事件', async () => {
      wrapper = createWrapper()
      await wrapper.find('button').trigger('click')
      expect(wrapper.emitted('click')[0]).toEqual([expect.any(Object)])
    })
  })

  describe('方法', () => {
    {% for method in methods %}
    it('{{ method.name }} 应该正常工作', async () => {
      wrapper = createWrapper()
      {% if method.is_async %}
      await wrapper.vm.{{ method.name }}()
      await flushPromises()
      {% else %}
      const result = wrapper.vm.{{ method.name }}()
      {% endif %}
      // 添加断言
    })
    {% endfor %}
  })

  describe('计算属性', () => {
    {% for computed in computed_props %}
    it('{{ computed.name }} 应该返回正确的值', () => {
      wrapper = createWrapper()
      expect(wrapper.vm.{{ computed.name }}).toBe({{ computed.expected_value }})
    })
    {% endfor %}
  })

  describe('边界条件', () => {
    it('应该处理空数据', () => {
      wrapper = createWrapper({ data: [] })
      expect(wrapper.find('.empty-state').exists()).toBe(true)
    })

    it('应该处理加载状态', () => {
      wrapper = createWrapper({ loading: true })
      expect(wrapper.find('.loading').exists()).toBe(true)
    })
  })
})
"""
        ))

        # TypeScript Vitest 工具函数模板
        self.engine.register_template(UnitTestTemplate(
            name="ts-utility",
            description="TypeScript 工具函数测试模板",
            language="typescript",
            framework="vitest",
            tags=["typescript", "utility", "function"],
            template_content="""import { describe, it, expect } from 'vitest'
import { {{ function_name }} } from './{{ file_name }}'

describe('{{ function_name }}', () => {
  describe('正常场景', () => {
    it('应该正确处理正常输入', () => {
      // Arrange
      const input = {{ normal_input }}
      const expected = {{ expected_output }}

      // Act
      const result = {{ function_name }}(input)

      // Assert
      expect(result).toBe(expected)
    })

    {% for test_case in test_cases %}
    it('应该正确处理: {{ test_case.description }}', () => {
      const result = {{ function_name }}({{ test_case.input }})
      expect(result).toEqual({{ test_case.expected }})
    })
    {% endfor %}
  })

  describe('边界条件', () => {
    it('应该处理空输入', () => {
      const result = {{ function_name }}({{ empty_input }})
      expect(result).toBe({{ empty_expected }})
    })

    it('应该处理 null', () => {
      const result = {{ function_name }}(null)
      expect(result).toBeNull()
    })

    it('应该处理 undefined', () => {
      const result = {{ function_name }}(undefined)
      expect(result).toBeUndefined()
    })

    {% if has_numbers %}
    it('应该处理最大值', () => {
      const result = {{ function_name }}(Number.MAX_VALUE)
      expect(result).toBeDefined()
    })

    it('应该处理最小值', () => {
      const result = {{ function_name }}(Number.MIN_VALUE)
      expect(result).toBeDefined()
    })
    {% endif %}

    {% if has_strings %}
    it('应该处理空字符串', () => {
      const result = {{ function_name }}('')
      expect(result).toBe('')
    })

    it('应该处理超长字符串', () => {
      const longString = 'a'.repeat(10000)
      const result = {{ function_name }}(longString)
      expect(result).toBeDefined()
    })
    {% endif %}
  })

  describe('异常场景', () => {
    it('应该抛出异常当输入无效', () => {
      expect(() => {{ function_name }}({{ invalid_input }})).toThrow()
    })

    {% for error_case in error_cases %}
    it('应该抛出异常: {{ error_case.description }}', () => {
      expect(() => {{ function_name }}({{ error_case.input }})).toThrow('{{ error_case.message }}')
    })
    {% endfor %}
  })
})
"""
        ))

        # React Hook 测试模板
        self.engine.register_template(UnitTestTemplate(
            name="react-hook",
            description="React Hook 测试模板",
            language="typescript",
            framework="vitest",
            tags=["react", "hook", "frontend"],
            template_content="""import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { {{ hook_name }} } from './{{ hook_file }}'

// Mock 依赖
{% for mock in mocks %}
vi.mock('{{ mock.source }}', () => ({
  {{ mock.name }}: vi.fn()
}))
{% endfor %}

describe('{{ hook_name }}', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('初始化', () => {
    it('应该返回正确的初始值', () => {
      const { result } = renderHook(() => {{ hook_name }}())

      expect(result.current.{{ initial_state }}).toBe({{ initial_value }})
    })

    it('应该返回所有必需的方法', () => {
      const { result } = renderHook(() => {{ hook_name }}())

      {% for method in methods %}
      expect(typeof result.current.{{ method.name }}).toBe('function')
      {% endfor %}
    })
  })

  describe('状态更新', () => {
    {% for method in state_methods %}
    it('{{ method.name }} 应该正确更新状态', () => {
      const { result } = renderHook(() => {{ hook_name }}())

      act(() => {
        result.current.{{ method.name }}({{ method.test_args }})
      })

      expect(result.current.{{ method.state }}).toBe({{ method.expected_value }})
    })
    {% endfor %}
  })

  describe('副作用', () => {
    it('应该在挂载时执行初始化', () => {
      const mockInit = vi.fn()
      {% if has_init_param %}
      renderHook(() => {{ hook_name }}({ onInit: mockInit }))
      {% else %}
      renderHook(() => {{ hook_name }}())
      {% endif %}

      expect(mockInit).toHaveBeenCalled()
    })

    it('应该在卸载时清理', () => {
      const mockCleanup = vi.fn()
      const { unmount } = renderHook(() => {{ hook_name }}())

      unmount()

      // 验证清理逻辑
    })
  })

  describe('异步操作', () => {
    {% if has_async %}
    it('应该正确处理异步操作', async () => {
      const { result } = renderHook(() => {{ hook_name }}())

      await act(async () => {
        await result.current.{{ async_method }}()
      })

      expect(result.current.{{ loading_state }}).toBe(false)
    })

    it('应该处理异步错误', async () => {
      const { result } = renderHook(() => {{ hook_name }}())

      await act(async () => {
        await result.current.{{ async_method }}()
      })

      expect(result.current.{{ error_state }}).toBeDefined()
    })
    {% endif %}
  })
})
"""
        ))

    def _load_custom_templates(self) -> None:
        """加载用户自定义模板."""
        if not self.custom_templates_dir:
            return

        templates_dir = Path(self.custom_templates_dir)
        if not templates_dir.exists():
            return

        for template_file in templates_dir.glob("*.yaml"):
            try:
                with open(template_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)

                template = UnitTestTemplate(
                    name=data["name"],
                    description=data.get("description", ""),
                    language=data["language"],
                    framework=data["framework"],
                    template_content=data["template"],
                    variables=data.get("variables", {}),
                    tags=data.get("tags", []),
                    author=data.get("author", ""),
                    version=data.get("version", "1.0.0"),
                )
                self.engine.register_template(template)
            except Exception as e:
                print(f"加载模板失败 {template_file}: {e}")

    def get_template(self, name: str) -> Optional[UnitTestTemplate]:
        """获取模板."""
        return self.engine.get_template(name)

    def list_templates(
        self,
        language: Optional[str] = None,
        framework: Optional[str] = None
    ) -> List[UnitTestTemplate]:
        """列出模板."""
        return self.engine.list_templates(language, framework)

    def render_template(
        self,
        template_name: str,
        context: Dict[str, Any]
    ) -> str:
        """渲染模板."""
        return self.engine.render(template_name, context)

    def select_template_for_file(
        self,
        file_analysis: Dict[str, Any]
    ) -> Optional[UnitTestTemplate]:
        """为文件选择合适的模板."""
        language = file_analysis.get("language", "")

        # 根据文件类型选择模板
        if language == "java":
            content = file_analysis.get("content", "")

            if "@Controller" in content or "@RestController" in content:
                return self.engine.get_template("java-spring-controller")
            elif "@Service" in content:
                return self.engine.get_template("java-spring-service")
            elif "@Repository" in content or "extends JpaRepository" in content:
                return self.engine.get_template("java-spring-repository")
            else:
                # 默认使用 Service 模板
                return self.engine.get_template("java-spring-service")

        elif language == "vue":
            return self.engine.get_template("vue-component")

        elif language == "typescript":
            # 检查是否是 Hook
            content = file_analysis.get("content", "")
            if "use" in file_analysis.get("file_name", "").lower():
                return self.engine.get_template("react-hook")
            else:
                return self.engine.get_template("ts-utility")

        return None

    def create_custom_template(
        self,
        name: str,
        description: str,
        language: str,
        framework: str,
        template_content: str,
        variables: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None
    ) -> None:
        """创建自定义模板."""
        if not self.custom_templates_dir:
            raise ValueError("未配置自定义模板目录")

        templates_dir = Path(self.custom_templates_dir)
        templates_dir.mkdir(parents=True, exist_ok=True)

        template_data = {
            "name": name,
            "description": description,
            "language": language,
            "framework": framework,
            "template": template_content,
            "variables": variables or {},
            "tags": tags or [],
            "version": "1.0.0",
        }

        template_file = templates_dir / f"{name}.yaml"
        with open(template_file, "w", encoding="utf-8") as f:
            yaml.dump(template_data, f, allow_unicode=True, default_flow_style=False)

        # 注册新模板
        self.engine.register_template(UnitTestTemplate(
            name=name,
            description=description,
            language=language,
            framework=framework,
            template_content=template_content,
            variables=variables or {},
            tags=tags or [],
        ))


# Jinja2 过滤器
def lower_first(value: str) -> str:
    """首字母小写."""
    if not value:
        return value
    return value[0].lower() + value[1:]
