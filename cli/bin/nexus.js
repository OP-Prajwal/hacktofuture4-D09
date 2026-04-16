#!/usr/bin/env node

import { Command } from 'commander';
import axios from 'axios';
import chalk from 'chalk';
import path from 'path';
import fs from 'fs';
import ora from 'ora';
import crypto from 'crypto';

const program = new Command();
const NEXUS_DIR = '.nexus';
const CONFIG_FILE = 'config.json';

// Resolve the backend URL: config > env > default
function getBackendUrl(config) {
  return config?.server || process.env.NEXUS_BACKEND_URL || 'http://localhost:8000';
}

const IGNORED_DIRS = new Set([
  '.git', 'node_modules', '.nexus', '__pycache__',
  '.venv', 'venv', 'dist', 'build', '.next', 'coverage', '.cache',
  '.gitnexus', '.claude'
]);

const BINARY_EXTENSIONS = new Set([
  '.pyc', '.pyo', '.pyd', '.class', '.o', '.obj', '.a', '.lib',
  '.so', '.dll', '.exe', '.zip', '.tar', '.gz', '.bz2', '.xz',
  '.7z', '.rar', '.whl', '.egg',
  '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.webp',
  '.tiff', '.ttf', '.otf', '.woff', '.woff2', '.eot',
  '.mp3', '.mp4', '.wav', '.ogg', '.avi', '.mov', '.mkv', '.webm',
  '.db', '.sqlite', '.sqlite3', '.parquet', '.pkl', '.npy', '.npz',
  '.bin', '.dat', '.img', '.iso', '.pdf', '.lock', '.svg'
]);

// ─── Config helpers ───────────────────────────────────────────────────────────

function getConfigPath() {
  return path.join(process.cwd(), NEXUS_DIR, CONFIG_FILE);
}
function writeConfig(config) {
  const dirPath = path.join(process.cwd(), NEXUS_DIR);
  if (!fs.existsSync(dirPath)) fs.mkdirSync(dirPath);
  fs.writeFileSync(getConfigPath(), JSON.stringify(config, null, 2));
}
function readConfig() {
  if (!fs.existsSync(getConfigPath())) {
    console.error(chalk.red('Fatal: Not a NEXUS repo. Run `nexus init` first.'));
    process.exit(1);
  }
  return JSON.parse(fs.readFileSync(getConfigPath(), 'utf-8'));
}

// ─── File helpers ─────────────────────────────────────────────────────────────

function isTextFile(ext) {
  return !BINARY_EXTENSIONS.has(ext.toLowerCase());
}

function walkDirectory(dir, basePath, acc = []) {
  for (const entry of fs.readdirSync(dir)) {
    if (IGNORED_DIRS.has(entry)) continue;
    const fullPath = path.join(dir, entry);
    const stat = fs.statSync(fullPath);
    if (stat.isDirectory()) {
      walkDirectory(fullPath, basePath, acc);
    } else {
      const ext = path.extname(entry);
      if (!isTextFile(ext)) continue;
      acc.push({
        path: path.relative(basePath, fullPath).replace(/\\/g, '/'),
        name: entry,
        size: stat.size,
        extension: ext,
        absolutePath: fullPath
      });
    }
  }
  return acc;
}

/**
 * SHA-256 hash a file by streaming it through the hash function.
 * Never loads the entire file into memory.
 */
function hashFileStream(absolutePath) {
  return new Promise((resolve, reject) => {
    const hash = crypto.createHash('sha256');
    fs.createReadStream(absolutePath)
      .on('data', chunk => hash.update(chunk))
      .on('end', () => resolve(hash.digest('hex')))
      .on('error', reject);
  });
}

/**
 * Upload a single file by streaming it directly as raw bytes.
 * 
 * Uses HTTP chunked-transfer-encoding — the file is never fully loaded
 * into memory on the client side. The read stream is piped straight
 * from disk into the HTTP connection.
 */
async function streamFileToBackend(api, file) {
  const readStream = fs.createReadStream(file.absolutePath, {
    highWaterMark: 64 * 1024  // 64KB read buffer
  });

  await axios.post(
    `${api}/blob/${file.hash}`,
    readStream,
    {
      headers: {
        'Content-Type': 'application/octet-stream',
        'Transfer-Encoding': 'chunked',
        'X-Nexus-Meta': JSON.stringify({
          name:       file.name,
          extension:  file.extension,
          size:       file.size
        })
      },
      maxBodyLength: Infinity,
      maxContentLength: Infinity,
      timeout: 120_000   // 2 min per file — safe for large files
    }
  );
}

