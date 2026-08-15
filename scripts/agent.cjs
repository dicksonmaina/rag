const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const root = process.cwd();
const state = {
  project: {},
  git: {},
  ci: false,
  autonomy: false,
  dependencies: {}
};

try {
  state.git.remote = execSync('git remote -v').toString().split('\n')[0] || null;
  state.git.branch = execSync('git branch --show-current').toString().trim();
} catch (e) {}

state.ci = fs.existsSync(path.join(root, '.github', 'workflows'));
state.autonomy = fs.existsSync(path.join(root, 'scripts', 'agent.cjs'));

const workflows = [];
if (fs.existsSync(path.join(root, '.github', 'workflows'))) {
  workflows.push(...fs.readdirSync(path.join(root, '.github', 'workflows')).filter(f => f.endsWith('.yml')));
}

console.log(JSON.stringify({ ...state, workflows }, null, 2));
