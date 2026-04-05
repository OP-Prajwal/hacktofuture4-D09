#!/usr/bin/env node

import { Command } from 'commander';
import axios from 'axios';
import chalk from 'chalk';
import path from 'path';
import fs from 'fs';
import ora from 'ora';

const program = new Command();
const BACKEND_URL = process.env.NEXUS_BACKEND_URL || 'http://localhost:8000';
const NEXUS_DIR = '.nexus';
const CONFIG_FILE = 'config.json';
const IGNORED_DIRS = new Set(['.git', 'node_modules', '.nexus', '__pycache__', '.venv', 'dist', 'build']);

function getConfigPath() {
  return path.join(process.cwd(), NEXUS_DIR, CONFIG_FILE);
}

function writeConfig(config) {
  const dirPath = path.join(process.cwd(), NEXUS_DIR);
  if (!fs.existsSync(dirPath)) {
    fs.mkdirSync(dirPath);
  }
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

function walkDirectory(dir, basePath, accumulatedFiles = []) {
  const files = fs.readdirSync(dir);
  
  for (const file of files) {
    if (IGNORED_DIRS.has(file)) continue;
    
    const filePath = path.join(dir, file);
    const stat = fs.statSync(filePath);
    
    if (stat.isDirectory()) {
      walkDirectory(filePath, basePath, accumulatedFiles);
    } else {
      const relPath = path.relative(basePath, filePath);
      accumulatedFiles.push({
        path: relPath,
        name: file,
        size: stat.size,
        extension: path.extname(file)
      });
    }
  }
  return accumulatedFiles;
}

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
  .description('Set the remote origin URL using <workspace>/<project>')
  .argument('<url>', 'Remote short code (e.g., acme/my-project)')
  .action((url) => {
    // Validate format like "workspace/project"
    if (!url.includes('/')) {
        console.error(chalk.red('Invalid remote format. Expected <workspace>/<project>'));
        process.exit(1);
    }
    
    const config = readConfig();
    config.remote = url;
    writeConfig(config);
    console.log(chalk.green(`Added remote: ${chalk.bold(url)}`));
  });

program
  .command('push')
  .description('Push the directory structure to the NEXUS-X backend graph')
  .action(async () => {
    const config = readConfig();
    if (!config.remote) {
      console.error(chalk.red('Fatal: No remote configured. Run `nexus remote <workspace>/<project>` first.'));
      process.exit(1);
    }

    const currentDir = process.cwd();
    const spinner = ora(`Pushing project structure to ${config.remote}...`).start();

    try {
      // Traverse project structure locally
      const filesInfo = walkDirectory(currentDir, currentDir);
      
      const payload = {
        project_name: config.remote.split('/')[1],
        files: filesInfo
      };

      const [workspace, project] = config.remote.split('/');
      
      const response = await axios.post(`${BACKEND_URL}/api/repo/${workspace}/${project}/push`, payload);

      if (response.data && response.data.status === 'success') {
        spinner.succeed(chalk.green(`Successfully pushed structure for ${config.remote}`));
        console.log(chalk.gray(`\nTotal files processed: ${response.data.files_processed.length}`));
        console.log(chalk.gray(`Nodes created: ${response.data.nodes_created}`));
      } else {
        spinner.fail(chalk.red('Failed to push to remote.'));
        console.error(chalk.red('\nBackend Response:'), response.data);
      }
    } catch (error) {
      spinner.fail(chalk.red('Error pushing to NEXUS-X.'));
      if (error.code === 'ECONNREFUSED') {
        console.error(chalk.yellow(`\nCould not connect to the backend at ${BACKEND_URL}.`));
      } else {
        console.error(chalk.red('\nBackend Error:'), error.response?.data?.detail || error.message);
      }
    }
  });

program.parse();