// ─── Commands ─────────────────────────────────────────────────────────────────

program
  .name('nexus')
  .description('NEXUS-X Developer Intelligence CLI')
  .version('1.0.0');

program
  .command('init')
  .description('Initialize a NEXUS-X repository in the current directory')
  .action(() => {
    const dirPath = path.join(process.cwd(), NEXUS_DIR);
    if (fs.existsSync(dirPath)) {
      console.log(chalk.yellow('Reinitialized existing NEXUS repository in ' + dirPath));
      return;
    }
    writeConfig({});
    console.log(chalk.green(`Initialized empty NEXUS repository in ${dirPath}`));
  });

program
  .command('connect')
  .description('Connect this project to a Nexus-X server')
  .argument('<server>', 'Nexus-X backend URL (e.g. https://nexus-x.yourcompany.com or http://localhost:8000)')
  .argument('<remote>', 'Workspace/Project code (e.g. mohit/my-project-abc123)')
  .action((server, remote) => {
    if (!remote.includes('/')) {
      console.error(chalk.red('Invalid format. Expected <workspace>/<project>'));
      process.exit(1);
    }

    // Clean trailing slash
    server = server.replace(/\/+$/, '');

    // Init .nexus if not already present
    const dirPath = path.join(process.cwd(), NEXUS_DIR);
    if (!fs.existsSync(dirPath)) fs.mkdirSync(dirPath);

    const config = { server, remote };
    writeConfig(config);

    console.log(chalk.cyan('\n🔗 NEXUS-X Connection Established\n'));
    console.log(chalk.white(`  Server:    ${chalk.bold(server)}`));
    console.log(chalk.white(`  Project:   ${chalk.bold(remote)}`));
    console.log(chalk.white(`  Config:    ${chalk.gray(getConfigPath())}\n`));
    console.log(chalk.green('✓ Ready. Run `nexus push` to sync your codebase.\n'));
  });

// Keep legacy `remote` as alias
program
  .command('remote')
  .description('(Legacy) Set the remote origin — prefer `nexus connect`')
  .argument('<url>', 'Remote short code (e.g. acme/my-project-abc123)')
  .action((url) => {
    if (!url.includes('/')) {
      console.error(chalk.red('Invalid format. Expected <workspace>/<project>'));
      process.exit(1);
    }
    const config = readConfig();
    config.remote = url;
    writeConfig(config);
    console.log(chalk.green(`Added remote: ${chalk.bold(url)}`));
  });

