package com.utagent.actions

import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.actionSystem.CommonDataKeys
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.progress.ProgressIndicator
import com.intellij.openapi.progress.ProgressManager
import com.intellij.openapi.progress.Task
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.Messages
import com.intellij.openapi.vfs.VirtualFile
import com.intellij.psi.PsiClass
import com.intellij.psi.PsiJavaFile
import com.intellij.psi.PsiManager
import com.utagent.service.UTAgentProjectService
import com.utagent.service.UTAgentSettingsService
import com.utagent.util.FileUtils

class GenerateTestAction : AnAction() {
    
    override fun update(e: AnActionEvent) {
        val project = e.project ?: return
        val file = e.getData(CommonDataKeys.VIRTUAL_FILE) ?: return
        
        val isJavaOrKotlin = file.extension in listOf("java", "kt")
        val isTestFile = file.name.contains("Test", ignoreCase = true) || 
                         file.path.contains("/test/")
        
        e.presentation.isEnabledAndVisible = isJavaOrKotlin && !isTestFile
    }
    
    override fun actionPerformed(e: AnActionEvent) {
        val project = e.project ?: return
        val file = e.getData(CommonDataKeys.VIRTUAL_FILE) ?: return
        
        val settings = UTAgentSettingsService.getInstance()
        if (!settings.isConfigured()) {
            Messages.showWarningDialog(
                project,
                "Please configure UT-Agent settings first.\nGo to Settings > Tools > UT-Agent",
                "UT-Agent Not Configured"
            )
            return
        }
        
        ProgressManager.getInstance().run(object : Task.Backgroundable(project, "Generating Unit Test...", true) {
            private var result: GenerateResult? = null
            
            override fun run(indicator: ProgressIndicator) {
                indicator.isIndeterminate = true
                indicator.text = "Analyzing source file..."
                
                val projectService = project.getService(UTAgentProjectService::class.java)
                result = projectService.generateTest(file, indicator)
            }
            
            override fun onSuccess() {
                result?.let { res ->
                    if (res.success) {
                        ApplicationManager.getApplication().invokeLater {
                            Messages.showInfoMessage(
                                project,
                                "Test generated successfully!\n\nFile: ${res.testFilePath}",
                                "UT-Agent"
                            )
                            FileUtils.openFileInEditor(project, res.testFilePath)
                        }
                    } else {
                        Messages.showErrorDialog(
                            project,
                            "Failed to generate test:\n${res.error}",
                            "UT-Agent Error"
                        )
                    }
                }
            }
            
            override fun onThrowable(error: Throwable) {
                Messages.showErrorDialog(
                    project,
                    "Error generating test: ${error.message}",
                    "UT-Agent Error"
                )
            }
        })
    }
}

data class GenerateResult(
    val success: Boolean,
    val testFilePath: String = "",
    val error: String = ""
)
