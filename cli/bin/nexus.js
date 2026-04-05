#!/usr/bin/env node

import { Command } from 'commander';
import axios from 'axios';
import chalk from 'chalk';
import path from 'path';
import fs from 'fs';
import ora from 'ora';
import crypto from 'crypto';

const program = new Command();
const BACKEND_URL = process.env.NEXUS_BACKEND_URL || 'http://localhost:8000';
const NEXUS_DIR = '.nexus';
const CONFIG_FILE = 'config.json';

// Directories to completely ignore during traversal
const IGNORED_DIRS = new Set([
  '.git', 'node_modules', '.nexus', '__pycache__',
  '.venv', 'venv', 'dist', 'build', '.next', 'coverage', '.cache'
]);

// Binary / non-text extensions to skip (no point storing compiled/media blobs)
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

// 4 MB per chunk — safe for MongoDB BSON limit and HTTP timeouts
const CHUNK_SIZE_BYTES = 4 * 1024 * 1024;

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
  const configPath = getConfigPath();
  if (!fs.existsSync(configPath)) {
    console.error(chalk.red('Fatal: Not a NEXUS repository. Run `nexus init` first.'));
    process.exit(1);
  }
  return JSON.parse(fs.readFileSync(configPath, 'utf-8'));
}

// ─── File system helpers ──────────────────────────────────────────────────────

function isTextFile(ext) {
  return !BINARY_EXTENSIONS.has(ext.toLowerCase());
}

/**
 * Recursively walk a directory.
 * Returns: { path, name, size, extension, absolutePath }[]
 */
function walkDirectory(dir, basePath, accumulated = []) {
  const entries = fs.readdirSync(dir);
  for (const entry of entries) {
    if (IGNORED_DIRS.has(entry)) continue;
    const fullPath = path.join(dir, entry);
    const stat = fs.statSync(fullPath);
    if (stat.isDirectory()) {
      walkDirectory(fullPath, basePath, accumulated);
    } else {
      const ext = path.extname(entry);
      if (!isTextFile(ext)) continue;     // skip binary files
      const relPath = path.relative(basePath, fullPath).replace(/\\/g, '/');
      accumulated.push({
        path: relPath,
        name: entry,
        size: stat.size,
        extension: ext,
        absolutePath: fullPath
      });
    }
  }
  return accumulated;
}

/**
 * Compute SHA-256 hash of a file's contents.
 * Returns a hex string — this is the "blob object ID".
 */
function hashFile(absolutePath) {
  const content = fs.readFileSync(absolutePath);
  return crypto.createHash('sha256').update(content).digest('hex');
}

/**
 * Split a file's base64 content into CHUNK_SIZE_BYTES chunks.
 * Returns string[] of base64 sub-strings.
 */
function chunkFile(absolutePath) {
  const buf = fs.readFileSync(absolutePath);
  const base64 = buf.toString('base64');
  const chunks = [];
  // Split the base64 string into 4MB chunks
  const chunkCharLen = Math.ceil((CHUNK_SIZE_BYTES * 4) / 3); // base64 overhead
  for (let i = 0; i < base64.length; i += chunkCharLen) {
    chunks.push(base64.slice(i, i + chunkCharLen));
  }
  return chunks;
}

// ─── Commands ─────────────────────────────────────────────────────────────────

program
  .name('nexus')
  .description('NEXUS-X Developer Intelligence CLI')
  .version('1.0.0');