program
  .command('push')
  .description('Stream repository files to NEXUS-X backend via binary HTTP streaming')
  .action(async () => {
    const config = readConfig();
    if (!config.remote) {
      console.error(chalk.red('Fatal: No remote set. Run `nexus remote <workspace>/<project>`'));
      process.exit(1);
    }

    const [workspace, project] = config.remote.split('/');
    const currentDir = process.cwd();
    const BACKEND_URL = getBackendUrl(config);
    const api = `${BACKEND_URL}/api/repo/${workspace}/${project}`;

    // ── Step 1: Walk and stream-hash ─────────────────────────────────────────
    let scanSpinner = ora('Scanning repository…').start();
    const allFiles = walkDirectory(currentDir, currentDir);

    if (allFiles.length === 0) {
      scanSpinner.fail(chalk.yellow('No text files found.'));
      return;
    }

    scanSpinner.text = `Hashing ${allFiles.length} files…`;
    const fileRecords = await Promise.all(
      allFiles.map(async f => ({
        ...f,
        hash: await hashFileStream(f.absolutePath)
      }))
    );
    scanSpinner.succeed(chalk.gray(`Scanned & hashed ${fileRecords.length} files.`));

    // ── Step 2: Preflight (delta check) ─────────────────────────────────────
    const preSpinner = ora('Negotiating delta with remote…').start();
    let missingHashes;
    try {
      const { data } = await axios.post(`${api}/preflight`, {
        hashes: fileRecords.map(f => f.hash)
      });
      missingHashes = new Set(data.missing);
    } catch (err) {
      preSpinner.fail(chalk.red('Preflight failed.'));
      logError(err); return;
    }

    const toUpload = fileRecords.filter(f => missingHashes.has(f.hash));
    const skipped  = fileRecords.length - toUpload.length;
    preSpinner.succeed(chalk.gray(
      `Delta: ${toUpload.length} new blob(s), ${skipped} already stored.`
    ));

    if (toUpload.length === 0) {
      console.log(chalk.green('\n✓ Everything up to date.\n'));
    } else {
      // ── Step 3: Stream each new blob ───────────────────────────────────────
      console.log(chalk.cyan(`\nStreaming ${toUpload.length} file(s) to remote…\n`));

      for (let i = 0; i < toUpload.length; i++) {
        const file = toUpload[i];
        const label = `[${i + 1}/${toUpload.length}] ${chalk.bold(file.path)}`;
        const upSpinner = ora(label).start();
        try {
          await streamFileToBackend(api, file);
          upSpinner.succeed(
            `${label}  ${chalk.gray(`sha256:${file.hash.slice(0, 8)}…  ${(file.size / 1024).toFixed(1)} KB`)}`
          );
        } catch (err) {
          upSpinner.fail(`${label}  ${chalk.red('stream failed')}`);
          logError(err);
        }
      }
    }

    // ── Step 4: Commit snapshot ──────────────────────────────────────────────
    const commitSpinner = ora('Committing snapshot…').start();
    try {
      const manifest = fileRecords.map(f => ({
        path: f.path, hash: f.hash, size: f.size, extension: f.extension
      }));
      const { data } = await axios.post(`${api}/commit`, {
        manifest,
        metadata: {
          push_source:  currentDir,
          local_path:   currentDir,
          total_files:  fileRecords.length,
          new_blobs:    toUpload.length,
          skipped_blobs: skipped
        }
      }, { timeout: 15_000 });

      commitSpinner.succeed(
        chalk.green('Committed  ') +
        chalk.gray(`id: ${data.commit_id}  ·  ${data.total_files} files`)
      );
    } catch (err) {
      commitSpinner.fail(chalk.red('Commit failed.'));
      logError(err);
    }

    console.log(chalk.green('\n✓ Push complete.\n'));
  });

program
  .command('ci [args...]')
  .description('Wrap a build process and automatically sync the codebase graph upon success')
  .action((args) => {
    if (args.length === 0) {
      console.error(chalk.red('Fatal: No build command provided. Usage: nexus ci <command> (e.g. nexus ci npm run build)'));
      process.exit(1);
    }

    const { spawnSync } = require('child_process');
    const cmdStr = args.join(' ');

    console.log(chalk.cyan(`\n🚀 [NEXUS-X Pipeline] Executing Build Command: ${chalk.bold(cmdStr)}\n`));

    // Spawn the wrapped build command
    const result = spawnSync(args[0], args.slice(1), { stdio: 'inherit', shell: true });

    if (result.status !== 0) {
      console.error(chalk.red(`\n❌ [NEXUS-X Pipeline] Build failed (exit code ${result.status}). Graph synchronization aborted.`));
      process.exit(result.status || 1);
    }

    console.log(chalk.green(`\n✓ [NEXUS-X Pipeline] Build succeeded! Synchronizing graph with Nexus backend...\n`));

    // Automatically trigger 'nexus push' upon build success
    const pushResult = spawnSync('node', [__filename, 'push'], { stdio: 'inherit', shell: true });

    if (pushResult.status !== 0) {
      console.error(chalk.red('\n❌ [NEXUS-X Pipeline] Graph synchronization failed.'));
      process.exit(pushResult.status || 1);
    }
  });

// ─── Live Telemetry Agent ─────────────────────────────────────────────────────

