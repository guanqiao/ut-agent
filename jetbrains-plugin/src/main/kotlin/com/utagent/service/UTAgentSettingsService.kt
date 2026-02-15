package com.utagent.service

import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.components.PersistentStateComponent
import com.intellij.openapi.components.State
import com.intellij.openapi.components.Storage
import com.intellij.util.xmlb.XmlSerializerUtil

@State(
    name = "UTAgentSettings",
    storages = [Storage("ut-agent-settings.xml")]
)
class UTAgentSettingsService : PersistentStateComponent<UTAgentSettingsService.State> {
    
    data class State(
        var llmProvider: String = "OpenAI",
        var apiKey: String = "",
        var baseUrl: String = "",
        var modelName: String = "gpt-4",
        var targetCoverage: Double = 80.0,
        var maxIterations: Int = 5,
        var testFramework: String = "junit5",
        var mockFramework: String = "mockito",
        var autoSave: Boolean = true,
        var verbose: Boolean = false
    )
    
    private var state = State()
    
    override fun getState(): State = state
    
    override fun loadState(state: State) {
        XmlSerializerUtil.copyBean(state, this.state)
    }
    
    var llmProvider: String
        get() = state.llmProvider
        set(value) { state.llmProvider = value }
    
    var apiKey: String
        get() = state.apiKey
        set(value) { state.apiKey = value }
    
    var baseUrl: String
        get() = state.baseUrl
        set(value) { state.baseUrl = value }
    
    var modelName: String
        get() = state.modelName
        set(value) { state.modelName = value }
    
    var targetCoverage: Double
        get() = state.targetCoverage
        set(value) { state.targetCoverage = value }
    
    var maxIterations: Int
        get() = state.maxIterations
        set(value) { state.maxIterations = value }
    
    var testFramework: String
        get() = state.testFramework
        set(value) { state.testFramework = value }
    
    var mockFramework: String
        get() = state.mockFramework
        set(value) { state.mockFramework = value }
    
    var autoSave: Boolean
        get() = state.autoSave
        set(value) { state.autoSave = value }
    
    var verbose: Boolean
        get() = state.verbose
        set(value) { state.verbose = value }
    
    fun isConfigured(): Boolean {
        return when (state.llmProvider.lowercase()) {
            "openai", "deepseek" -> state.apiKey.isNotEmpty()
            "ollama" -> true
            else -> false
        }
    }
    
    companion object {
        fun getInstance(): UTAgentSettingsService {
            return ApplicationManager.getApplication().getService(UTAgentSettingsService::class.java)
        }
    }
}
