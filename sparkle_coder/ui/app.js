"use strict";

const icons = {
  plus: '<path d="M12 5v14M5 12h14"/>',
  chat: '<path d="M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8z"/>',
  folder: '<path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v10H3z"/>',
  file: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M8 13h8M8 17h5"/>',
  history: '<path d="M3 11a9 9 0 1 1 2.6 7M3 4v7h7M12 7v5l3 2"/>',
  settings: '<path d="m12 3 2 3 3-.5.5 3 3 2-2 2 .5 3-3 .5-2 3-2-2-3 .5-.5-3-3-2 2-2-.5-3 3-.5z"/><circle cx="12" cy="12" r="3"/>',
  arrow: '<path d="M12 19V5M5 12l7-7 7 7"/>',
  play: '<path d="m8 5 11 7-11 7z"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  close: '<path d="m6 6 12 12M6 18 18 6"/>',
  stop: '<rect x="6" y="6" width="12" height="12" rx="1"/>',
  bolt: '<path d="m13 2-9 12h7l-1 8 10-12h-7z"/>',
  code: '<path d="m8 7-5 5 5 5M16 7l5 5-5 5M14 4l-4 16"/>',
  shield: '<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6z"/><path d="m8 12 3 3 5-6"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  panel: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M15 4v16"/>',
  power: '<path d="M12 2v10M6.3 4.7a9 9 0 1 0 11.4 0"/>',
  undo: '<path d="m9 5-5 5 5 5M4 10h9a6 6 0 0 1 6 6v3"/>',
  bug: '<path d="M8 6 6 3M16 6l2-3M3 10h4M17 10h4M3 16h4M17 16h4"/><rect x="7" y="6" width="10" height="15" rx="5"/><path d="M7 12h10M12 12v9"/>',
};
function icon(name) { return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (icons[name] || icons.code) + '</svg>'; }
function id(name) { return document.getElementById(name); }
function node(tag, className, text) { const e = document.createElement(tag); if (className) e.className = className; if (text !== undefined) e.textContent = text; return e; }
function fillIcons(root = document) { root.querySelectorAll("[data-icon]").forEach(e => e.innerHTML = icon(e.dataset.icon)); }

