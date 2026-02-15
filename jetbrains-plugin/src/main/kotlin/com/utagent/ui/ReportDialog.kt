package com.utagent.ui

import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.DialogWrapper
import com.intellij.ui.components.JBScrollPane
import com.intellij.util.ui.JBUI
import java.awt.BorderLayout
import java.awt.Dimension
import javax.swing.*

class ReportDialog(private val project: Project) : DialogWrapper(project) {
    
    private val reportArea = JTextArea().apply {
        isEditable = false
        rows = 25
        columns = 80
        font = font.deriveFont(12f)
    }
    
    init {
        title = "UT-Agent Coverage Report"
        init()
        loadReport()
    }
    
    override fun createCenterPanel(): JComponent {
        val panel = JPanel(BorderLayout())
        panel.preferredSize = Dimension(700, 500)
        
        val scrollPane = JBScrollPane(reportArea)
        scrollPane.border = JBUI.Borders.empty(10)
        
        val buttonPanel = JPanel().apply {
            add(JButton("Refresh").apply {
                addActionListener { loadReport() }
            })
            add(JButton("Export").apply {
                addActionListener { exportReport() }
            })
        }
        
        panel.add(scrollPane, BorderLayout.CENTER)
        panel.add(buttonPanel, BorderLayout.SOUTH)
        
        return panel
    }
    
    private fun loadReport() {
        val reportPath = "${project.basePath}/target/site/jacoco/index.html"
        val reportFile = java.io.File(reportPath)
        
        if (reportFile.exists()) {
            val content = parseHtmlReport(reportFile.readText())
            reportArea.text = content
        } else {
            reportArea.text = """
                No coverage report found.
                
                Please run tests with coverage first:
                - Right-click on a test file
                - Select "UT-Agent > Run Tests with Coverage"
                
                Or use the CLI:
                ut-agent generate --project ${project.basePath}
            """.trimIndent()
        }
    }
    
    private fun parseHtmlReport(html: String): String {
        val builder = StringBuilder()
        builder.appendLine("=" .repeat(60))
        builder.appendLine("UT-Agent Coverage Report")
        builder.appendLine("=".repeat(60))
        builder.appendLine()
        
        val coverageRegex = Regex("""(\d+%)""")
        val classRegex = Regex("""class="([^"]+)"""")
        
        val lines = html.lines()
        var inTable = false
        
        for (line in lines) {
            when {
                line.contains("<table") -> inTable = true
                line.contains("</table") -> inTable = false
                inTable && line.contains("<td") -> {
                    val text = line.replace(Regex("<[^>]+>"), "").trim()
                    if (text.isNotEmpty()) {
                        builder.append(text.padEnd(20))
                    }
                }
                inTable && line.contains("</tr") -> builder.appendLine()
            }
        }
        
        return builder.toString()
    }
    
    private fun exportReport() {
        val chooser = JFileChooser().apply {
            dialogTitle = "Export Coverage Report"
            selectedFile = java.io.File("coverage-report.txt")
        }
        
        if (chooser.showSaveDialog(contentPane) == JFileChooser.APPROVE_OPTION) {
            chooser.selectedFile.writeText(reportArea.text)
        }
    }
    
    override fun createActions(): Array<Action> {
        return arrayOf(okAction)
    }
}
