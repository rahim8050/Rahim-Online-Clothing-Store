// tailwind.config.js
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",         // project-level templates/
    "./**/templates/**/*.html",      // app-level users/templates/, orders/templates/, etc.
    "./static/js/**/*.js",
    "./static/src/**/*.js",
    "./src/**/*.{js,ts,vue}",
    "./**/*.py",                     // optional if you build class strings in Python
  ],
  theme: { extend: {} },
  plugins: [],

};