id("app").innerHTML = `
<div class="shell">
  <button class="nav-backdrop" id="navBackdrop" aria-label="Close navigation"></button>
  <aside class="sidebar" id="sidebar">
    <div class="brand"><img src="/favicon.svg" alt="" width="32" height="32"><div>SPARKLE<span>CODER</span></div><span class="personal">Personal</span></div>
    <button class="new-task" id="newTask"><span data-icon="plus"></span>New task<span class="shortcut">⌘ K</span></button>
    <nav class="navigation" aria-label="Workspace navigation">
      <button data-view="build" class="nav-item active"><span data-icon="chat"></span>Build<span class="nav-dot"></span></button>
      <button data-view="files" class="nav-item"><span data-icon="folder"></span>Project files<span class="nav-count" id="fileCount">0</span></button>
      <button data-view="monitor" class="nav-item"><span data-icon="panel"></span>Run monitor<span class="nav-count" id="monitorLive">Live</span></button>
      <button id="briefButton" class="nav-item"><span data-icon="file"></span>Project brief</button>
      <button id="setupButton" class="nav-item"><span data-icon="check"></span>Check setup</button>
      <button id="storageButton" class="nav-item"><span data-icon="folder"></span>Device storage</button>
      <button data-view="history" class="nav-item"><span data-icon="history"></span>Run history</button>
    </nav>
    <div class="recent-heading">RECENT TASKS</div><div id="recentTasks" class="recent-tasks"><p class="muted">Your tasks will appear here.</p></div>
    <div class="sidebar-bottom">
      <button id="settingsButton" class="connection-card"><span class="connection-symbol" data-icon="bolt"></span><span class="connection-label"><strong id="connectionLabel">Connect Nemotron</strong><span id="connectionSub">Add your model connection</span></span><span data-icon="settings"></span></button>
      <div class="local-label"><span data-icon="shield"></span>Engine on your device<button id="quitButton" aria-label="Quit application" title="Quit application"><span data-icon="power"></span></button></div>
      <button id="experienceButton" class="text-button experience-button" aria-pressed="false">Switch to advanced view</button>
      <div class="app-version" id="appVersion">PERSONAL EDITION</div>
    </div>
  </aside>
  <main class="workspace">
    <header class="topbar">
      <button class="icon-button mobile-only" id="menuButton" aria-label="Open navigation"><span data-icon="menu"></span></button>
      <span class="project-icon" data-icon="folder"></span>
      <select id="projectSelect" aria-label="Selected project"></select>
      <button class="icon-button" id="addProject" title="Add project" aria-label="Add project"><span data-icon="plus"></span></button>
      <span class="topbar-divider"></span><span class="project-path" id="projectPath"></span>
      <div class="topbar-actions"><button id="trackTask" class="text-button" title="Open live run monitor">Monitor <span id="headerRunStatus">Ready</span></button><button class="icon-button details-toggle" id="detailsButton" aria-label="Show activity panel"><span data-icon="panel"></span></button></div>
    </header>
    <div id="missingProjectsNotice" class="missing-projects-notice" role="status" hidden><span id="missingProjectsText"></span><button id="findProjectFolder" class="button secondary">Find folder</button></div>
    <div class="work-area">
      <section class="main-column">
        <div id="buildView" class="page-view build-view">
          <div class="supervision-strip" id="supervisionStrip" hidden><span class="pulse-dot"></span><span id="currentAction">Ready</span><span id="elapsedTime">0s</span><button id="showMonitor" class="text-button">Details ↗</button></div><div class="conversation" id="conversation">
            <div id="welcome" class="welcome">
              <div class="workspace-label"><span></span>YOUR PERSONAL CODING AGENT</div>
              <h1>What are we building?</h1>
              <p>Describe the result. Watch the work.<br>Review every change.</p>
              <div class="suggestions">
                <button class="suggestion" data-prompt="Build a simple to-do list that works offline. Let me add, complete, and delete tasks, and keep them after refreshing. Use a simple web page. Test the behavior and give me easy steps to open and use it. I do not have programming experience."><span data-icon="code"></span><strong>Start with a to-do list</strong><span>A small first project with clear checks</span></button>
                <button class="suggestion" data-prompt="Inspect this project, identify a concrete bug, reproduce it with a test, and fix it without changing unrelated behavior."><span data-icon="bug"></span><strong>Fix a bug</strong><span>Find the cause and verify a fix</span></button>
                <button class="suggestion" data-mode="ask" data-prompt="Explore this project. Explain its architecture and how to build and test it. Do not change files yet."><span data-icon="folder"></span><strong>Explore a project</strong><span>Understand the code you have</span></button>
              </div>
              <button id="demoButton" class="demo-button"><span class="demo-play" data-icon="play"></span><span><strong>Take it for a test run</strong><span>A local demo. No API key needed.</span></span><span class="demo-arrow">↗</span></button>
            </div>
            <div id="messages" class="messages" aria-live="polite"></div>
            <div id="resultBanner" class="result-banner" hidden></div><section id="deliveryPanel" class="delivery-panel" aria-label="What works and how to use it" hidden></section>
            <section id="repairPanel" class="delivery-panel" aria-label="Repair history" hidden></section>
          </div>
          <div id="approvalCard" class="approval-card" hidden>
            <div class="approval-heading"><span data-icon="shield"></span><strong id="approvalTitle">Permission to run a command</strong></div>
            <p id="approvalDescription">This command runs with your configured permissions and may change files. Review it before allowing.</p>
            <p id="approvalPurpose" class="approval-purpose" hidden></p><details id="approvalDetails"><summary>View the exact command or file changes</summary><pre id="approvalCommand"></pre></details>
            <div class="approval-actions"><button id="denyCommand" class="button secondary">Deny</button><button id="allowCommand" class="button primary">Allow once</button></div>
          </div>
          <form id="taskForm" class="composer">
            <div class="task-mode-row"><label for="taskMode">Mode</label><select id="taskMode"><option value="build">Build · edit and verify</option><option value="ask">Ask · inspect and explain</option></select><span id="runBudgetLabel">Unlimited run</span></div>
            <label class="sr-only" for="goal">Task for Nemotron</label>
            <textarea id="goal" rows="3" maxlength="12000" placeholder="Describe what you want to build or change…"></textarea>
            <div id="verificationFields" class="verification-fields" hidden><label for="verifyCommands">Required checks <span>One command per line</span></label><textarea id="verifyCommands" rows="2" placeholder="For example: python3 -m unittest discover -s tests -v"></textarea><p>These checks run automatically when the agent proposes completion.</p></div>
            <div class="supervision-choice"><label><input type="checkbox" id="reviewEdits" checked> Review each file edit</label><span>Command approvals remain on</span></div><div class="composer-toolbar"><button type="button" id="modelButton" class="model-button"><span data-icon="bolt"></span><span id="modelName">Nemotron Super</span><span class="chevron">⌄</span></button><button type="button" id="toggleChecks" class="text-button"><span data-icon="check"></span><span>Checks</span></button><span class="composer-spacer"></span><button type="button" id="pauseButton" class="button secondary" hidden>Pause</button><button type="button" id="stopButton" class="button danger" hidden><span data-icon="stop"></span>Stop</button><button type="submit" id="runButton" class="button primary">Run agent<span data-icon="arrow"></span></button></div>
          </form>
          <div class="composer-note"><span id="taskNote">Files stay in your project. Commands need your approval.</span><span class="keyboard-hint">Ctrl / ⌘ + Enter</span></div>
        </div>
        <div id="filesView" class="page-view files-view" hidden>
          <div class="view-heading"><div><span class="eyebrow">ON YOUR DEVICE</span><h1>Project files</h1></div><button id="openProjectFolder" class="button secondary">Open folder ↗</button></div>
          <div class="file-actions"><button id="importFiles" class="button primary">Import files</button><button id="importFolder" class="button secondary">Import folder</button><button id="downloadProject" class="button secondary">Download ZIP</button><button id="exportFolder" class="button secondary">Copy to folder</button><button id="refreshFiles" class="text-button">Refresh</button></div>
          <input id="uploadFiles" type="file" multiple hidden><input id="uploadFolder" type="file" webkitdirectory multiple hidden>
          <div id="dropZone" class="drop-zone" tabindex="0">Drop files here, or paste copied files. Existing files are kept; duplicates get a new name.</div>
          <div id="transferStatus" class="transfer-status" hidden role="status"><span id="transferText"></span><button id="cancelImport" class="text-button" hidden>Cancel remaining</button><pre id="transferErrors" hidden></pre></div>
          <label class="sr-only" for="fileSearch">Filter files</label><input id="fileSearch" class="file-search" placeholder="Find a file by name…" type="search">
          <div class="file-workbench"><div id="fileList" class="file-list"></div><div class="file-content"><div class="file-content-heading"><span id="fileName">Select a file</span><span id="fileMeta"></span></div>
          <div class="file-tools"><button id="copyFileText" class="text-button" disabled>Copy text</button><button id="copyFilePath" class="text-button" disabled>Copy path</button><button id="duplicateFile" class="text-button" disabled>Duplicate</button><button id="downloadFile" class="text-button" disabled>Download file</button></div><pre id="filePreview">Your project files will appear here.</pre></div></div>
          <p class="file-limit-note">Built files and binary assets are supported. Transfers: 20 MiB per file, 100 MiB per project export. Credentials, dependencies, Git internals, and agent history are excluded from project exports. Use Open folder for direct device access.</p>
        </div>
        <div id="monitorView" class="page-view monitor-view" hidden>
          <div class="view-heading"><div><span class="eyebrow">YOU CONTROL THE WORK</span><h1>Run monitor</h1></div><div class="monitor-controls"><button id="monitorPause" class="button secondary" disabled>Pause</button><button id="monitorStop" class="button danger" disabled>Stop</button></div></div>
          <div class="monitor-current"><span class="pulse-dot"></span><div><strong id="monitorAction">No active task</strong><span id="monitorHeartbeat">Start a task to see every operation here.</span></div><span class="status-badge" id="monitorStatus">Ready</span></div>
          <div class="monitor-metrics"><div><span>ELAPSED</span><strong id="monitorElapsed">—</strong></div><div><span>MODEL CALLS</span><strong id="monitorCalls">—</strong></div><div><span>FILE-TOOL CHANGES</span><strong id="monitorFiles">0</strong></div><div><span>CHECKS PASSED</span><strong id="monitorChecks">0 / 0</strong></div></div>
          <div class="monitor-plan"><span id="planProgress">No plan recorded yet.</span><progress id="planProgressBar" max="1" value="0" hidden></progress></div>
          <div class="monitor-grid"><section class="timeline-panel"><div class="panel-toolbar"><h2>Activity timeline</h2><button id="downloadReport" class="text-button" disabled>Save report</button></div><div id="eventTimeline" class="event-timeline"></div></section>
          <section class="console-panel"><div class="panel-toolbar"><h2>Command output</h2><div><button id="copyConsole" class="text-button">Copy</button><button id="downloadLog" class="text-button" disabled>Save log</button></div></div><label class="console-follow"><input id="followConsole" type="checkbox" checked> Follow new output</label><pre id="liveConsole" tabindex="0">Command output will appear here as it is emitted.</pre><p>Some programs buffer their output. The current action and elapsed time stay visible while you wait.</p></section></div>
          <div id="monitorAttention" class="monitor-attention" hidden><span>An action needs your approval.</span><button id="reviewPending" class="button primary">Review action</button></div>
        </div>
        <div id="historyView" class="page-view history-view" hidden><div class="view-heading"><div><span class="eyebrow">SAVED WORK</span><h1>Run history</h1></div><span id="historyCount" class="muted"></span></div><div id="historyList"></div></div>
      </section>
      <aside class="inspector" id="inspector" aria-label="Task details">
        <div class="inspector-heading"><span>Task details</span><button id="closeDetails" class="icon-button details-toggle" aria-label="Close activity panel"><span data-icon="close"></span></button><span class="status-badge" id="runStatus">Ready</span></div>
        <div class="inspector-tabs" role="tablist" aria-label="Task information"><button class="active" data-tab="activity" role="tab" aria-selected="true">Activity</button><button data-tab="changes" role="tab" aria-selected="false">Changes<span id="changeCount">0</span></button><button data-tab="checks" role="tab" aria-selected="false">Checks<span id="checkCount">0</span></button></div>
        <div id="activityTab" class="inspector-content"><div id="plan"></div><div class="panel-label">ACTIVITY</div><div id="activityList" class="activity-list"><div class="empty-detail"><span data-icon="bolt"></span><strong>Ready when you are</strong><p>The agent's progress and decisions will appear here.</p></div></div></div>
        <div id="changesTab" class="inspector-content" hidden><div class="panel-toolbar"><span class="panel-label">FILE CHANGES</span><button id="undoButton" class="text-button" disabled><span data-icon="undo"></span>Undo</button></div><div id="changesList"></div></div>
        <div id="checksTab" class="inspector-content" hidden><div class="panel-label">VERIFICATION</div><div id="checksList"></div></div>
        <div class="run-metrics"><div><span>MODEL CALLS</span><strong id="callsMetric">—</strong></div><div><span>TOKENS</span><strong id="tokensMetric">—</strong></div><span class="metrics-icon" data-icon="bolt"></span></div>
      </aside>
    </div>
  </main>
</div>
<dialog id="settingsDialog">
  <div class="dialog-header"><div><span class="eyebrow">YOUR ENGINE</span><h2>Connect Nemotron</h2></div><button class="icon-button" data-close="settingsDialog" aria-label="Close settings"><span data-icon="close"></span></button></div>
  <form id="settingsForm">
    <p class="dialog-intro">Use NVIDIA's API or a Nemotron server running on your own hardware.</p>
    <label for="connectionType">Connection</label><select id="connectionType"><option value="nvidia">NVIDIA API</option><option value="local">Local or custom server</option></select>
    <label for="baseUrl">API base URL</label><input id="baseUrl" type="url" required autocomplete="off">
    <label for="modelId">Model ID</label><input id="modelId" list="modelOptions" required autocomplete="off"><datalist id="modelOptions"><option value="nvidia/nemotron-3-super-120b-a12b"><option value="nvidia/nemotron-3-nano-30b-a3b"><option value="nvidia/nemotron-3-ultra-550b-a55b"></datalist>
    <label for="apiKey">API key <span id="keyHint">Paste it here; it is never written to disk</span></label><div class="folder-input"><input id="apiKey" type="password" autocomplete="new-password" placeholder="Paste your NVIDIA key here"><button type="button" id="showApiKey" class="button secondary" aria-pressed="false">Show</button></div><button type="button" id="clearApiKey" class="text-button key-clear">Remove configured key</button>
    <p class="settings-note">For NVIDIA-hosted models, paste the key from <a href="https://build.nvidia.com/nvidia/nemotron-3-super-120b-a12b" target="_blank" rel="noreferrer">build.nvidia.com</a> here. It stays in memory and is cleared when SPARKLE CODER quits. The CLI alternative is the <code>NVIDIA_API_KEY</code> environment variable.</p>
    <div class="settings-row"><div><label for="executionMode">Run commands in</label><select id="executionMode"><option value="local">This computer</option><option value="docker">Docker container</option></select></div><div><label for="toolFormat">Tool format</label><select id="toolFormat"><option value="native">Native tool calls</option><option value="json">JSON fallback</option></select></div></div>
    <button type="button" id="removeRunCaps" class="button secondary unlimited-button">Remove all run caps</button><p class="settings-note" id="capsHint">Model calls, run duration, total tokens and command duration can all be unlimited.</p>
    <details class="advanced"><summary>Run and connection settings</summary><div class="settings-row"><div><label for="maxSteps">Model calls <span>Blank = unlimited</span></label><input id="maxSteps" type="number" min="1" placeholder="Unlimited"></div><div><label for="maxSeconds">Elapsed seconds <span>Blank = unlimited</span></label><input id="maxSeconds" type="number" min="1" placeholder="Unlimited"></div></div><div class="settings-row"><div><label for="maxTotalTokens">Total tokens <span>Blank = unlimited</span></label><input id="maxTotalTokens" type="number" min="1" placeholder="Unlimited"></div><div><label for="commandTimeout">Command seconds <span>Blank = unlimited</span></label><input id="commandTimeout" type="number" min="1" placeholder="Unlimited"></div></div><div class="settings-row"><div><label for="maxTokens">Output tokens per call</label><input id="maxTokens" type="number" min="1"></div><div><label for="requestTimeout">API response timeout <span>Seconds before retry</span></label><input id="requestTimeout" type="number" min="1"></div></div></details>
    <p class="settings-note">Use <strong>Stop</strong> to end a task. Temporary connection failures retry automatically. Your model provider still controls its context size, output limit, rate limits and account quota.</p>
    <p class="settings-note" id="executionNote">Local commands use your computer's permissions. You approve each agent-proposed command.</p>
    <div id="connectionResult" class="inline-result" role="status" hidden></div>
    <div class="dialog-actions"><button type="button" id="testConnection" class="button secondary">Test connection</button><button type="submit" class="button primary" id="saveSettings">Save connection</button></div>
  </form>
</dialog>
<dialog id="projectDialog"><div class="dialog-header"><div><span class="eyebrow">YOUR FILES</span><h2>Add a project</h2></div><button class="icon-button" data-close="projectDialog" aria-label="Close project dialog"><span data-icon="close"></span></button></div><form id="projectForm"><label for="projectName">Project name</label><input id="projectName" required maxlength="100" placeholder="My next project"><label for="projectFolder">Existing folder <span>Optional</span></label><div class="folder-input"><input id="projectFolder" placeholder="Leave blank to create a new folder"><button type="button" id="browseFolder" class="button secondary">Browse</button></div><p class="settings-note">A new folder is created when you leave this blank. Existing files are preserved.</p><div id="projectError" class="inline-result" hidden></div><div class="dialog-actions"><button type="submit" class="button primary" id="saveProject">Open project</button></div></form></dialog>
<dialog id="undoDialog"><div class="dialog-header"><h2>Undo these file changes?</h2><button class="icon-button" data-close="undoDialog" aria-label="Close rollback dialog"><span data-icon="close"></span></button></div><p class="dialog-intro">Restore files edited by this task. Later changes are protected. Shell commands and external actions cannot be undone here.</p><ul id="undoFiles"></ul><div class="dialog-actions"><button class="button secondary" data-close="undoDialog">Cancel</button><button class="button danger" id="confirmUndo">Undo file changes</button></div></dialog>
<dialog id="storageDialog"><div class="dialog-header"><div><span class="eyebrow">LOCAL DEVICE STORAGE</span><h2>Your data folder</h2></div><button class="icon-button" data-close="storageDialog" aria-label="Close storage settings"><span data-icon="close"></span></button></div><p class="dialog-intro">New projects live in the PROJECTS folder inside SPARKLE CODER. Saved tasks stay with each project. Settings live in APP_DATA beside PROJECTS. Choose an empty folder to move managed data there. Existing projects outside this folder stay in their current locations.</p><label for="projectsPath">Your projects folder</label><input id="projectsPath" readonly><button id="openProjectsDirectory" class="button secondary projects-open">Open PROJECTS folder</button><p id="storageMigration" class="settings-note" hidden></p><label for="storagePath">Settings and managed data <span>Advanced: choose another location</span></label><div class="folder-input"><input id="storagePath"><button id="browseStorage" class="button secondary">Browse</button></div><div class="storage-links"><button id="openStorage" class="text-button">Open current folder ↗</button><button id="copyStoragePath" class="text-button">Copy current path</button></div><p class="settings-note">Switching folders copies data first and keeps the original as a backup. API keys remain in memory.</p><div id="storageResult" class="inline-result" hidden></div><div class="dialog-actions"><button id="saveStorage" class="button primary">Copy data and use this folder</button></div></dialog>
<dialog id="reconnectDialog"><div class="dialog-header"><h2>Find your project folder</h2><button class="icon-button" data-close="reconnectDialog" aria-label="Close folder recovery"><span data-icon="close"></span></button></div>
  <p class="dialog-intro">The app could not find this folder. It may have moved, or its drive may be disconnected. Your saved project entry is kept. You can keep working in another project while you look for it.</p>
  <form id="reconnectForm"><label for="missingProjectSelect">Project to reconnect</label><select id="missingProjectSelect"></select>
  <p class="settings-note">Last known location:</p><p id="missingProjectPath" class="missing-project-path"></p>
  <label for="reconnectPath">Where are its files now?</label><div class="folder-input"><input id="reconnectPath" required placeholder="Choose the existing project folder"><button type="button" id="browseReconnect" class="button secondary">Browse</button></div>
  <p class="settings-note">Choose the folder containing your project files. Saved tasks appear if that folder still contains its .nemotron history. Reconnecting does not copy files or restore deleted files.</p>
  <div id="reconnectResult" class="inline-result" role="status" hidden></div><div class="dialog-actions"><button type="submit" id="saveReconnect" class="button primary">Reconnect project</button></div></form></dialog>
<dialog id="duplicateDialog"><div class="dialog-header"><h2>Copy a project file</h2><button class="icon-button" data-close="duplicateDialog" aria-label="Close"><span data-icon="close"></span></button></div><form id="duplicateForm"><label for="duplicatePath">New path inside this project</label><input id="duplicatePath" required><p class="settings-note">Use forward slashes for folders. Existing files are preserved.</p><div class="dialog-actions"><button type="submit" class="button primary">Create copy</button></div></form></dialog>
<dialog id="exportDialog"><div class="dialog-header"><h2>Copy project to your device</h2><button class="icon-button" data-close="exportDialog" aria-label="Close"><span data-icon="close"></span></button></div><form id="exportForm"><label for="exportPath">Destination folder</label><div class="folder-input"><input id="exportPath" required placeholder="Absolute device-folder path"><button type="button" id="browseExport" class="button secondary">Browse</button></div><p class="settings-note">Creates a new project copy inside this folder. Existing files are preserved. Dependencies, credentials, Git internals, and agent history are excluded.</p><div id="exportResult" class="inline-result" hidden></div><div class="dialog-actions"><button type="submit" id="saveExport" class="button primary">Copy project</button></div></form></dialog>
<dialog id="briefDialog"><div class="dialog-header"><h2>Tell SPARKLE about your project</h2><button class="icon-button" data-close="briefDialog" aria-label="Close project brief"><span data-icon="close"></span></button></div>
  <form id="briefForm"><p class="dialog-intro">Keep your goals in one place. Each new task gets a copy. Saved tasks keep their original checklist, so changes here cannot quietly remove their requirements.</p>
  <label for="briefPurpose">What is this project for?</label><textarea id="briefPurpose" rows="3" maxlength="2000" placeholder="A personal expense tracker I can use offline."></textarea>
  <label for="briefRequirements">What must work? <span>One requirement per line; up to 20</span></label><textarea id="briefRequirements" rows="5" maxlength="6020" placeholder="Add, edit, and delete an expense&#10;Keep expenses after restarting&#10;Export expenses to CSV"></textarea>
  <label for="briefConstraints">Preferences and things to preserve</label><textarea id="briefConstraints" rows="3" maxlength="2000" placeholder="Explain things simply. Keep my existing data. Use local storage."></textarea>
  <p class="settings-note">No programming commands needed. Saved on your device with this project. Do not put passwords or API keys here.</p><div id="briefResult" class="inline-result" role="status" hidden></div>
  <div class="dialog-actions"><button type="submit" id="saveBrief" class="button primary">Save project brief</button></div></form></dialog>
<dialog id="setupDialog"><div class="dialog-header"><h2>Project setup</h2><button class="icon-button" data-close="setupDialog" aria-label="Close setup report"><span data-icon="close"></span></button></div>
  <p id="setupSummary" class="dialog-intro" role="status">Reading project settings…</p><div id="setupItems" class="setup-items"></div><details class="technical-details"><summary>Project map and available checks</summary><pre id="setupMap"></pre></details>
  <p class="settings-note">This scan does not run commands or install software. Finding a tool does not prove its version or the project works.</p>
  <div class="dialog-actions"><button id="setupConnection" class="button secondary">Connect Nemotron</button><button id="refreshSetup" class="button secondary">Check again</button><button id="investigateSetup" class="button primary">Help with setup</button></div></dialog>
<dialog id="quitDialog"><div class="dialog-header"><h2>Close SPARKLE CODER?</h2></div><p class="dialog-intro">The local engine will stop. Your projects and run history are saved. Use the desktop launcher to reopen it.</p><div class="dialog-actions"><button class="button secondary" data-close="quitDialog">Keep working</button><button id="confirmQuit" class="button danger">Quit app</button></div></dialog>
`;
fillIcons();

