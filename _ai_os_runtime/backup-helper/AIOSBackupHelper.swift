import AppKit
import Foundation

let fileManager = FileManager.default
let environment = ProcessInfo.processInfo.environment
let arguments = ProcessInfo.processInfo.arguments
let requestedVaultRoot = environment["AI_OS_VAULT_ROOT"] ?? "/Volumes/Devarsh SSD/Obsidian memory "
let supportRoot = fileManager.homeDirectoryForCurrentUser
    .appendingPathComponent("Library/Application Support/AIOS", isDirectory: true)
let bookmarkURL = supportRoot.appendingPathComponent("backup-vault.bookmark")

func fail(_ message: String, code: Int32) -> Never {
    FileHandle.standardError.write(Data("\(message)\n".utf8))
    exit(code)
}

func writeBookmark(for vaultURL: URL) throws {
    try fileManager.createDirectory(at: supportRoot, withIntermediateDirectories: true)
    let data = try vaultURL.bookmarkData(options: [.withSecurityScope], includingResourceValuesForKeys: nil, relativeTo: nil)
    try data.write(to: bookmarkURL, options: .atomic)
}

if arguments.contains("--setup-auto") {
    let vaultURL = URL(fileURLWithPath: requestedVaultRoot, isDirectory: true)
    do {
        _ = try fileManager.contentsOfDirectory(atPath: vaultURL.path)
        try writeBookmark(for: vaultURL)
        FileHandle.standardOutput.write(Data("Stored scoped backup access for \(vaultURL.path).\n".utf8))
        exit(0)
    } catch {
        fail("Unable to store scoped vault access automatically: \(error)", code: 89)
    }
}

let hasOperationalMode = arguments.contains("--backup") || arguments.contains("--scheduled-reports")
if arguments.contains("--setup") || (!hasOperationalMode && !arguments.contains("--setup-auto")) {
    let app = NSApplication.shared
    app.setActivationPolicy(.accessory)
    app.activate(ignoringOtherApps: true)

    let panel = NSOpenPanel()
    panel.title = "Choose the AI OS Obsidian vault"
    panel.message = "Grant this backup helper access only to the Obsidian memory folder on Devarsh SSD."
    panel.prompt = "Use Vault"
    panel.canChooseDirectories = true
    panel.canChooseFiles = false
    panel.allowsMultipleSelection = false
    panel.canCreateDirectories = false
    panel.directoryURL = URL(fileURLWithPath: requestedVaultRoot, isDirectory: true)

    guard panel.runModal() == .OK, let selectedURL = panel.url else {
        fail("AI OS Backup Helper setup was cancelled.", code: 80)
    }
    do {
        try writeBookmark(for: selectedURL)
        FileHandle.standardOutput.write(Data("Stored scoped backup access for \(selectedURL.path).\n".utf8))
        exit(0)
    } catch {
        fail("Unable to store scoped vault access: \(error)", code: 81)
    }
}

guard let bookmarkData = try? Data(contentsOf: bookmarkURL) else {
    fail("AI OS Backup Helper is not configured. Run the app once with --setup.", code: 82)
}

var bookmarkIsStale = false
let vaultURL: URL
do {
    vaultURL = try URL(
        resolvingBookmarkData: bookmarkData,
        options: [.withSecurityScope, .withoutUI],
        relativeTo: nil,
        bookmarkDataIsStale: &bookmarkIsStale
    )
} catch {
    fail("Unable to resolve scoped vault access: \(error)", code: 83)
}

guard vaultURL.startAccessingSecurityScopedResource() else {
    fail("Unable to activate scoped vault access. Run setup again.", code: 84)
}

do {
    _ = try fileManager.contentsOfDirectory(atPath: vaultURL.path)
    if bookmarkIsStale { try writeBookmark(for: vaultURL) }
} catch {
    fail("AI OS Backup Helper cannot read the selected vault: \(error)", code: 85)
}

if environment["AI_OS_BACKUP_ACCESS_CHECK_ONLY"] == "1" {
    FileHandle.standardOutput.write(Data("AI OS Backup Helper scoped vault access check passed.\n".utf8))
    vaultURL.stopAccessingSecurityScopedResource()
    exit(0)
}

func runChild(executable: String, arguments: [String], environment: [String: String], failureCode: Int32) -> Int32 {
    let process = Process()
    process.executableURL = URL(fileURLWithPath: executable)
    process.arguments = arguments
    process.environment = environment
    process.standardOutput = FileHandle.standardOutput
    process.standardError = FileHandle.standardError

    do {
        try process.run()
        process.waitUntilExit()
        return process.terminationStatus
    } catch {
        fail("AI OS helper failed to launch \(executable): \(error)", code: failureCode)
    }
}

let runtimeRoot = environment["AI_OS_RUNTIME_ROOT"] ?? "\(requestedVaultRoot)/_ai_os_runtime"
if arguments.contains("--scheduled-reports") {
    let reportScript = "\(runtimeRoot)/scripts/run_scheduled_reports.py"
    guard fileManager.isReadableFile(atPath: reportScript) else {
        fail("AI OS scheduled-report script is unavailable: \(reportScript)", code: 90)
    }
    var childEnvironment = environment
    childEnvironment["AI_OS_VAULT_ROOT"] = vaultURL.path
    childEnvironment["AI_OS_RUNTIME_ROOT"] = runtimeRoot
    let preferredPython = environment["AI_OS_PYTHON_BIN"] ?? "/opt/homebrew/bin/python3"
    let python = fileManager.isExecutableFile(atPath: preferredPython) ? preferredPython : "/usr/bin/python3"
    let status = runChild(
        executable: python,
        arguments: [reportScript, "--all", "--json", "--trigger-type", "launchd"],
        environment: childEnvironment,
        failureCode: 91
    )
    vaultURL.stopAccessingSecurityScopedResource()
    exit(status)
}

let backupRoot = URL(fileURLWithPath: environment["AI_OS_CRITICAL_BACKUP_ROOT"] ?? fileManager.homeDirectoryForCurrentUser.appendingPathComponent("AI_OS_CRITICAL_BACKUP").path, isDirectory: true)
let stagedVault = backupRoot.appendingPathComponent(".vault-stage-\(ProcessInfo.processInfo.processIdentifier)", isDirectory: true)
do {
    try? fileManager.removeItem(at: stagedVault)
    try fileManager.createDirectory(at: stagedVault, withIntermediateDirectories: true)
    for item in try fileManager.contentsOfDirectory(at: vaultURL, includingPropertiesForKeys: nil) where item.lastPathComponent != "_ai_os_runtime" {
        try fileManager.copyItem(at: item, to: stagedVault.appendingPathComponent(item.lastPathComponent))
    }
} catch {
    try? fileManager.removeItem(at: stagedVault)
    fail("Unable to stage the scoped vault copy: \(error)", code: 86)
}

let backupScript = "\(runtimeRoot)/scripts/critical_state_backup.sh"
guard fileManager.isExecutableFile(atPath: backupScript) else {
    fail("AI OS backup script is unavailable or not executable: \(backupScript)", code: 87)
}

var childEnvironment = environment
childEnvironment["AI_OS_BACKUP_VAULT_SOURCE"] = stagedVault.path
childEnvironment["AI_OS_VAULT_ROOT"] = vaultURL.path
let status = runChild(executable: "/bin/bash", arguments: [backupScript], environment: childEnvironment, failureCode: 88)
try? fileManager.removeItem(at: stagedVault)
vaultURL.stopAccessingSecurityScopedResource()
exit(status)