program
  .command('run [args...]')
  .description('Run a production process and stream all logs/errors live to Nexus-X')
  .action(async (args) => {
    if (args.length === 0) {
      console.error(chalk.red('Fatal: No command provided. Usage: nexus run <command> (e.g. nexus run node server.js)'));
      process.exit(1);
    }

    const config = readConfig();
    if (!config.remote) {
      console.error(chalk.red('Fatal: No remote set. Run `nexus connect <server> <workspace>/<project>` first.'));
      process.exit(1);
    }

    const [workspace, project] = config.remote.split('/');
    const BACKEND_URL = getBackendUrl(config);
    const wsUrl = BACKEND_URL.replace(/^http/, 'ws') + `/ws/runner/${workspace}/${project}`;
    const cmdStr = args.join(' ');

    console.log(chalk.cyan('\n📡 NEXUS-X Live Telemetry Agent\n'));
    console.log(chalk.white(`  Server:    ${chalk.bold(BACKEND_URL)}`));
    console.log(chalk.white(`  Project:   ${chalk.bold(config.remote)}`));
    console.log(chalk.white(`  Command:   ${chalk.bold(cmdStr)}`));
    console.log(chalk.white(`  WebSocket: ${chalk.gray(wsUrl)}\n`));

    // ── Connect WebSocket to backend ──
    let ws = null;
    let wsConnected = false;

    try {
      const WebSocket = (await import('ws')).default;
      ws = new WebSocket(wsUrl);

      await new Promise((resolve, reject) => {
        ws.on('open', () => {
          wsConnected = true;
          console.log(chalk.green('✓ Connected to Nexus-X backend. Streaming logs...\n'));
          console.log(chalk.gray('─'.repeat(60) + '\n'));
          resolve();
        });
        ws.on('error', (err) => {
          console.log(chalk.yellow(`⚠ WebSocket connection failed: ${err.message}`));
          console.log(chalk.yellow('  Logs will be buffered and sent via HTTP fallback.\n'));
          resolve(); // Don't block — run the process anyway
        });
        // Timeout after 5s
        setTimeout(() => {
          if (!wsConnected) {
            console.log(chalk.yellow('⚠ WebSocket connection timed out. Running in offline mode.\n'));
            resolve();
          }
        }, 5000);
      });
    } catch {
      console.log(chalk.yellow('⚠ WebSocket module not available. Running in offline mode.\n'));
    }

    // Helper to send a log line to the backend
    function sendLog(line, stream = 'stdout') {
      if (ws && wsConnected && ws.readyState === 1) {
        ws.send(JSON.stringify({ type: 'log', line, stream }));
      }
    }

    function sendExit(code) {
      if (ws && wsConnected && ws.readyState === 1) {
        ws.send(JSON.stringify({ type: 'exit', code }));
        setTimeout(() => ws.close(), 500);
      }
    }

    // ── Spawn the wrapped process ──
    const { spawn } = require('child_process');
    const child = spawn(args[0], args.slice(1), {
      shell: true,
      cwd: process.cwd(),
      env: { ...process.env, NEXUS_TELEMETRY: 'active' }
    });

    // Buffer for HTTP fallback
    const logBuffer = [];

    child.stdout.on('data', (data) => {
      const text = data.toString();
      process.stdout.write(text); // Mirror to local terminal
      text.split('\n').filter(Boolean).forEach(line => {
        sendLog(line, 'stdout');
        logBuffer.push({ line, stream: 'stdout', ts: Date.now() });
      });
    });

    child.stderr.on('data', (data) => {
      const text = data.toString();
      process.stderr.write(text); // Mirror to local terminal
      text.split('\n').filter(Boolean).forEach(line => {
        sendLog(line, 'stderr');
        logBuffer.push({ line, stream: 'stderr', ts: Date.now() });
      });
    });

    child.on('close', async (code) => {
      console.log(chalk.gray('\n' + '─'.repeat(60)));
      console.log(
        code === 0
          ? chalk.green(`\n✓ Process exited cleanly (code 0)`)
          : chalk.red(`\n✗ Process exited with code ${code}`)
      );

      sendExit(code);

      // HTTP fallback: if WebSocket wasn't connected, POST the logs
      if (!wsConnected && logBuffer.length > 0) {
        console.log(chalk.cyan('\n📤 Uploading buffered logs via HTTP...'));
        try {
          await axios.post(
            `${BACKEND_URL}/api/repo/${workspace}/${project}/logs`,
            { logs: logBuffer, exit_code: code },
            { timeout: 30000 }
          );
          console.log(chalk.green(`✓ ${logBuffer.length} log lines uploaded.\n`));
        } catch (err) {
          console.log(chalk.yellow(`⚠ Log upload failed: ${err.message}\n`));
        }
      }

      console.log(chalk.cyan(`📊 View live in dashboard: ${BACKEND_URL.replace(/:\d+$/, ':5173')}\n`));
      process.exit(code);
    });

    // Handle user Ctrl+C
    process.on('SIGINT', () => {
      child.kill('SIGINT');
    });
    process.on('SIGTERM', () => {
      child.kill('SIGTERM');
    });
  });

