package com.utagent.actions

import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.actionSystem.CommonDataKeys
import com.intellij.openapi.project.Project
import com.utagent.service.UTAgentProjectService

class RunWithCoverageAction : AnAction() {
    
    override fun update(e: AnActionEvent) {
        val project = e.project
        val file = e.getData(CommonDataKeys.VIRTUAL_FILE)
        
        val isTestFile = file?.name?.contains("Test", ignoreCase = true) == true
        
        e.presentation.isEnabledAndVisible = project != null && isTestFile
    }
    
    override fun actionPerformed(e: AnActionEvent) {
        val project = e.project ?: return
        val file = e.getData(CommonDataKeys.VIRTUAL_FILE) ?: return
        
        val projectService = project.getService(UTAgentProjectService::class.java)
        projectService.runTestsWithCoverage(file)
    }
}
