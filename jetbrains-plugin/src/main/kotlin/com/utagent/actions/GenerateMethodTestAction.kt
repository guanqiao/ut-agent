package com.utagent.actions

import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.actionSystem.CommonDataKeys
import com.intellij.openapi.editor.Editor
import com.intellij.openapi.project.Project
import com.intellij.psi.PsiMethod
import com.intellij.psi.util.PsiTreeUtil
import com.utagent.service.UTAgentProjectService
import com.utagent.service.UTAgentSettingsService

class GenerateMethodTestAction : AnAction() {
    
    override fun update(e: AnActionEvent) {
        val editor = e.getData(CommonDataKeys.EDITOR)
        val file = e.getData(CommonDataKeys.VIRTUAL_FILE)
        
        val isJavaOrKotlin = file?.extension in listOf("java", "kt")
        val hasSelection = editor?.selectionModel?.hasSelection() == true
        
        e.presentation.isEnabledAndVisible = isJavaOrKotlin && hasSelection
    }
    
    override fun actionPerformed(e: AnActionEvent) {
        val project = e.project ?: return
        val editor = e.getData(CommonDataKeys.EDITOR) ?: return
        val file = e.getData(CommonDataKeys.VIRTUAL_FILE) ?: return
        
        val selectedText = editor.selectionModel.selectedText ?: return
        val startOffset = editor.selectionModel.selectionStart
        
        val psiFile = com.intellij.psi.PsiManager.getInstance(project).findFile(
            com.intellij.openapi.vfs.VirtualFileManager.getInstance().findFileByUrl(file.url)!!
        ) ?: return
        
        val element = psiFile.findElementAt(startOffset)
        val method = PsiTreeUtil.getParentOfType(element, PsiMethod::class.java)
        
        if (method != null) {
            val projectService = project.getService(UTAgentProjectService::class.java)
            projectService.generateTestForMethod(file, method, selectedText)
        }
    }
}