program
  .command('analyze')
  .description('Build the Code Intelligence Graph from the latest pushed snapshot')
  .action(async () => {
    const config = readConfig();
    if (!config.remote) {
      console.error(chalk.red('Fatal: No remote set. Run `nexus remote <workspace>/<project>`'));
      process.exit(1);
    }

    const [workspace, project] = config.remote.split('/');
    const BACKEND_URL = getBackendUrl(config);
    const api = `${BACKEND_URL}/api/repo/${workspace}/${project}`;

    console.log(chalk.cyan('\n🧠 NEXUS-X Code Intelligence Graph\n'));
    console.log(chalk.gray(`  Project: ${chalk.bold(config.remote)}`));
    console.log(chalk.gray(`  Backend: ${BACKEND_URL}\n`));

    // ── Step 1: Trigger analysis ──────────────────────────────────────────
    const analyzeSpinner = ora('Analyzing repository — parsing files, building graph…').start();

    try {
      const { data } = await axios.post(`${api}/analyze`, {}, { timeout: 300_000 });

      if (data.status === 'error') {
        analyzeSpinner.fail(chalk.red(data.message));
        return;
      }

      analyzeSpinner.succeed(chalk.green('Analysis complete!'));

      // ── Display Summary ─────────────────────────────────────────────────
      console.log(chalk.cyan('\n┌─────────────────────────────────────────┐'));
      console.log(chalk.cyan('│  📊 Analysis Summary                    │'));
      console.log(chalk.cyan('├─────────────────────────────────────────┤'));

      const reg = data.registry || {};
      console.log(chalk.white(`│  Files analyzed:    ${chalk.bold(String(data.files_analyzed || 0).padStart(16))}`));
      console.log(chalk.white(`│  Functions found:   ${chalk.bold(String(reg.functions || 0).padStart(16))}`));
      console.log(chalk.white(`│  Methods found:     ${chalk.bold(String(reg.methods || 0).padStart(16))}`));
      console.log(chalk.white(`│  Classes found:     ${chalk.bold(String(reg.classes || 0).padStart(16))}`));
      console.log(chalk.white(`│  Total symbols:     ${chalk.bold(String(reg.total_symbols || 0).padStart(16))}`));

      console.log(chalk.cyan('├─────────────────────────────────────────┤'));
      console.log(chalk.cyan('│  🔗 Resolved References                │'));
      console.log(chalk.cyan('├─────────────────────────────────────────┤'));

      const res = data.resolved || {};
      console.log(chalk.white(`│  Function calls:    ${chalk.bold(String(res.calls || '0/0').padStart(16))}`));
      console.log(chalk.white(`│  File imports:      ${chalk.bold(String(res.imports || '0/0').padStart(16))}`));
      console.log(chalk.white(`│  Class inheritance:  ${chalk.bold(String(res.extends || '0/0').padStart(15))}`));

      console.log(chalk.cyan('├─────────────────────────────────────────┤'));
      console.log(chalk.cyan('│  🕸️  MongoDB Native Graph Engine        │'));
      console.log(chalk.cyan('├─────────────────────────────────────────┤'));

      const graph = data.graph || {};
      console.log(chalk.white(`│  Nodes matched:     ${chalk.bold(String(graph.nodes || 0).padStart(16))}`));
      console.log(chalk.white(`│  Edges mapped:      ${chalk.bold(String(graph.edges || 0).padStart(16))}`));
      console.log(chalk.white(`│  Processing job:    ${chalk.bold(String(data.job_id || 'sync').padStart(16))}`));
      console.log(chalk.white(`│  Engine status:     ${chalk.bold(String(data.status || 'ok').padStart(16))}`));
      console.log(chalk.white(`│  Async mode:        ${chalk.bold(String('Enabled').padStart(16))}`));

      console.log(chalk.cyan('└─────────────────────────────────────────┘'));
      console.log(chalk.green('\n✓ Knowledge graph building dynamically in MongoDB.\n'));

    } catch (err) {
      analyzeSpinner.fail(chalk.red('Analysis failed.'));
      logError(err);
    }
  });

// ─── Error helper ─────────────────────────────────────────────────────────────

function logError(err) {
  if (err.code === 'ECONNREFUSED') {
    console.error(chalk.yellow(`  No connection to backend at ${BACKEND_URL}`));
  } else {
    console.error(chalk.red('  Error:'), err.response?.data?.detail || err.message);
  }
}

program.parse();
