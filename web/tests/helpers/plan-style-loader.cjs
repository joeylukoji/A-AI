'use strict';

const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const STYLE_MODULES = [
  'plan-style-palette.js',
  'plan-style-floors.js',
  'plan-style-furniture.js',
  'plan-style-assets.js',
  'plan-style-presentation.js',
  'plan-style-walls.js',
  'plan-style-openings.js',
  'plan-style-annotations.js',
  'plan-style.js',
];

function loadPlanStyle(context = { window: {} }) {
  for (const name of STYLE_MODULES) {
    const file = path.join(__dirname, '../../static/js', name);
    vm.runInNewContext(fs.readFileSync(file, 'utf8'), context, { filename: name });
  }
  return context.window.PlanStyle;
}

module.exports = { STYLE_MODULES, loadPlanStyle };