let appState = null, projectId = null, currentSession = null, currentRun = null;
let files = [], historyItems = [], changes = [], runEvents = [], view = "build", tab = "activity";
let fileData=null, transferBusy=false, cancelTransfer=false, lastConsoleKey="";
let pollTimer = null, lastMessageKey = "", lastChangeKey = "", selectedFile = "", toastTimer = null;
let briefRevision = null, briefProjectId = null, setupProjectId = null;
const hash = new URLSearchParams(location.hash.slice(1));
if (hash.get("token")) { sessionStorage.setItem("sparkleToken", hash.get("token")); window.history.replaceState(null, "", location.pathname); }
const accessToken = sessionStorage.getItem("sparkleToken") || "";

async function api(path, body) {
  const response = await fetch("/api" + path, {
    method: body === undefined ? "GET" : "POST",
    headers: { "X-Sparkle-Token": accessToken, ...(body === undefined ? {} : {"Content-Type": "application/json"}) },
    ...(body === undefined ? {} : {body: JSON.stringify(body)}),
  });
  const result = await response.json();
  const runState=/^\/runs(?:\/|$)/.test(path)&&typeof result.status==="string";
  if (!response.ok || (result.error&&!runState)) throw new Error(result.error || "The request failed.");
  return result;
}
function toast(message) { id("toast").textContent = message; id("toast").classList.add("visible"); clearTimeout(toastTimer); toastTimer = setTimeout(() => id("toast").classList.remove("visible"), 5000); }
function busy() { return currentRun && ["queued", "running", "approval", "pausing", "paused_by_user", "stopping"].includes(currentRun.status); }
function friendly(status) { return ({checked:"Checks passed",answered:"Answer ready",needs_input:"Your input needed",running:"Working",queued:"Starting",approval:"Needs approval",stopping:"Stopping",pausing:"Pausing",paused_by_user:"Paused by you",blocked:"Needs attention",unverified:"Checks pending",paused:"Paused",interrupted:"Stopped",undone:"Undone"})[status] || "Ready"; }
function shortModel(model) { if (model.includes("super")) return "Nemotron Super"; if (model.includes("ultra")) return "Nemotron Ultra"; if (model.includes("nano")) return "Nemotron Nano"; return model.split("/").pop() || "Nemotron"; }
async function action(fn) { try { await fn(); } catch (error) { toast(error.message); } }
function emptyPanel(text, description) { const e = node("div", "empty-detail"); const symbol = node("span"); symbol.innerHTML = icon("code"); e.append(symbol, node("strong", "", text), node("p", "", description)); return e; }
function changeView(name) { view = name; ["build","files","history","monitor"].forEach(v => id(v + "View").hidden = v !== name); document.querySelectorAll("[data-view]").forEach(b => b.classList.toggle("active", b.dataset.view === name)); document.body.classList.remove("sidebar-open"); if(name==="files") action(loadFiles); if(name==="history") action(loadHistory); if(name==="monitor")renderMonitor(); }
function setTab(name) { tab = name; ["activity","changes","checks"].forEach(t => id(t+"Tab").hidden = t!==name); document.querySelectorAll("[data-tab]").forEach(b => { b.classList.toggle("active", b.dataset.tab===name); b.setAttribute("aria-selected", String(b.dataset.tab===name)); }); if(name==="changes") action(loadChanges); }

