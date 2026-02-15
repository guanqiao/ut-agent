package com.utagent.config

import com.intellij.openapi.options.Configurable
import com.intellij.openapi.ui.ComboBox
import com.intellij.ui.components.JBPasswordField
import com.intellij.ui.components.JBTextField
import com.intellij.util.ui.FormBuilder
import com.intellij.util.ui.JBUI
import com.utagent.service.UTAgentSettingsService
import javax.swing.JCheckBox
import javax.swing.JComponent
import javax.swing.JPanel

class UTAgentConfigurable : Configurable {
    
    private val settings = UTAgentSettingsService.getInstance()
    
    private val providerCombo = ComboBox(arrayOf("OpenAI", "DeepSeek", "Ollama"))
    private val apiKeyField = JBPasswordField()
    private val baseUrlField = JBTextField()
    private val modelField = JBTextField()
    private val targetCoverageField = JBTextField()
    private val maxIterationsField = JBTextField()
    private val testFrameworkCombo = ComboBox(arrayOf("JUnit 5", "JUnit 4", "TestNG"))
    private val mockFrameworkCombo = ComboBox(arrayOf("Mockito", "PowerMock", "EasyMock"))
    private val autoSaveCheckBox = JCheckBox("Auto-save generated tests")
    private val verboseCheckBox = JCheckBox("Enable verbose logging")
    
    private var modified = false
    
    override fun getDisplayName(): String = "UT-Agent"
    
    override fun createComponent(): JComponent {
        val panel = FormBuilder.createFormBuilder()
            .addSeparator()
            .addComponent(createSectionLabel("LLM Configuration"))
            .addLabeledComponent("Provider:", providerCombo)
            .addLabeledComponent("API Key:", apiKeyField)
            .addLabeledComponent("Base URL (optional):", baseUrlField)
            .addLabeledComponent("Model:", modelField)
            .addSeparator()
            .addComponent(createSectionLabel("Generation Settings"))
            .addLabeledComponent("Target Coverage (%):", targetCoverageField)
            .addLabeledComponent("Max Iterations:", maxIterationsField)
            .addSeparator()
            .addComponent(createSectionLabel("Java Settings"))
            .addLabeledComponent("Test Framework:", testFrameworkCombo)
            .addLabeledComponent("Mock Framework:", mockFrameworkCombo)
            .addSeparator()
            .addComponent(createSectionLabel("Options"))
            .addComponent(autoSaveCheckBox)
            .addComponent(verboseCheckBox)
            .addComponentFillVertically(JPanel(), 0)
            .panel
        
        panel.border = JBUI.Borders.empty(10)
        
        loadSettings()
        setupListeners()
        
        return panel
    }
    
    private fun createSectionLabel(text: String): JComponent {
        return javax.swing.JLabel(text).apply {
            font = font.deriveFont(font.style or java.awt.Font.BOLD)
            border = JBUI.Borders.emptyTop(10)
        }
    }
    
    private fun loadSettings() {
        providerCombo.selectedItem = settings.llmProvider
        apiKeyField.text = settings.apiKey
        baseUrlField.text = settings.baseUrl
        modelField.text = settings.modelName
        targetCoverageField.text = settings.targetCoverage.toString()
        maxIterationsField.text = settings.maxIterations.toString()
        testFrameworkCombo.selectedItem = settings.testFramework.uppercase().replace("JUNIT", "JUnit ")
        mockFrameworkCombo.selectedItem = settings.mockFramework.replaceFirstChar { it.uppercase() }
        autoSaveCheckBox.isSelected = settings.autoSave
        verboseCheckBox.isSelected = settings.verbose
    }
    
    private fun setupListeners() {
        providerCombo.addActionListener { 
            modified = true
            updateModelField()
        }
        apiKeyField.document.addDocumentListener(object : javax.swing.event.DocumentListener {
            override fun insertUpdate(e: javax.swing.event.DocumentEvent?) { modified = true }
            override fun removeUpdate(e: javax.swing.event.DocumentEvent?) { modified = true }
            override fun changedUpdate(e: javax.swing.event.DocumentEvent?) { modified = true }
        })
        baseUrlField.document.addDocumentListener(object : javax.swing.event.DocumentListener {
            override fun insertUpdate(e: javax.swing.event.DocumentEvent?) { modified = true }
            override fun removeUpdate(e: javax.swing.event.DocumentEvent?) { modified = true }
            override fun changedUpdate(e: javax.swing.event.DocumentEvent?) { modified = true }
        })
        modelField.document.addDocumentListener(object : javax.swing.event.DocumentListener {
            override fun insertUpdate(e: javax.swing.event.DocumentEvent?) { modified = true }
            override fun removeUpdate(e: javax.swing.event.DocumentEvent?) { modified = true }
            override fun changedUpdate(e: javax.swing.event.DocumentEvent?) { modified = true }
        })
    }
    
    private fun updateModelField() {
        val provider = providerCombo.selectedItem as String
        val defaultModel = when (provider) {
            "OpenAI" -> "gpt-4"
            "DeepSeek" -> "deepseek-chat"
            "Ollama" -> "llama2"
            else -> ""
        }
        if (modelField.text.isEmpty() || modelField.text in listOf("gpt-4", "deepseek-chat", "llama2")) {
            modelField.text = defaultModel
        }
    }
    
    override fun isModified(): Boolean = modified
    
    override fun apply() {
        settings.llmProvider = providerCombo.selectedItem as String
        settings.apiKey = String(apiKeyField.password)
        settings.baseUrl = baseUrlField.text
        settings.modelName = modelField.text
        settings.targetCoverage = targetCoverageField.text.toDoubleOrNull() ?: 80.0
        settings.maxIterations = maxIterationsField.text.toIntOrNull() ?: 5
        settings.testFramework = (testFrameworkCombo.selectedItem as String).lowercase().replace(" ", "")
        settings.mockFramework = (mockFrameworkCombo.selectedItem as String).lowercase()
        settings.autoSave = autoSaveCheckBox.isSelected
        settings.verbose = verboseCheckBox.isSelected
        modified = false
    }
    
    override fun reset() {
        loadSettings()
        modified = false
    }
}
