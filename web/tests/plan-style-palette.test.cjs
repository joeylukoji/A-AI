'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { loadPlanStyle: loadStyle } = require('./helpers/plan-style-loader.cjs');

test('room palette returns existing labels and fills without changing input', () => {
  const style = loadStyle();
  const room = { type: 'kitchen', name: 'Cuisine ouverte' };
  const before = JSON.stringify(room);
  assert.equal(style.label(room), 'Cuisine ouverte');
  assert.equal(style.fill(room), '#e9eeeb');
  assert.equal(JSON.stringify(room), before);
});

test('generic room names fall back to type labels and unknown colors', () => {
  const style = loadStyle();
  assert.equal(style.label({ type: 'bathroom', name: 'Pièce' }), 'SDB');
  assert.equal(style.label({ type: 'future-room' }), 'Pièce');
  assert.equal(style.fill({ type: 'future-room' }), '#f1f2ee');
  assert.equal(style.label(null), 'Pièce');
  assert.equal(style.label({ type: 'bedroom', name: 'bedroom' }), 'Chambre');
  assert.equal(style.label({ type: 'living', name: 'other' }), 'Séjour');
  assert.equal(style.fills.kitchen, style.fill({ type: 'kitchen' }));
  assert.equal(style.labels.garage, 'Garage');
});

test('all plan templates load the palette before the style renderer', () => {
  const scripts = fs.readFileSync(path.join(__dirname, '../templates/partials.html'), 'utf8');
  const paletteIndex = scripts.indexOf('/static/js/plan-style-palette.js');
  const floorsIndex = scripts.indexOf('/static/js/plan-style-floors.js');
  const furnitureIndex = scripts.indexOf('/static/js/plan-style-furniture.js');
  const presentationIndex = scripts.indexOf('/static/js/plan-style-presentation.js');
  const wallsIndex = scripts.indexOf('/static/js/plan-style-walls.js');
  const annotationsIndex = scripts.indexOf('/static/js/plan-style-annotations.js');
  const styleIndex = scripts.indexOf('/static/js/plan-style.js');
  assert.ok(paletteIndex >= 0 && floorsIndex > paletteIndex &&
    furnitureIndex > floorsIndex && presentationIndex > furnitureIndex &&
    wallsIndex > presentationIndex && annotationsIndex > wallsIndex &&
    styleIndex > annotationsIndex);
  for (const name of ['editor.html', 'project.html', 'admin_plan.html']) {
    const source = fs.readFileSync(path.join(__dirname, '../templates', name), 'utf8');
    assert.match(source, /\{\{template "plan_style_scripts" \.\}\}/, name);
  }
});
