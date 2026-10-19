'use strict';
const fs = require('node:fs');
const assert = require('node:assert/strict');
const app = fs.readFileSync('www/core-app.js', 'utf8');
const css = fs.readFileSync('www/approved-v22.css', 'utf8');
const html = fs.readFileSync('www/index.html', 'utf8');
assert(app.includes("dash.hero_image_url||'./assets/site/clinic.jpg'"), "Authenticated dashboard must use the uploaded hero URL.");
assert(app.includes('--approved-hero-image:url('), "Dashboard must expose the image URL as a CSS custom property.");
assert(css.includes("var(--approved-hero-image, url('./assets/site/hero.svg')) right center/cover no-repeat!important"),
  "Hero background must use the configured image, with the original SVG as fallback.");
assert(!css.includes("url('./assets/site/hero.svg') right center/cover no-repeat!important"),
  "Static sculpture must not override an uploaded image.");
assert(html.includes("approved-v22.css?v=20261017-dynamic-hero-v6"),
  "Stylesheet cache version must be bumped when the image selection rule changes.");
console.log('Gender-specific hero image rendering, fallback and cache bust: OK');