function renderProjects() {
  id("projectSelect").replaceChildren();
  appState.projects.forEach(p => { const option = node("option","",p.name+(p.available===false?" (folder not found)":"")); option.value=p.id; option.selected=p.id===projectId; id("projectSelect").append(option); });
  const project = appState.projects.find(p=>p.id===projectId);
  id("projectPath").textContent = project ? project.path : "";
  id("projectPath").title = project ? project.path : "";
  const missing=appState.projects.filter(p=>p.available===false);
  id("missingProjectsNotice").hidden=missing.length===0;
  id("missingProjectsText").textContent=missing.length===1 ? "One saved project folder could not be found. You can keep working and reconnect it later." : missing.length+" saved project folders could not be found. You can keep working and reconnect them later.";
}
function renderProvider() {
  const s=appState.settings; id("modelName").textContent=shortModel(s.model);
  id("connectionLabel").textContent=s.connected ? "Nemotron connected" : s.key_configured || !s.base_url.includes("integrate.api.nvidia.com") ? "Model configured" : "Connect Nemotron";
  id("connectionSub").textContent=s.connected ? shortModel(s.model) : "Connection settings";
  id("settingsButton").classList.toggle("connected",s.connected);
  id("appVersion").textContent="PERSONAL EDITION · "+appState.version;
  id("runBudgetLabel").textContent=[s.max_steps,s.max_seconds,s.max_total_tokens,s.command_timeout].some(v=>v!=null)?"Custom run caps":"Unlimited run";
}
function renderControls() {
  const working=busy(); id("runButton").disabled=!!working || transferBusy; id("runButton").firstChild.textContent=working ? "Working " : currentSession ? "Continue " : "Run agent";
  id("taskMode").disabled=!!working;
  id("saveBrief").disabled=!!working;
  id("investigateSetup").disabled=!!working;
  id("reviewEdits").disabled=!!working||id("taskMode").value==="ask";
  id("stopButton").hidden=!working; id("stopButton").disabled=currentRun?.status==="stopping";
  id("projectSelect").disabled=!!working || transferBusy; id("addProject").disabled=!!working||transferBusy; id("newTask").disabled=!!working||transferBusy;
  id("findProjectFolder").disabled=!!working||transferBusy;
  const status=working ? currentRun.status : currentSession?.status;
  id("runStatus").textContent=currentRun?.mode==="demo" && working ? "Demo · "+friendly(status) : friendly(status);
  id("runStatus").className="status-badge "+(status||"");
  id("undoButton").disabled=!!working || !currentSession?.changed_files?.length || currentSession?.undone;
  id("taskNote").textContent=working ? (currentRun.status==="stopping" ? "Stopping commands; an in-flight model request may need to finish." : currentRun.mode==="demo" ? "Offline demo · scripted responses, real file edits and tests." : "Working in your project. You can stop the task at any time.") : "Files stay in your project. Commands need your approval.";
  id("goal").placeholder=currentSession ? "Give this task a follow-up, or continue where it stopped…" : "Describe what you want to build or change…";
  id("approvalCard").hidden=!(currentRun?.approval && currentRun.status==="approval");
  if(currentRun?.approval) {
    const a=currentRun.approval, editing=a.kind==="file edit";
    id("approvalPurpose").hidden=!a.purpose;id("approvalPurpose").textContent=a.purpose?"Why this step: "+a.purpose:"";
    if(id("approvalDetails").dataset.approval!==a.id){id("approvalDetails").dataset.approval=a.id;id("approvalDetails").open=editing;}
    id("approvalTitle").textContent=editing?"Review file edit: "+a.path:"Permission to run a command";
    id("approvalDescription").textContent=editing?(a.truncated?"Preview is truncated. Deny and request a smaller edit for a complete review.":"Review the proposed diff. Allow once applies this edit."):"This command runs with your configured permissions and may change files. Review it before allowing.";
    id("approvalCommand").textContent=editing?a.diff:a.command;
  }
  renderSupervision();
}
function appendText(parent,text) {
  const pieces=text.split(/```/g);
  pieces.forEach((piece,index)=> {
    if(index%2) { const pre=node("pre","message-code"); pre.textContent=piece.replace(/^[\w+-]*\n/,"").trimEnd(); const wrap=node("div","code-copy-wrap"),copy=node("button","code-copy-button","Copy code");copy.type="button";copy.onclick=()=>action(()=>copyText(pre.textContent));wrap.append(copy,pre);parent.append(wrap); }
    else if(piece.trim()) parent.append(node("div","message-text",piece.trim()));
  });
}
function renderSession(session) {
  currentSession=session;
  id("welcome").hidden=!!session; id("messages").hidden=!session;
  const messageKey=JSON.stringify(session?.messages||[]);
  if(messageKey!==lastMessageKey) {
    const container=id("conversation"), nearBottom=container.scrollHeight-container.scrollTop-container.clientHeight<120;
    id("messages").replaceChildren();
    (session?.messages||[]).forEach(message=> {
      const row=node("article","message "+message.role);
      const label=node("div","message-author",message.role==="user" ? "You" : "SPARKLE CODER");
      const avatar=node("span","message-avatar"); avatar.innerHTML=icon(message.role==="user"?"chat":"bolt"); label.prepend(avatar); row.append(label);
      const body=node("div","message-body"); appendText(body,message.content); row.append(body); id("messages").append(row);
    });
    lastMessageKey=messageKey; if(nearBottom || !session) container.scrollTop=container.scrollHeight;
  }
  id("resultBanner").hidden=!session || busy() || session.status==="running";
  if(session && !busy()) renderRecovery(session);
  renderDelivery(session);
  renderRepairHistory(session);
  id("callsMetric").textContent=session?.usage?.calls ?? "—";
  const usage=session?.usage; id("tokensMetric").textContent=usage ? ((usage.prompt_tokens||0)+(usage.completion_tokens||0)).toLocaleString() : "—";
  id("changeCount").textContent=session?.changed_files?.length||0; id("checkCount").textContent=session?.checks?.length||0;
  id("plan").replaceChildren();
  if(session?.plan?.length) {
    id("plan").append(node("div","panel-label","PLAN"));
    session.plan.forEach(step=> { const row=node("div","plan-step "+step.status); const mark=node("span","plan-mark",step.status==="completed"?"✓":step.status==="in_progress"?"•":""); row.append(mark,node("span","",step.step)); id("plan").append(row); });
  }
  renderActivity(); renderChecks(); renderControls(); renderMonitor();
}
function renderActivity() {
  const target=id("activityList"); target.replaceChildren();
  const actions=currentSession?.actions||[];
  if(!actions.length && !runEvents.length) { target.append(emptyPanel("Ready when you are","The agent's progress and decisions will appear here.")); return; }
  const names={inspect_setup:"Inspected project setup",revise_check:"Corrected a test",update_delivery:"Prepared usage instructions",discover_checks:"Found project checks",request_input:"Asked for a missing detail",list_files:"Explored project",read_file:"Read file",search_files:"Searched code",write_file:"Wrote file",edit_file:"Edited file",delete_file:"Removed file",run_command:"Ran command",verify:"Ran verification",update_plan:"Updated plan",remember:"Saved project memory"};
  actions.slice(-25).reverse().forEach(a=> { const row=node("div","activity-row"); const marker=node("span","activity-marker "+(a.ok?"ok":"failed")); marker.innerHTML=icon(a.ok?"check":"close"); const detail=node("div"); detail.append(node("strong","",names[a.tool]||a.tool),node("span","",a.label||a.purpose||a.path||a.query||(a.command?"Command recorded — open Run monitor for details":a.ok?"Completed":"Needs attention"))); row.append(marker,detail); if(a.error) row.title=a.error; target.append(row); });
  if(busy()) { const latest=runEvents[runEvents.length-1]; const row=node("div","live-activity",latest?.text?.slice(0,250)||"Working…"); target.prepend(row); }
}
function renderRecovery(session) {
  const banner=id("resultBanner"),recovery=session.recovery,attention=["needs_input","blocked","unverified"].includes(session.status);
  banner.replaceChildren();banner.className="result-banner "+session.status;
  banner.append(node("strong","recovery-title",attention?(recovery?.title||"This task needs another step"):friendly(session.status)));
  if(attention) {
    banner.append(node("p","",recovery?.what_happened||"The work is saved, but the checks are not complete."));
    if(recovery?.meaning)banner.append(node("p","recovery-meaning",recovery.meaning));
    banner.append(node("p","recovery-next",recovery?.next_step||"Ask SPARKLE CODER to investigate, or add a missing detail below."));
    const details=node("details","technical-details");details.append(node("summary","","Technical details (optional)"),node("pre","",recovery?.technical_details||session.summary||"See the recorded checks for details."));banner.append(details);
  } else banner.append(node("p","",session.status==="checked"?"The recorded checks passed. See what they cover below.":session.status==="answered"?"Switch to Build when you want changes.":"Your work is saved. Continue when you are ready."));
  if(session.status==="undone")return;
  const actions=node("div","recovery-actions");
  if(attention||["paused","interrupted"].includes(session.status)) {
    const fix=recovery?.can_auto_fix!==false&&attention;
    const resume=node("button","button primary",fix?"Try fixing it":"Resume task");
    resume.onclick=()=>fix?followup("Please investigate and fix the failed checks. Check whether the code or the test is wrong, preserve my requirements, and explain the result simply.","build"):id("taskForm").requestSubmit();actions.append(resume);
  }
  if(recovery?.action==="connection"){const settings=node("button","button secondary","Connection settings");settings.onclick=openSettings;actions.prepend(settings);}
  if(attention){const explain=node("button","button secondary","Explain this simply");explain.onclick=()=>followup("Explain the current problem in simple words. Tell me what happened, what is still unknown, and exactly what I need to do, if anything. Do not change files.","ask");actions.append(explain);}
  if(attention||session.status==="checked"){const checks=node("button","button secondary","See checks");checks.onclick=()=>{setTab("checks");document.body.classList.add("details-open");};actions.append(checks);}
  banner.append(actions);
}
function followup(message,mode) {
  if(busy())return;
  id("taskMode").value=mode;
  id("goal").value=[id("goal").value.trim(),message].filter(Boolean).join("\n\n");
  id("taskForm").requestSubmit();
}
function renderDelivery(session) {
  const panel=id("deliveryPanel"),delivery=session?.delivery||{},proof=session?.proof;
  panel.hidden=!session||(!delivery.summary&&!proof?.total&&!proof?.requirements?.length);panel.replaceChildren();if(panel.hidden)return;
  panel.append(node("h2","","What works and what is left"));
  if(delivery.summary){panel.append(node("p","delivery-summary",delivery.summary),node("span","delivery-source","Agent explanation · check evidence below"));}
  if(proof?.total)panel.append(node("p","proof-count",proof.passed+" of "+proof.total+" current checks passed"+(proof.needs_recheck?" · "+proof.needs_recheck+" need to run again":"")));
  const labels={passed:"Check passed",needs_fix:"Needs a fix",not_checked:"Not checked yet",needs_recheck:"Needs another check"};
  if(proof?.requirements?.length){
    panel.append(node("h3","","Your requirements"),node("p","proof-count",proof.requirements_passed+" of "+proof.requirements.length+" have passing evidence"));
    proof.requirements.forEach(item=>{const row=node("div","proof-feature");row.append(node("span","",item.text),node("span","proof-state "+item.status,labels[item.status]));panel.append(row);});
  }
  (proof?.features||[]).forEach(feature=>{const row=node("div","proof-feature");row.append(node("span","",feature.feature),node("span","proof-state "+feature.status,labels[feature.status]));panel.append(row);});
  if(proof?.note)panel.append(node("p","proof-note",proof.note));
  if(delivery.how_to_use?.length){panel.append(node("h3","","How to use it"));const steps=node("ol","usage-steps");delivery.how_to_use.forEach(step=>steps.append(node("li","",step)));panel.append(steps);}
  if(delivery.limitations?.length){panel.append(node("h3","","Still to check or finish"));const list=node("ul","usage-steps");delivery.limitations.forEach(item=>list.append(node("li","",item)));panel.append(list);}
  if(!busy()){const controls=node("div","recovery-actions"),how=node("button","button secondary","Explain how to use it"),folder=node("button","button secondary","Open project folder");how.onclick=()=>followup("Explain how to open and use this project, step by step, for someone who does not program. State any missing setup clearly.","ask");folder.onclick=()=>action(()=>api("/open-folder",{project_id:projectId}));controls.append(how,folder);panel.append(controls);}
}
function checkCard(c) {
  const box=node("details","check-card "+(c.superseded?"superseded":c.ok?"passed":"failed"));
  const summary=node("summary"),badge=node("span","check-indicator",c.superseded?"↪":c.ok?"✓":"×");
  summary.append(badge,node("span","check-command",c.label||"Project check"));box.append(summary);
  if(c.superseded)box.append(node("p","check-explanation","This earlier test was corrected. Its result is kept for reference."),node("p","check-explanation",c.correction_reason));
  else if(c.explanation)box.append(node("p","check-explanation",c.explanation.what_happened),node("p","check-explanation",c.explanation.meaning));
  box.append(node("div","check-meta",(c.required?"Your required check":c.source==="discovered"?"Existing project check":"Agent-created check")+" · "+(c.ok?"Recorded pass":"Did not pass")),node("pre","check-output",c.command+"\n\n"+(c.output||"No output was produced.")));return box;
}
function renderChecks() {
  const target=id("checksList"),checks=currentSession?.checks||[];target.replaceChildren();
  if(!checks.length){target.append(emptyPanel("No checks yet","Checks show whether the project behaves as intended. SPARKLE CODER can find or create them."));return;}
  checks.filter(c=>c.active!==false).slice().reverse().forEach(c=>target.append(checkCard(c)));
  const earlier=checks.filter(c=>c.active===false);
  if(earlier.length){const history=node("details","check-history");history.append(node("summary","","Earlier checks and corrections ("+earlier.length+")"));earlier.slice().reverse().forEach(c=>history.append(checkCard(c)));target.append(history);}
}
function renderRepairHistory(session) {
  const panel=id("repairPanel"),reviews=session?.repair_history||[];
  panel.replaceChildren();panel.hidden=!reviews.length;if(panel.hidden)return;
  const details=node("details","repair-history");details.append(node("summary","","What SPARKLE investigated ("+reviews.length+" reviews)"));
  reviews.slice(-8).reverse().forEach(review=>{
    const entry=node("article","repair-entry");entry.append(node("strong","",review.what_happened),node("p","",review.next_step));
    entry.append(node("p","proof-note","Source files inspected: "+(review.files?.join(", ")||"No matching file was found; more investigation is needed.")));
    if(review.missing_requirements?.length)entry.append(node("p","","Still to check: "+review.missing_requirements.join("; ")));
    details.append(entry);
  });panel.append(details);
}
async function loadChanges() {
  id("changesList").replaceChildren();
  if(!currentSession) { id("changesList").append(emptyPanel("No changes yet","File edits will appear here as the agent works.")); return; }
  const result=await api("/projects/"+projectId+"/sessions/"+currentSession.id+"/changes"); changes=result.changes;
  if(!changes.length) id("changesList").append(emptyPanel("No changes yet","This task has not edited files through the agent's file tools."));
  changes.forEach(c=> { const box=node("details","change-card"), summary=node("summary"); summary.append(node("span","changed-path",c.path),node("span","diff-add","+"+c.added),node("span","diff-remove","−"+c.removed)); box.append(summary); const pre=node("pre","diff"); c.diff.split("\n").forEach(line=>pre.append(node("span",line.startsWith("+")?"addition":line.startsWith("-")?"deletion":"",line+"\n"))); box.append(pre); id("changesList").append(box); });
}
async function loadFiles() {
  if(!projectId)return;
  const requestedProject=projectId,result=await api("/projects/"+projectId+"/files");
  if(requestedProject!==projectId)return;
  files=result.files; id("fileCount").textContent=files.length+(result.truncated?"+":""); renderFileList();
  if(selectedFile&&!files.includes(selectedFile)){selectedFile="";fileData=null;id("filePreview").textContent="Select a file to preview it.";}
  renderFileButtons();
}
function renderFileList() {
  id("fileList").replaceChildren();
  const query=id("fileSearch").value.toLowerCase(),shown=files.filter(path=>path.toLowerCase().includes(query));
  if(!shown.length)id("fileList").append(node("p","empty-file-list",files.length?"No matching files.":"Import files or start a task to add code."));
  shown.forEach(path=>{const button=node("button","file-row"+(selectedFile===path?" selected":""),path);const mark=node("span");mark.innerHTML=icon("file");button.prepend(mark);button.title=path;button.onclick=()=>action(()=>openFile(path));id("fileList").append(button);});
}
async function openFile(path) {
  const requestedProject=projectId;selectedFile=path;
  const data=await api("/projects/"+projectId+"/file?path="+encodeURIComponent(path));
  if(projectId!==requestedProject||selectedFile!==path)return;
  fileData=data;id("fileName").textContent=path;
  id("fileMeta").textContent=humanBytes(data.bytes)+(data.truncated?" · preview truncated":"");
  id("filePreview").textContent=data.binary?"Binary file. Use Download file or Duplicate to copy it.":data.content;
  renderFileList();renderFileButtons();
}
async function loadHistory() {
  if(!projectId)return; historyItems=(await api("/projects/"+projectId+"/sessions")).sessions;
  id("recentTasks").replaceChildren(); id("historyList").replaceChildren(); id("historyCount").textContent=historyItems.length+" saved";
  if(!historyItems.length) { id("recentTasks").append(node("p","muted","Your tasks will appear here.")); id("historyList").append(emptyPanel("A fresh start","Every task is saved here so you can review or continue it.")); }
  historyItems.forEach((s,index)=> {
    const date=new Date(s.updated).toLocaleString([], {month:"short",day:"numeric",hour:"2-digit",minute:"2-digit"});
    const button=node("button","history-row"); const copy=node("div"); copy.append(node("strong","",s.goal),node("span","",date)); button.append(copy,node("span","status-badge "+s.status,friendly(s.status))); button.onclick=()=>action(()=>loadSession(s.id)); id("historyList").append(button);
    if(index<6) { const recent=node("button","recent-item",s.goal); recent.title=s.goal; recent.onclick=()=>action(()=>loadSession(s.id)); id("recentTasks").append(recent); }
  });
}
async function loadSession(sessionId) { if(busy()) { toast("Finish or stop the current task first."); return; } currentRun=null; runEvents=[]; const data=await api("/projects/"+projectId+"/sessions/"+sessionId); runEvents=data.events||[]; id("taskMode").value=data.task_mode||"build"; renderSession(data); id("verifyCommands").value=(data.required_checks||[]).join("\n"); changeView("build"); if(tab==="changes")await loadChanges(); }
async function newTask() { if(busy()||transferBusy)return; currentRun=null; runEvents=[]; id("taskMode").value="build"; renderSession(null); id("goal").value=""; id("verifyCommands").value=""; id("verificationFields").hidden=true; changeView("build"); setTab("activity"); id("goal").focus(); }
async function selectProject(next) { if(busy()||transferBusy)return; if(appState.projects.find(p=>p.id===next)?.available===false){renderProjects();openReconnect(next);return;} await api("/select-project",{project_id:next}); projectId=next; selectedFile=""; fileData=null; id("fileSearch").value=""; id("fileName").textContent="Select a file"; id("filePreview").textContent="Select a file to inspect its contents."; renderProjects(); await newTask(); await Promise.all([loadFiles(),loadHistory()]); }
async function refreshState() { appState=await api("/state"); projectId=projectId||appState.selected_project; renderProjects(); renderProvider(); renderExperience(); if(appState.active_run&&!currentRun) { currentRun=appState.active_run; projectId=currentRun.project_id; renderProjects(); schedulePoll(50); } }

function schedulePoll(ms=600) { clearTimeout(pollTimer); pollTimer=setTimeout(()=>action(pollRun),ms); }
async function pollRun() {
  if(!currentRun)return;
  const runId=currentRun.id, after=runEvents[runEvents.length-1]?.sequence||0;
  try {
    const result=await api("/runs/"+runId+"?after="+after); if(currentRun?.id!==runId)return;
    currentRun=result; runEvents.push(...result.events); runEvents=runEvents.slice(-600);
    if(result.session){id("taskMode").value=result.session.task_mode||"build";renderSession(result.session);}else renderControls();
    if(result.error)toast(result.error);
    renderMonitor();
    const changeKey=(result.session?.changed_files||[]).join()+":"+(result.session?.actions?.length||0);
    if(tab==="changes"&&changeKey!==lastChangeKey) { lastChangeKey=changeKey; await loadChanges(); }
    if(busy())schedulePoll();
    else { await Promise.all([loadFiles(),loadHistory()]); renderControls(); }
  } catch(error) { toast(error.message); id("monitorHeartbeat").textContent="Connection lost. Retrying; the engine may still be working."; if(busy())schedulePoll(2000); }
}
async function startTask(event) {
  event.preventDefault(); if(busy()||transferBusy)return;
  const goal=id("goal").value.trim(); if(!goal&&!currentSession) { id("goal").focus(); return; }
  if(appState.settings.base_url.includes("integrate.api.nvidia.com")&&!appState.settings.key_configured) { openSettings(); toast("Add your NVIDIA API key to start a live task."); return; }
  id("runButton").disabled=true;
  try {
    const result=await api("/runs",{project_id:projectId,goal,verify:id("verifyCommands").value.split("\n").map(x=>x.trim()).filter(Boolean),session_id:currentSession?.undone?null:currentSession?.id,review_edits:id("reviewEdits").checked,task_mode:id("taskMode").value});
    currentRun=result; runEvents=[]; lastChangeKey=""; id("goal").value=""; changeView("build"); renderControls(); schedulePoll(50);
  } finally { renderControls(); }
}
async function startDemo() { if(busy())return; id("demoButton").disabled=true; try { const result=await api("/demo",{}); currentRun=result.run; projectId=result.project.id; runEvents=[]; currentSession=null; await refreshState(); renderSession(null); changeView("monitor"); schedulePoll(50); } finally { id("demoButton").disabled=false; } }
async function answerApproval(allow) { if(!currentRun?.approval)return; id("allowCommand").disabled=true; id("denyCommand").disabled=true; try { await api("/runs/"+currentRun.id+"/approval",{approval_id:currentRun.approval.id,allow}); currentRun.approval=null; renderControls(); schedulePoll(10); } finally { id("allowCommand").disabled=false; id("denyCommand").disabled=false; } }

function openSettings() {
  const s=appState.settings; id("baseUrl").value=s.base_url; id("modelId").value=s.model; id("apiKey").value="";
  id("apiKey").placeholder=s.key_configured?"Key is set. Leave blank to keep it.":"Paste your key here";
  id("apiKey").type="password";id("showApiKey").textContent="Show";id("showApiKey").setAttribute("aria-pressed","false");
  id("keyHint").textContent=s.key_configured?(s.key_source==="environment"?"Loaded from your environment":"Key ready for this app session"):"Paste your NVIDIA API key below";
  id("clearApiKey").disabled=!s.key_configured;
  id("executionMode").value=s.execution; id("toolFormat").value=s.tool_format;
  id("maxSteps").value=s.max_steps ?? ""; id("maxSeconds").value=s.max_seconds ?? "";
  id("maxTotalTokens").value=s.max_total_tokens ?? ""; id("maxTokens").value=s.max_tokens;
  id("commandTimeout").value=s.command_timeout ?? "";id("requestTimeout").value=s.request_timeout;
  id("capsHint").textContent="Blank run caps mean unlimited. Changes apply to your next run or resumed task.";
  id("connectionType").value=s.base_url.includes("integrate.api.nvidia.com")?"nvidia":"local"; id("connectionResult").hidden=true; id("settingsDialog").showModal();
}
async function saveSettings(test=false) {
  const optionalNumber=(name)=>{const raw=id(name).value.trim(); if(!raw)return null; const value=Number(raw); return Number.isInteger(value)?value:raw;};
  const body={base_url:id("baseUrl").value.trim(),model:id("modelId").value.trim(),api_key:id("apiKey").value.trim(),execution:id("executionMode").value,tool_format:id("toolFormat").value,max_steps:optionalNumber("maxSteps"),max_seconds:optionalNumber("maxSeconds"),max_total_tokens:optionalNumber("maxTotalTokens"),command_timeout:optionalNumber("commandTimeout"),request_timeout:Number(id("requestTimeout").value),max_tokens:Number(id("maxTokens").value)};
  id("saveSettings").disabled=true; id("testConnection").disabled=true;
  try {
    await api("/settings",body); id("apiKey").value=""; await refreshState(); id("clearApiKey").disabled=!appState.settings.key_configured; id("keyHint").textContent=appState.settings.key_configured?"Key ready for this connection":"No API key configured";
    if(test) { id("connectionResult").hidden=false; id("connectionResult").textContent="Checking the model endpoint…"; const result=await api("/connect",{}); id("connectionResult").textContent=result.message; id("connectionResult").className="inline-result "+(result.connected?"success":""); if(result.models?.length) { id("modelOptions").replaceChildren(); result.models.filter(x=>x.toLowerCase().includes("nemotron")).forEach(x=>{const option=node("option");option.value=x;id("modelOptions").append(option);}); } await refreshState(); }
    else { id("settingsDialog").close(); toast("Connection saved. Your key stays in this app process."); }
  } catch(error) { id("connectionResult").hidden=false; id("connectionResult").className="inline-result"; id("connectionResult").textContent=error.message; }
  finally { id("saveSettings").disabled=false; id("testConnection").disabled=false; }
}

function renderExperience() {
  const advanced=appState.experience==="advanced";
  document.body.classList.toggle("simple-mode",!advanced);
  id("experienceButton").textContent=advanced?"Switch to simple view":"Switch to advanced view";
  id("experienceButton").setAttribute("aria-pressed",String(advanced));
}
async function openProjectBrief() {
  briefProjectId=projectId;
  id("briefResult").hidden=true;id("saveBrief").disabled=true;
  const result=await api("/projects/"+briefProjectId+"/brief");
  briefRevision=result.revision;
  id("briefPurpose").value=result.brief.purpose;
  id("briefRequirements").value=result.brief.requirements.join("\n");
  id("briefConstraints").value=result.brief.constraints;
  id("saveBrief").disabled=!!busy();id("briefDialog").showModal();
}
async function saveProjectBrief(event) {
  event.preventDefault();if(busy())return;
  id("saveBrief").disabled=true;id("briefResult").hidden=false;
  try {
    const result=await api("/projects/"+briefProjectId+"/brief",{revision:briefRevision,brief:{
      purpose:id("briefPurpose").value,requirements:id("briefRequirements").value.split("\n").map(x=>x.trim()).filter(Boolean),constraints:id("briefConstraints").value}});
    briefRevision=result.revision;id("briefResult").textContent="Saved. New tasks will use this brief. Existing tasks keep their original checklist.";
  } catch(error) {id("briefResult").textContent=error.message;}
  finally {id("saveBrief").disabled=!!busy();}
}
function renderSetupReport(report) {
  id("setupSummary").textContent=report.attention?report.attention+" setup item(s) need attention. Your files are saved.":"No missing tools were identified by this scan. Project tests still need to run.";
  const target=id("setupItems");target.replaceChildren();
  const labels={found:"Found",attention:"Needs attention",info:"Not verified"};
  report.items.forEach(item=>{
    const card=node("article","setup-item "+item.status),heading=node("div","setup-item-heading");
    heading.append(node("strong","",item.title),node("span","",labels[item.status]));card.append(heading,node("p","",item.detail));
    if(item.next_step)card.append(node("p","setup-next",item.next_step));target.append(card);
  });
  const overview=report.overview;
  id("setupMap").textContent=["Files inspected: "+overview.file_count+(overview.scan_truncated?" (partial scan)":""),
    "Languages: "+(Object.keys(overview.languages).join(", ")||"Not identified yet"),
    "Project settings: "+(overview.manifests.join(", ")||"None found"),
    "Starting points: "+(overview.entry_points.join(", ")||"None identified"),
    "\nCandidate checks (not executed):",...report.checks.map(check=>check.cwd+": "+check.command)].join("\n");
}
async function refreshSetup() {
  id("refreshSetup").disabled=true;id("setupSummary").textContent="Reading project settings…";
  id("setupItems").replaceChildren();id("setupMap").textContent="";
  try {renderSetupReport(await api("/projects/"+setupProjectId+"/setup"));}
  catch(error){id("setupSummary").textContent="Setup could not be inspected. "+error.message;}
  finally {id("refreshSetup").disabled=false;id("investigateSetup").disabled=!!busy();}
}
async function openSetup() {setupProjectId=projectId;id("setupDialog").showModal();await refreshSetup();}

function humanBytes(bytes=0) { return bytes<1024?bytes+" B":bytes<1048576?(bytes/1024).toFixed(1)+" KiB":(bytes/1048576).toFixed(1)+" MiB"; }
function duration(seconds=0) { return seconds<60?Math.floor(seconds)+"s":Math.floor(seconds/60)+"m "+Math.floor(seconds%60)+"s"; }
async function copyText(text) {
  try { if(!navigator.clipboard?.writeText)throw new Error(); await navigator.clipboard.writeText(text); }
  catch(_) { const field=node("textarea","clipboard-fallback");field.value=text;document.body.append(field);field.select();const ok=document.execCommand("copy");field.remove();if(!ok)throw new Error("Clipboard access is unavailable. Select the text and use your system Copy command."); }
  toast("Copied to clipboard.");
}
async function downloadBlob(path) {
  const response=await fetch("/api"+path,{headers:{"X-Sparkle-Token":accessToken}});
  if(!response.ok){let data;try{data=await response.json();}catch(_){data={};}throw new Error(data.error||"Download failed.");}
  return response.blob();
}
async function saveDownload(path,name) {
  const blob=await downloadBlob(path),url=URL.createObjectURL(blob),link=node("a");
  link.href=url;link.download=name;document.body.append(link);link.click();link.remove();
  setTimeout(()=>URL.revokeObjectURL(url),30000);toast("Download sent to your browser. Check its Downloads list.");
}
function renderFileButtons() {
  const chosen=!!selectedFile,working=!!busy()||transferBusy;
  id("copyFileText").disabled=!chosen||!fileData||fileData.binary;
  id("copyFilePath").disabled=!chosen;id("downloadFile").disabled=!chosen;
  id("duplicateFile").disabled=!chosen||working;
  ["importFiles","importFolder","downloadProject","exportFolder"].forEach(x=>id(x).disabled=working);
}
function renderSupervision() {
  const working=!!busy(),paused=currentRun?.pause_requested;
  id("pauseButton").hidden=!working;id("pauseButton").textContent=paused?"Resume":"Pause";
  id("pauseButton").disabled=!working||currentRun?.status==="stopping";
  id("monitorPause").disabled=!working||currentRun?.status==="stopping";id("monitorPause").textContent=paused?"Resume":"Pause";
  id("monitorStop").disabled=!working||currentRun?.status==="stopping";
  id("reviewEdits").disabled=working||id("taskMode").value==="ask";
  id("headerRunStatus").textContent=friendly(currentRun?.status||currentSession?.status);
  id("monitorLive").textContent=working?"Live":"";
  id("supervisionStrip").hidden=!working;
  id("currentAction").textContent=currentRun?.current_action||"Ready";
  id("elapsedTime").textContent=duration(currentRun?.elapsed_seconds);
  renderFileButtons();
}
function eventDescription(e) {
  if(e.kind==="model_retry")return "Reconnecting · attempt "+e.attempt+" in "+e.delay+"s · "+e.reason;
  if(e.kind==="verification_start")return "Running a project check";
  if(e.kind==="action_context")return e.purpose;
  if(e.kind==="check_revised")return "Corrected a test: "+e.label;
  const labels={model_start:"Model request started",model_end:"Model response received",tool_start:"Started "+(e.tool||"tool"),tool_end:(e.ok?"Completed ":"Failed ")+(e.tool||"tool"),command_start:"Command started",command_end:e.cancelled?"Command stopped":"Command exited "+e.exit_code,approval_requested:"Approval needed",approval_decision:e.allowed?"You approved this action":"You denied this action",paused:"Paused by you",resumed:"Resumed by you",pause_requested:"Pause requested",stop_requested:"Stop requested",finished:"Task finished",message:e.text};
  return labels[e.kind]||e.text||e.kind;
}
function renderMonitor() {
  const active=busy(),session=currentSession,events=runEvents.length?runEvents:(session?.events||[]);
  id("monitorAction").textContent=currentRun?.current_action||(session?"Saved task: "+session.goal:"No active task");
  id("monitorStatus").textContent=friendly(currentRun?.status||session?.status);
  id("monitorStatus").className="status-badge "+(currentRun?.status||session?.status||"");
  id("monitorHeartbeat").textContent=currentRun?"Last event "+new Date(currentRun.last_activity||currentRun.created).toLocaleTimeString()+" · "+(currentRun.mode==="demo"?"Scripted offline demo":appState?.settings.model||"Nemotron")+(currentRun.log_truncated?" · saved log reached its size limit":""):session?"Saved activity from this device. No task is running.":"Start a task to see every operation here.";
  id("monitorElapsed").textContent=currentRun?duration(currentRun.elapsed_seconds):events.length?duration(events[events.length-1].elapsed):"—";
  id("monitorCalls").textContent=session?.usage?.calls??"—";
  id("monitorFiles").textContent=session?.changed_files?.length||0;
  const checks=(session?.checks||[]).filter(c=>c.active!==false);id("monitorChecks").textContent=(session?.proof?.passed??checks.filter(c=>c.ok).length)+" / "+(session?.proof?.total??checks.length);
  const plan=session?.plan||[],completed=plan.filter(p=>p.status==="completed").length;
  id("planProgress").textContent=plan.length?"Plan: "+completed+" of "+plan.length+" steps complete":"No plan recorded yet.";
  id("planProgressBar").hidden=!plan.length;id("planProgressBar").max=plan.length||1;id("planProgressBar").value=completed;
  id("eventTimeline").replaceChildren();
  const timeline=events.filter(e=>e.kind!=="command_output"&&e.kind!=="message").slice(-100).reverse();
  if(!timeline.length)id("eventTimeline").append(emptyPanel("Watch the work","Model calls, file operations, command results and your decisions appear here."));
  timeline.forEach(e=>{const row=node("div","timeline-event "+e.kind),time=node("time","",new Date(e.at).toLocaleTimeString());row.append(time,node("strong","",eventDescription(e)));const detail=e.path||e.command||e.error||e.summary||(e.kind==="model_start"?"Call "+e.call+" · "+e.model:"");if(detail)row.append(node("span","",detail));id("eventTimeline").append(row);});
  const output=events.filter(e=>["command_start","command_output","command_end"].includes(e.kind)).map(e=>e.kind==="command_start"?"\n$ "+e.command+"\n":e.kind==="command_output"?e.output:"\n[exit "+e.exit_code+(e.cancelled?", stopped":"")+"]\n").join("");
  if(output!==lastConsoleKey){id("liveConsole").textContent=output||"Command output will appear here as it is emitted.";lastConsoleKey=output;if(id("followConsole").checked)id("liveConsole").scrollTop=id("liveConsole").scrollHeight;}
  id("downloadReport").disabled=!session;id("downloadLog").disabled=!session;
  id("monitorAttention").hidden=!(active&&currentRun?.approval);
  renderSupervision();
}
async function togglePause() {
  if(!busy())return;
  currentRun=await api("/runs/"+currentRun.id+(currentRun.pause_requested?"/resume":"/pause"),{});
  renderControls();renderMonitor();schedulePoll(20);
}
async function chooseFolder(inputId) { const result=await api("/select-folder",{});if(result.path)id(inputId).value=result.path; }
async function uploadSelection(selection) {
  if(busy()||transferBusy)throw new Error("Finish or stop the current task before importing files.");
  const items=Array.from(selection);if(!items.length)return;
  if(items.length>500)throw new Error("Import up to 500 files at a time, or open an existing device folder as a project.");
  if(items.reduce((n,f)=>n+f.size,0)>100*1024*1024)throw new Error("Import up to 100 MiB at a time, or open the device folder as a project.");
  transferBusy=true;cancelTransfer=false;id("transferStatus").hidden=false;id("transferErrors").hidden=true;id("cancelImport").hidden=false;renderControls();
  const destinationProject=projectId,errors=[];let done=0,copied=0;
  try {
    for(const file of items){
      if(cancelTransfer)break;
      const path=file.webkitRelativePath||file.name;
      id("transferText").textContent="Importing "+(done+1)+" / "+items.length+" · "+path;
      try {
        if(file.size>20*1024*1024)throw new Error("File exceeds 20 MiB.");
        const encoded=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(",")[1]);reader.onerror=()=>reject(new Error("Could not read this file."));reader.readAsDataURL(file);});
        if(cancelTransfer)break;
        const result=await api("/projects/"+destinationProject+"/import",{path,data:encoded});
        copied++;if(result.renamed)errors.push(path+" → "+result.path+" (original preserved)");
      }catch(error){errors.push(path+": "+error.message);}
      done++;
    }
    id("transferText").textContent=(cancelTransfer?"Import stopped. ":"Import finished. ")+copied+" files copied; "+(items.length-done)+" not processed.";
    id("transferErrors").textContent=errors.join("\n");id("transferErrors").hidden=!errors.length;
  } finally {transferBusy=false;id("cancelImport").hidden=true;id("uploadFiles").value="";id("uploadFolder").value="";await loadFiles();renderControls();}
}
function openStorageSettings() {id("storagePath").value=appState.storage.path;id("projectsPath").value=appState.storage.projects_path;id("storageMigration").hidden=!appState.storage.migration;id("storageMigration").textContent=appState.storage.migration?.message||"";id("storageResult").hidden=true;id("storageDialog").showModal();}
function updateReconnectSelection() {
  const project=appState.projects.find(p=>p.id===id("missingProjectSelect").value);
  id("missingProjectPath").textContent=project?.path||"";
  id("reconnectPath").value=project?.path||"";
  id("reconnectResult").hidden=true;
}
function openReconnect(selected) {
  if(busy()||transferBusy)return;
  const missing=appState.projects.filter(p=>p.available===false);
  if(!missing.length)return;
  id("missingProjectSelect").replaceChildren(...missing.map(p=>{const option=node("option","",p.name);option.value=p.id;return option;}));
  id("missingProjectSelect").value=missing.some(p=>p.id===selected)?selected:missing[0].id;
  updateReconnectSelection();id("reconnectDialog").showModal();
}
async function reconnectProject() {
  if(busy()||transferBusy)return;
  const selected=id("missingProjectSelect").value;
  id("saveReconnect").disabled=true;id("missingProjectSelect").disabled=true;id("browseReconnect").disabled=true;
  id("reconnectResult").hidden=false;id("reconnectResult").textContent="Checking the folder…";
  try {
    const project=await api("/projects/"+selected+"/reconnect",{path:id("reconnectPath").value});
    await refreshState();await selectProject(project.id);id("reconnectDialog").close();toast("Project reconnected. Your files are ready to open.");
  } catch(error) {id("reconnectResult").textContent=error.message;}
  finally {id("saveReconnect").disabled=false;id("missingProjectSelect").disabled=false;id("browseReconnect").disabled=false;}
}

id("trackTask").onclick=id("showMonitor").onclick=()=>changeView("monitor");
id("reviewPending").onclick=()=>{changeView("build");id("approvalCard").scrollIntoView({block:"nearest"});};
id("pauseButton").onclick=id("monitorPause").onclick=()=>action(togglePause);
id("monitorStop").onclick=()=>id("stopButton").click();
id("copyConsole").onclick=()=>action(()=>copyText(id("liveConsole").textContent));
id("downloadReport").onclick=()=>action(()=>saveDownload("/projects/"+projectId+"/sessions/"+currentSession.id+"/report","task-report-"+currentSession.id+".md"));
id("downloadLog").onclick=()=>action(()=>saveDownload("/projects/"+projectId+"/sessions/"+currentSession.id+"/logs","task-log-"+currentSession.id+".jsonl"));
id("openProjectFolder").onclick=()=>action(()=>api("/open-folder",{project_id:projectId}));
id("fileSearch").oninput=renderFileList;
id("copyFilePath").onclick=()=>action(()=>copyText(appState.projects.find(p=>p.id===projectId).path+"/"+selectedFile));
id("copyFileText").onclick=()=>action(async()=>copyText(await (await downloadBlob("/projects/"+projectId+"/download?path="+encodeURIComponent(selectedFile))).text()));
id("downloadFile").onclick=()=>action(()=>saveDownload("/projects/"+projectId+"/download?path="+encodeURIComponent(selectedFile),selectedFile.split("/").pop()));
id("downloadProject").onclick=()=>action(async()=>{id("downloadProject").disabled=true;try{await saveDownload("/projects/"+projectId+"/download-project","project-"+projectId+".zip");}finally{renderFileButtons();}});
id("importFiles").onclick=()=>id("uploadFiles").click();id("importFolder").onclick=()=>id("uploadFolder").click();
id("uploadFiles").onchange=e=>action(()=>uploadSelection(e.target.files));id("uploadFolder").onchange=e=>action(()=>uploadSelection(e.target.files));
id("cancelImport").onclick=()=>{cancelTransfer=true;id("transferText").textContent="Stopping after the current file…";};
id("dropZone").onclick=()=>id("uploadFiles").click();
id("dropZone").onkeydown=e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();id("uploadFiles").click();}};
id("filesView").ondragover=e=>{e.preventDefault();id("dropZone").classList.add("dragging");};
id("filesView").ondragleave=()=>id("dropZone").classList.remove("dragging");
id("filesView").ondrop=e=>{e.preventDefault();id("dropZone").classList.remove("dragging");action(()=>uploadSelection(e.dataTransfer.files));};
id("filesView").onpaste=e=>{if(e.clipboardData?.files.length){e.preventDefault();action(()=>uploadSelection(e.clipboardData.files));}};
id("duplicateFile").onclick=()=>{const dot=selectedFile.lastIndexOf("."),slash=selectedFile.lastIndexOf("/");id("duplicatePath").value=dot>slash?selectedFile.slice(0,dot)+"-copy"+selectedFile.slice(dot):selectedFile+"-copy";id("duplicateDialog").showModal();};
id("duplicateForm").onsubmit=e=>{e.preventDefault();action(async()=>{const result=await api("/projects/"+projectId+"/duplicate",{source:selectedFile,destination:id("duplicatePath").value});id("duplicateDialog").close();await loadFiles();await openFile(result.path);toast("Created "+result.path);});};
id("exportFolder").onclick=()=>{id("exportForm").reset();id("exportResult").hidden=true;id("exportDialog").showModal();};
id("browseExport").onclick=()=>action(()=>chooseFolder("exportPath"));
id("exportForm").onsubmit=e=>{e.preventDefault();action(async()=>{id("saveExport").disabled=true;id("exportResult").hidden=false;id("exportResult").textContent="Copying project…";try{const result=await api("/projects/"+projectId+"/export-folder",{path:id("exportPath").value});id("exportResult").textContent=result.files+" files copied to "+result.path;}catch(error){id("exportResult").textContent=error.message;}finally{id("saveExport").disabled=false;}});};
id("storageButton").onclick=openStorageSettings;
id("findProjectFolder").onclick=()=>openReconnect();
id("missingProjectSelect").onchange=updateReconnectSelection;
id("browseReconnect").onclick=()=>action(()=>chooseFolder("reconnectPath"));
id("reconnectForm").onsubmit=e=>{e.preventDefault();action(reconnectProject);};
id("browseStorage").onclick=()=>action(()=>chooseFolder("storagePath"));
id("openProjectsDirectory").onclick=()=>action(()=>api("/open-folder",{target:"projects"}));
id("openStorage").onclick=()=>action(()=>api("/open-folder",{}));
id("copyStoragePath").onclick=()=>action(()=>copyText(appState.storage.path));
id("saveStorage").onclick=()=>action(async()=>{id("saveStorage").disabled=true;id("storageResult").hidden=false;id("storageResult").textContent="Copying data and switching folders…";try{const result=await api("/storage",{path:id("storagePath").value});await refreshState();id("storageResult").textContent=result.message||"Already using this folder.";id("storagePath").value=appState.storage.path;id("projectsPath").value=appState.storage.projects_path;await loadFiles();}catch(error){id("storageResult").textContent=error.message;}finally{id("saveStorage").disabled=false;}});

document.querySelectorAll("[data-view]").forEach(b=>b.onclick=()=>changeView(b.dataset.view));
document.querySelectorAll("[data-tab]").forEach(b=>b.onclick=()=>setTab(b.dataset.tab));
document.querySelectorAll("[data-close]").forEach(b=>b.onclick=()=>id(b.dataset.close).close());
document.querySelectorAll(".suggestion").forEach(b=>b.onclick=()=>{id("taskMode").value=b.dataset.mode||"build";renderControls();id("goal").value=b.dataset.prompt;id("goal").focus();});
id("briefButton").onclick=()=>action(openProjectBrief);
id("briefForm").onsubmit=e=>action(()=>saveProjectBrief(e));
id("setupButton").onclick=()=>action(openSetup);
id("refreshSetup").onclick=()=>action(refreshSetup);
id("setupConnection").onclick=()=>{id("setupDialog").close();openSettings();};
id("investigateSetup").onclick=()=>{if(busy())return;id("setupDialog").close();followup("Inspect this project's setup. Identify missing tools or dependencies, explain what is needed in simple words, and ask before running installation commands. Verify the setup with real checks where possible.","build");};
id("experienceButton").onclick=()=>action(async()=>{await api("/experience",{experience:appState.experience==="advanced"?"simple":"advanced"});await refreshState();});
id("taskMode").onchange=renderControls;
id("showApiKey").onclick=()=>{const show=id("apiKey").type==="password";id("apiKey").type=show?"text":"password";id("showApiKey").textContent=show?"Hide":"Show";id("showApiKey").setAttribute("aria-pressed",String(show));};
id("clearApiKey").onclick=()=>action(async()=>{await api("/settings",{base_url:id("baseUrl").value.trim(),clear_key:true});await refreshState();id("apiKey").value="";id("keyHint").textContent="Key removed for this app session";id("clearApiKey").disabled=true;});
id("removeRunCaps").onclick=()=>{["maxSteps","maxSeconds","maxTotalTokens","commandTimeout"].forEach(name=>id(name).value="");id("capsHint").textContent="All run caps cleared. Click Save connection to apply.";};
id("newTask").onclick=()=>action(newTask);
id("taskForm").onsubmit=e=>action(()=>startTask(e));
id("demoButton").onclick=()=>action(startDemo);
id("stopButton").onclick=()=>action(async()=>{if(currentRun){currentRun=await api("/runs/"+currentRun.id+"/stop",{});renderControls();schedulePoll(20);}});
id("allowCommand").onclick=()=>action(()=>answerApproval(true)); id("denyCommand").onclick=()=>action(()=>answerApproval(false));
id("toggleChecks").onclick=()=>{id("verificationFields").hidden=!id("verificationFields").hidden;if(!id("verificationFields").hidden)id("verifyCommands").focus();};
id("settingsButton").onclick=openSettings; id("modelButton").onclick=openSettings;
id("settingsForm").onsubmit=e=>{e.preventDefault();action(()=>saveSettings());}; id("testConnection").onclick=()=>action(()=>saveSettings(true));
id("connectionType").onchange=()=>{if(id("connectionType").value==="nvidia"){id("baseUrl").value="https://integrate.api.nvidia.com/v1";id("modelId").value="nvidia/nemotron-3-super-120b-a12b";}else{id("baseUrl").value="http://127.0.0.1:8000/v1";id("modelId").value="";}id("apiKey").value="";id("apiKey").placeholder=id("connectionType").value==="nvidia"?"Paste your NVIDIA key here":"Optional for an unauthenticated local server";};
id("executionMode").onchange=()=>id("executionNote").textContent=id("executionMode").value==="docker"?"Requires Docker and the supplied development image. Container networking is disabled by default.":"Local commands use your computer's permissions. You approve each agent-proposed command.";
id("projectSelect").onchange=()=>action(()=>selectProject(id("projectSelect").value));
id("addProject").onclick=()=>{id("projectForm").reset();id("projectError").hidden=true;id("projectDialog").showModal();};
id("browseFolder").onclick=()=>action(async()=>{id("browseFolder").disabled=true;try{const result=await api("/select-folder",{});if(result.path){id("projectFolder").value=result.path;if(!id("projectName").value)id("projectName").value=result.path.split(/[\\/]/).pop();}}finally{id("browseFolder").disabled=false;}});
id("projectForm").onsubmit=e=>{e.preventDefault();action(async()=>{id("saveProject").disabled=true;try{const project=await api("/projects",{name:id("projectName").value,path:id("projectFolder").value});await refreshState();await selectProject(project.id);id("projectDialog").close();}catch(error){id("projectError").hidden=false;id("projectError").textContent=error.message;}finally{id("saveProject").disabled=false;}});};
id("refreshFiles").onclick=()=>action(loadFiles);
id("undoButton").onclick=()=>action(async()=>{const result=await api("/projects/"+projectId+"/sessions/"+currentSession.id+"/undo");id("undoFiles").replaceChildren(...result.paths.map(p=>node("li","",p)));id("undoDialog").showModal();});
id("confirmUndo").onclick=()=>action(async()=>{await api("/projects/"+projectId+"/sessions/"+currentSession.id+"/undo",{confirm:true});id("undoDialog").close();await loadSession(currentSession.id);await loadFiles();await loadChanges();toast("File-tool edits were undone.");});
id("menuButton").onclick=()=>document.body.classList.toggle("sidebar-open"); id("navBackdrop").onclick=()=>document.body.classList.remove("sidebar-open");
id("detailsButton").onclick=()=>document.body.classList.toggle("details-open"); id("closeDetails").onclick=()=>document.body.classList.remove("details-open");
id("quitButton").onclick=()=>id("quitDialog").showModal();
id("confirmQuit").onclick=()=>action(async()=>{await api("/quit",{});clearTimeout(pollTimer);id("quitDialog").close();id("app").replaceChildren(emptyPanel("Workspace closed","Your work is saved. Use the desktop launcher to open the app again."));});
document.addEventListener("keydown",e=>{if((e.ctrlKey||e.metaKey)&&e.key==="Enter"&&!document.querySelector("dialog[open]")){e.preventDefault();id("taskForm").requestSubmit();}if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==="k"){e.preventDefault();action(newTask);}});
document.querySelectorAll("dialog").forEach(dialog=>dialog.addEventListener("click",e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close();}}));

(async()=>{try{await refreshState();await Promise.all([loadFiles(),loadHistory()]);renderSession(null);if(currentRun)schedulePoll(20);}catch(error){id("app").replaceChildren(emptyPanel("Open the app from its launcher",error.message));}})();
