package com.utagent.toolwindow

import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.SimpleToolWindowPanel
import com.intellij.ui.components.JBLabel
import com.intellij.ui.components.JBScrollPane
import com.intellij.util.ui.FormBuilder
import com.intellij.util.ui.JBUI
import com.utagent.service.UTAgentSettingsService
import java.awt.BorderLayout
import java.awt.Dimension
import javax.swing.*

class UTAgentToolWindowFactory : com.intellij.openapi.wm.ToolWindowFactory {
    
    override fun createToolWindowContent(project: Project, toolWindow: com.intellij.openapi.wm.ToolWindow) {
        val panel = UTAgentToolWindowPanel(project)
        val content = com.intellij.ui.content.ContentFactory.getInstance().createContent(panel, "", false)
        toolWindow.contentManager.addContent(content)
    }
}

class UTAgentToolWindowPanel(private val project: Project) : SimpleToolWindowPanel(true, true) {
    
    private val settings = UTAgentSettingsService.getInstance()
    
    private val statusLabel = JBLabel("Ready").apply {
        border = JBUI.Borders.empty(5)
    }
    
    private val coverageLabel = JBLabel("Coverage: --")
    private val targetCoverageField = JTextField(settings.targetCoverage.toString()).apply {
        preferredSize = Dimension(60, 30)
    }
    
    private val providerCombo = JComboBox(arrayOf("OpenAI", "DeepSeek", "Ollama")).apply {
        selectedItem = settings.llmProvider
    }
    
    private val modelField = JTextField(settings.modelName).apply {
        preferredSize = Dimension(150, 30)
    }
    
    private val generateButton = JButton("Generate Tests").apply {
        addActionListener { generateTests() }
    }
    
    private val runCoverageButton = JButton("Run with Coverage").apply {
        addActionListener { runWithCoverage() }
    }
    
    private val logArea = JTextArea().apply {
        isEditable = false
        rows = 10
        columns = 30
    }
    
    init {
        setupUI()
    }
    
    private fun setupUI() {
        val configPanel = FormBuilder.createFormBuilder()
            .addLabeledComponent("LLM Provider:", providerCombo)
            .addLabeledComponent("Model:", modelField)
            .addLabeledComponent("Target Coverage (%):", targetCoverageField)
            .addComponentFillVertically(JPanel(), 0)
            .panel
        
        configPanel.border = JBUI.Borders.empty(10)
        
        val buttonPanel = JPanel().apply {
            layout = BoxLayout(this, BoxLayout.X_AXIS)
            add(generateButton)
            add(Box.createHorizontalStrut(10))
            add(runCoverageButton)
        }
        
        val topPanel = JPanel(BorderLayout()).apply {
            add(configPanel, BorderLayout.CENTER)
            add(buttonPanel, BorderLayout.SOUTH)
        }
        
        val statusPanel = JPanel().apply {
            layout = BoxLayout(this, BoxLayout.X_AXIS)
            add(statusLabel)
            add(Box.createHorizontalStrut(20))
            add(coverageLabel)
        }
        
        val scrollPane = JBScrollPane(logArea)
        
        val mainPanel = JPanel(BorderLayout()).apply {
            add(topPanel, BorderLayout.NORTH)
            add(scrollPane, BorderLayout.CENTER)
            add(statusPanel, BorderLayout.SOUTH)
        }
        
        setContent(mainPanel)
    }
    
    private fun generateTests() {
        saveSettings()
        log("Starting test generation...")
        statusLabel.text = "Generating..."
        
        val projectService = project.getService(com.utagent.service.UTAgentProjectService::class.java)
        projectService.generateTestsForProject { success, message ->
            SwingUtilities.invokeLater {
                if (success) {
                    log("Generation completed: $message")
                    statusLabel.text = "Completed"
                } else {
                    log("Generation failed: $message")
                    statusLabel.text = "Failed"
                }
            }
        }
    }
    
    private fun runWithCoverage() {
        saveSettings()
        log("Running tests with coverage...")
        statusLabel.text = "Running..."
        
        val projectService = project.getService(com.utagent.service.UTAgentProjectService::class.java)
        projectService.runCoverageCheck { coverage ->
            SwingUtilities.invokeLater {
                coverageLabel.text = "Coverage: ${String.format("%.1f", coverage)}%"
                statusLabel.text = "Ready"
                log("Coverage check completed: ${String.format("%.1f", coverage)}%")
            }
        }
    }
    
    private fun saveSettings() {
        settings.llmProvider = providerCombo.selectedItem as String
        settings.modelName = modelField.text
        settings.targetCoverage = targetCoverageField.text.toDoubleOrNull() ?: 80.0
    }
    
    private fun log(message: String) {
        SwingUtilities.invokeLater {
            logArea.append("[${
                java.time.LocalTime.now().format(
                    java.time.format.DateTimeFormatter.ofPattern("HH:mm:ss")
                )
            }] $message\n")
        }
    }
    
    fun refresh() {
        providerCombo.selectedItem = settings.llmProvider
        modelField.text = settings.modelName
        targetCoverageField.text = settings.targetCoverage.toString()
    }
}
