'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function loadPresentation() {
  const context = { window: {} };
  const file = path.join(__dirname, '../static/js/plan-style-presentation.js');
  vm.runInNewContext(fs.readFileSync(file, 'utf8'), context, { filename: file });
  return context.window.PlanStylePresentation({
    m2px: () => 20,
    ink: '#25343b',
    paper: '#ffffff',
  });
}

function recordingContext() {
  const calls = [];
  const states = [];
  const target = {
    calls,
    fillStyle: '#sentinel',
    shadowColor: '',
    shadowBlur: 0,
    shadowOffsetX: 0,
    shadowOffsetY: 0,
    measureText(text) { return { width: text.length * 6 }; },
    save() {
      states.push({ fillStyle: this.fillStyle, shadowColor: this.shadowColor,
        shadowBlur: this.shadowBlur, shadowOffsetX: this.shadowOffsetX,
        shadowOffsetY: this.shadowOffsetY });
      calls.push(['save']);
    },
    restore() {
      Object.assign(this, states.pop());
      calls.push(['restore']);
    },
    fillRect(...args) {
      calls.push(['fillRect', ...args, this.fillStyle, this.shadowColor,
        this.shadowBlur || 0, this.shadowOffsetY || 0]);
    },
    fillText(...args) { calls.push(['fillText', ...args, this.font]); },
  };
  return new Proxy(target, {
    get(object, name) {
      if (name in object) return object[name];
      return (...args) => calls.push([name, ...args]);
    },
  });
}

const toScreen = ({ x, y }) => ({ x: 100 + x * 20, y: 80 + y * 20 });

test('site presentation paints a quiet canvas and a shadowed white footprint', () => {
  const presentation = loadPresentation();
  const ctx = recordingContext();
  presentation.drawSite(ctx, 12, 9, toScreen, 960, 640);
  const fills = ctx.calls.filter(call => call[0] === 'fillRect');
  assert.deepEqual(fills[0].slice(1, 7), [0, 0, 960, 640, '#f3f2ed', '']);
  assert.deepEqual(fills[1].slice(1, 5), [100, 80, 240, 180]);
  assert.equal(fills[1][5], '#ffffff');
  assert.match(fills[1][6], /^rgba\(/);
  assert.ok(fills[1][7] > 0);
  assert.equal(ctx.fillStyle, '#sentinel');
  assert.equal(ctx.shadowColor, '');
  assert.equal(ctx.shadowBlur, 0);
  assert.equal(ctx.shadowOffsetY, 0);
  assert.equal(ctx.calls.filter(call => call[0] === 'save').length,
    ctx.calls.filter(call => call[0] === 'restore').length);
});

test('dimensions retain French formatting and add an exact two-metre scale bar', () => {
  const presentation = loadPresentation();
  const ctx = recordingContext();
  presentation.drawDimensions(ctx, 12, 9, toScreen);
  const labels = ctx.calls.filter(call => call[0] === 'fillText').map(call => call[1]);
  assert.deepEqual(labels, ['12,0 m', '9,0 m', '0', '1', '2 m']);
  const bars = ctx.calls.filter(call => call[0] === 'fillRect' && call[3] === 20 && call[4] === 4);
  assert.equal(bars.length, 2);
  assert.equal(bars[1][1] - bars[0][1], 20);
  assert.equal(ctx.calls.filter(call => call[0] === 'save').length,
    ctx.calls.filter(call => call[0] === 'restore').length);
});

test('invalid geometry never emits non-finite canvas coordinates', () => {
  const presentation = loadPresentation();
  const ctx = recordingContext();
  const invalidScreen = () => ({ x: Number.NaN, y: Number.POSITIVE_INFINITY });
  const degenerateScreen = () => ({ x: 10, y: 10 });
  presentation.drawSite(ctx, Number.NaN, 9, invalidScreen, 960, 640);
  presentation.drawDimensions(ctx, Number.NaN, 9, invalidScreen);
  presentation.drawDimensions(ctx, 12, 9, degenerateScreen);
  presentation.drawScaleBar(ctx, 12, 9, degenerateScreen);
  assert.deepEqual(ctx.calls.filter(call => call[0] === 'fillRect').map(call => call.slice(1, 5)),
    [[0, 0, 960, 640]]);
  assert.equal(ctx.calls.flat().some(value => typeof value === 'number' && !Number.isFinite(value)), false);
});