program
  .command('init')
  .description('Initialize an empty NEXUS-X repository in the current directory')
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
  .command('remote')
  .description('Set the remote origin using <workspace>/<project>')
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
  .description('Push repository blobs to NEXUS-X backend (git-like delta transfer)')
  .action(async () => {
    const config = readConfig();
    if (!config.remote) {
      console.error(chalk.red('Fatal: No remote configured. Run `nexus remote <workspace>/<project>` first.'));
      process.exit(1);
    }

    const [workspace, project] = config.remote.split('/');
    const currentDir = process.cwd();
    const api = `${BACKEND_URL}/api/repo/${workspace}/${project}`;

    // ── Step 1: Walk and hash ────────────────────────────────────────────────
    const spinner = ora('Scanning repository…').start();
    const allFiles = walkDirectory(currentDir, currentDir);

    if (allFiles.length === 0) {
      spinner.fail(chalk.yellow('No text files found to push.'));
      return;
    }

    spinner.text = `Hashing ${allFiles.length} files…`;
    const fileRecords = allFiles.map(f => ({
      ...f,
      hash: hashFile(f.absolutePath)
    }));
    spinner.succeed(chalk.gray(`Scanned ${fileRecords.length} files.`));

    // ── Step 2: Preflight — delta check ─────────────────────────────────────
    const preflightSpinner = ora('Checking delta against remote…').start();
    let missingHashes;
    try {
      const preflightRes = await axios.post(`${api}/preflight`, {
        hashes: fileRecords.map(f => f.hash)
      });
      missingHashes = new Set(preflightRes.data.missing);
    } catch (err) {
      preflightSpinner.fail(chalk.red('Preflight check failed.'));
      logError(err);
      return;
    }

    const toUpload = fileRecords.filter(f => missingHashes.has(f.hash));
    const skipped = fileRecords.length - toUpload.length;
    preflightSpinner.succeed(
      chalk.gray(`Delta: ${toUpload.length} new, ${skipped} already stored.`)
    );

    if (toUpload.length === 0) {
      console.log(chalk.green('\n✓ Everything up to date. Nothing to push.'));
    } else {
      // ── Step 3: Chunked upload ─────────────────────────────────────────────
      console.log(chalk.cyan(`\nUploading ${toUpload.length} blob(s)…\n`));

      for (let i = 0; i < toUpload.length; i++) {
        const file = toUpload[i];
        const chunks = chunkFile(file.absolutePath);
        const label = chalk.bold(`[${i + 1}/${toUpload.length}] ${file.path}`);
        const chunkSpinner = ora(`${label}  (${chunks.length} chunk(s))`).start();

        try {
          // Upload each chunk sequentially
          for (let ci = 0; ci < chunks.length; ci++) {
            await axios.post(
              `${api}/blob/${file.hash}/chunk/${ci}`,
              { data: chunks[ci], total_chunks: chunks.length },
              { timeout: 30000 }
            );
          }

          // Finalize — assemble chunks into a stored blob
          await axios.post(`${api}/blob/${file.hash}/finalize`, {
            total_chunks: chunks.length,
            size: file.size,
            extension: file.extension,
            name: file.name
          }, { timeout: 15000 });

          chunkSpinner.succeed(`${label}  ${chalk.gray(`sha256:${file.hash.slice(0, 8)}…`)}`);
        } catch (err) {
          chunkSpinner.fail(`${label}  ${chalk.red('upload failed')}`);
          logError(err);
        }
      }
    }

    // ── Step 4: Commit — record the snapshot ──────────────────────────────────
    const commitSpinner = ora('Creating commit snapshot…').start();
    try {
      const manifest = fileRecords.map(f => ({
        path: f.path,
        hash: f.hash,
        size: f.size,
        extension: f.extension
      }));

      const commitRes = await axios.post(`${api}/commit`, {
        manifest,
        metadata: {
          push_source: currentDir,
          total_files: fileRecords.length,
          new_blobs: toUpload.length,
          skipped_blobs: skipped
        }
      }, { timeout: 15000 });

      commitSpinner.succeed(
        chalk.green(`Committed  `) +
        chalk.gray(`id: ${commitRes.data.commit_id}  · ${commitRes.data.total_files} files`)
      );
    } catch (err) {
      commitSpinner.fail(chalk.red('Commit failed.'));
      logError(err);
    }

    console.log(chalk.green('\n✓ Push complete.\n'));
  });

// ─── Helpers ──────────────────────────────────────────────────────────────────

function logError(err) {
  if (err.code === 'ECONNREFUSED') {
    console.error(chalk.yellow(`  Could not connect to backend at ${BACKEND_URL}`));
  } else {
    console.error(chalk.red('  Error:'), err.response?.data?.detail || err.message);
  }
}

program.parse();
