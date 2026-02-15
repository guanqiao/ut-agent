package com.utagent.util

import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.editor.Editor
import com.intellij.openapi.fileEditor.FileDocumentManager
import com.intellij.openapi.fileEditor.FileEditorManager
import com.intellij.openapi.project.Project
import com.intellij.openapi.vfs.LocalFileSystem
import com.intellij.openapi.vfs.VirtualFile
import java.io.File

object FileUtils {
    
    fun findOrCreateTestFile(project: Project, sourceFile: VirtualFile): VirtualFile? {
        val projectPath = project.basePath ?: return null
        val sourcePath = sourceFile.path
        
        val testPath = convertToTestPath(projectPath, sourcePath)
        val testFile = File(testPath)
        
        if (!testFile.exists()) {
            testFile.parentFile.mkdirs()
            testFile.createNewFile()
        }
        
        return LocalFileSystem.getInstance().refreshAndFindFileByIoFile(testFile)
    }
    
    fun convertToTestPath(projectPath: String, sourcePath: String): String {
        return sourcePath
            .replace("/src/main/java/", "/src/test/java/")
            .replace("/src/main/kotlin/", "/src/test/kotlin/")
            .replace(".java", "Test.java")
            .replace(".kt", "Test.kt")
    }
    
    fun openFileInEditor(project: Project, filePath: String) {
        ApplicationManager.getApplication().invokeLater {
            val file = LocalFileSystem.getInstance().findFileByPath(filePath)
            if (file != null) {
                FileEditorManager.getInstance(project).openFile(file, true)
            }
        }
    }
    
    fun getEditorForFile(project: Project, file: VirtualFile): Editor? {
        return FileEditorManager.getInstance(project).selectedTextEditor?.takeIf {
            FileDocumentManager.getInstance().getFile(it.document) == file
        }
    }
    
    fun isTestFile(file: VirtualFile): Boolean {
        val path = file.path
        return path.contains("/test/") || 
               path.contains("Test.", ignoreCase = true) ||
               path.contains("Tests.", ignoreCase = true)
    }
    
    fun getSourceFileForTest(testFile: VirtualFile): VirtualFile? {
        val testPath = testFile.path
        val sourcePath = testPath
            .replace("/src/test/java/", "/src/main/java/")
            .replace("/src/test/kotlin/", "/src/main/kotlin/")
            .replace("Test.java", ".java")
            .replace("Test.kt", ".kt")
        
        return LocalFileSystem.getInstance().findFileByPath(sourcePath)
    }
    
    fun getClassName(file: VirtualFile): String {
        return file.nameWithoutExtension
    }
    
    fun getPackageName(file: VirtualFile): String {
        val path = file.path
        val srcIndex = path.indexOf("/src/")
        if (srcIndex == -1) return ""
        
        val afterSrc = path.substring(srcIndex)
        val javaIndex = afterSrc.indexOf("/java/")
        val kotlinIndex = afterSrc.indexOf("/kotlin/")
        
        val packageStart = when {
            javaIndex != -1 -> javaIndex + 6
            kotlinIndex != -1 -> kotlinIndex + 8
            else -> return ""
        }
        
        val packagePath = afterSrc.substring(packageStart, afterSrc.lastIndexOf('/'))
        return packagePath.replace('/', '.')
    }
}
