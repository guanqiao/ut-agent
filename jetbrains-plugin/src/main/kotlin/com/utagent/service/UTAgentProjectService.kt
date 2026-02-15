package com.utagent.service

import com.intellij.execution.ExecutionManager
import com.intellij.execution.RunManager
import com.intellij.execution.configurations.GeneralCommandLine
import com.intellij.execution.process.OSProcessHandler
import com.intellij.execution.process.ProcessAdapter
import com.intellij.execution.process.ProcessEvent
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.progress.ProgressIndicator
import com.intellij.openapi.project.Project
import com.intellij.openapi.vfs.VirtualFile
import com.utagent.actions.GenerateResult
import java.io.File
import java.util.concurrent.CompletableFuture

class UTAgentProjectService(private val project: Project) {
    
    private val settings = UTAgentSettingsService.getInstance()
    
    fun generateTest(sourceFile: VirtualFile, indicator: ProgressIndicator): GenerateResult {
        val projectPath = project.basePath ?: return GenerateResult(false, error = "Project path not found")
        val sourcePath = sourceFile.path
        
        indicator.text = "Running UT-Agent..."
        
        val command = buildCommand(
            "generate",
            "--project", projectPath,
            "--file", sourcePath,
            "--llm", settings.llmProvider.lowercase(),
            "--model", settings.modelName,
            "--coverage-target", settings.targetCoverage.toString(),
            "--max-iterations", settings.maxIterations.toString()
        )
        
        val output = executeCommand(command, indicator)
        
        return if (output.success) {
            val testFilePath = extractTestFilePath(output.output)
            GenerateResult(true, testFilePath)
        } else {
            GenerateResult(false, error = output.error)
        }
    }
    
    fun generateTestForMethod(
        sourceFile: VirtualFile,
        method: com.intellij.psi.PsiMethod,
        selectedText: String
    ) {
        val projectPath = project.basePath ?: return
        val methodName = method.name
        
        ApplicationManager.getApplication().executeOnPooledThread {
            val command = buildCommand(
                "generate-method",
                "--project", projectPath,
                "--file", sourceFile.path,
                "--method", methodName,
                "--llm", settings.llmProvider.lowercase()
            )
            executeCommand(command)
        }
    }
    
    fun generateTestsForProject(callback: (Boolean, String) -> Unit) {
        val projectPath = project.basePath ?: return callback(false, "Project path not found")
        
        ApplicationManager.getApplication().executeOnPooledThread {
            val command = buildCommand(
                "generate",
                "--project", projectPath,
                "--llm", settings.llmProvider.lowercase(),
                "--coverage-target", settings.targetCoverage.toString()
            )
            
            val result = executeCommand(command)
            
            ApplicationManager.getApplication().invokeLater {
                callback(result.success, if (result.success) result.output else result.error)
            }
        }
    }
    
    fun runTestsWithCoverage(testFile: VirtualFile) {
        val projectPath = project.basePath ?: return
        
        ApplicationManager.getApplication().executeOnPooledThread {
            val command = buildCommand(
                "run-coverage",
                "--project", projectPath,
                "--test-file", testFile.path
            )
            executeCommand(command)
        }
    }
    
    fun runCoverageCheck(callback: (Double) -> Unit) {
        val projectPath = project.basePath ?: return callback(0.0)
        
        ApplicationManager.getApplication().executeOnPooledThread {
            val command = buildCommand(
                "check-coverage",
                "--project", projectPath
            )
            
            val result = executeCommand(command)
            val coverage = extractCoverage(result.output)
            
            ApplicationManager.getApplication().invokeLater {
                callback(coverage)
            }
        }
    }
    
    private fun buildCommand(vararg args: String): List<String> {
        val utAgentPath = findUTAgentExecutable()
        val envVars = mutableMapOf<String, String>()
        
        if (settings.apiKey.isNotEmpty()) {
            when (settings.llmProvider.lowercase()) {
                "openai" -> envVars["OPENAI_API_KEY"] = settings.apiKey
                "deepseek" -> envVars["DEEPSEEK_API_KEY"] = settings.apiKey
            }
        }
        
        if (settings.baseUrl.isNotEmpty()) {
            when (settings.llmProvider.lowercase()) {
                "openai" -> envVars["OPENAI_BASE_URL"] = settings.baseUrl
                "deepseek" -> envVars["DEEPSEEK_BASE_URL"] = settings.baseUrl
            }
        }
        
        return listOf(utAgentPath, *args)
    }
    
    private fun findUTAgentExecutable(): String {
        val possiblePaths = listOf(
            "ut-agent",
            "python -m ut_agent",
            "pip show ut-agent"
        )
        
        for (path in possiblePaths) {
            try {
                val process = ProcessBuilder(path.split(" "))
                    .redirectErrorStream(true)
                    .start()
                if (process.waitFor() == 0 || process.exitValue() == 0) {
                    return path.split(" ").first()
                }
            } catch (e: Exception) {
                continue
            }
        }
        
        return "ut-agent"
    }
    
    private fun executeCommand(
        command: List<String>,
        indicator: ProgressIndicator? = null
    ): CommandResult {
        return try {
            val processBuilder = ProcessBuilder(command)
                .directory(File(project.basePath ?: "."))
                .redirectErrorStream(true)
            
            settings.apiKey.takeIf { it.isNotEmpty() }?.let { key ->
                when (settings.llmProvider.lowercase()) {
                    "openai" -> processBuilder.environment()["OPENAI_API_KEY"] = key
                    "deepseek" -> processBuilder.environment()["DEEPSEEK_API_KEY"] = key
                }
            }
            
            val process = processBuilder.start()
            val output = process.inputStream.bufferedReader().readText()
            val exitCode = process.waitFor()
            
            if (exitCode == 0) {
                CommandResult(true, output)
            } else {
                CommandResult(false, error = output)
            }
        } catch (e: Exception) {
            CommandResult(false, error = e.message ?: "Unknown error")
        }
    }
    
    private fun extractTestFilePath(output: String): String {
        val regex = Regex("""Test file:\s*(.+\.java)""")
        return regex.find(output)?.groupValues?.get(1)?.trim() ?: ""
    }
    
    private fun extractCoverage(output: String): Double {
        val regex = Regex("""Overall coverage:\s*([\d.]+)%""")
        return regex.find(output)?.groupValues?.get(1)?.toDoubleOrNull() ?: 0.0
    }
    
    data class CommandResult(
        val success: Boolean,
        val output: String = "",
        val error: String = ""
    )
}
