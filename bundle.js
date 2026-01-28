// bundle.js
// Bundles the OpenCode telemetry plugin into a single self-contained JavaScript file
// for easy distribution via NFS or other shared storage

import * as esbuild from 'esbuild';

console.log('Building OpenCode Telemetry Plugin bundles...\n');

// Check if --production flag is passed
const isProduction = process.argv.includes('--production');

// Common build options
const commonOptions = {
  entryPoints: ['src/index.ts'],
  bundle: true,
  platform: 'node',
  target: 'node18',
  format: 'esm',
  external: ['@opencode-ai/plugin'],
  banner: {
    js: `import { createRequire } from 'module'; const require = createRequire(import.meta.url);`,
  },
  logLevel: 'info',
};

try {
  if (isProduction) {
    // Production build - minified, optimized for NFS distribution
    console.log('Building PRODUCTION bundle (minified)...\n');
    await esbuild.build({
      ...commonOptions,
      outfile: 'dist/telemetry-plugin.bundle.min.js',
      minify: true,
      sourcemap: false,
      keepNames: false,
    });

    console.log('\n✅ Production bundle created successfully!');
    console.log('   Output: dist/telemetry-plugin.bundle.min.js');
  } else {
    // Development build - readable, with source maps
    console.log('Building DEVELOPMENT bundle (unminified)...\n');
    await esbuild.build({
      ...commonOptions,
      outfile: 'dist/telemetry-plugin.bundle.js',
      minify: false,
      sourcemap: true,
      keepNames: true,
    });

    console.log('\n✅ Development bundle created successfully!');
    console.log('   Output: dist/telemetry-plugin.bundle.js');
    console.log('   Source map: dist/telemetry-plugin.bundle.js.map');
    console.log('\nFor production (minified) bundle, run: npm run bundle -- --production');
  }

  console.log('\nTo use the bundled plugin, add to your opencode.jsonc:');
  console.log('  "plugin": ["file:///absolute/path/to/dist/telemetry-plugin.bundle.js"]');
} catch (error) {
  console.error('❌ Bundle failed:', error);
  process.exit(1);
}
