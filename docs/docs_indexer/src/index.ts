import { glob } from 'glob';
import fs from 'fs-extra';
import path from 'path';
import { fileURLToPath } from 'url';
import { parseDocument } from './extractor.js';
import { buildDocsRoutes } from './routeBuilder.js';
import { buildSearchIndex } from './searchIndexBuilder.js';
import { preprocessAdmonitions } from './parser.js';
import type { ParsedDocument } from './types.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Paths
const DOCS_SOURCE = path.resolve(__dirname, '../../');
const SERVER_DOCS_DIR = path.resolve(__dirname, '../../../server/docs_content');

async function main() {
  console.log('🔍 Starting documentation indexer...\n');

  // Find all markdown files
  const files = await glob('**/*.{md,mdx}', {
    cwd: DOCS_SOURCE,
    ignore: ['**/node_modules/**', '**/docs_indexer/**']
  });

  console.log(`📄 Found ${files.length} documentation files:\n`);
  files.forEach(f => console.log(`   - ${f}`));
  console.log();

  // Parse all documents
  const documents: ParsedDocument[] = [];

  for (const file of files) {
    const filePath = path.join(DOCS_SOURCE, file);
    const content = await fs.readFile(filePath, 'utf-8');

    try {
      const doc = parseDocument(content, filePath, file);
      documents.push(doc);
      console.log(`✅ Parsed: ${file} (${doc.headings.length} headings)`);
    } catch (error) {
      console.error(`❌ Error parsing ${file}:`, error);
    }
  }

  console.log();

  // Build routes
  const routes = buildDocsRoutes(documents);
  console.log(`🗺️  Built routes: ${routes.categories.length} categories`);

  // Build search index
  const searchIndex = buildSearchIndex(documents);
  console.log(`🔎 Built search index: ${searchIndex.documents.length} entries`);

  // Ensure output directory exists
  await fs.ensureDir(SERVER_DOCS_DIR);

  // Write routes file
  const routesPath = path.join(SERVER_DOCS_DIR, 'docs_routes.json');
  await fs.writeJson(routesPath, routes, { spaces: 2 });
  console.log(`\n📝 Written: ${routesPath}`);

  // Write search index
  const searchPath = path.join(SERVER_DOCS_DIR, 'search_index.json');
  await fs.writeJson(searchPath, searchIndex, { spaces: 2 });
  console.log(`📝 Written: ${searchPath}`);

  // Copy documentation files (with admonition preprocessing)
  console.log('\n📋 Copying documentation files...');

  for (const file of files) {
    const srcPath = path.join(DOCS_SOURCE, file);
    const destPath = path.join(SERVER_DOCS_DIR, file);

    // Read and preprocess content
    let content = await fs.readFile(srcPath, 'utf-8');
    content = preprocessAdmonitions(content);

    // Ensure directory exists and write file
    await fs.ensureDir(path.dirname(destPath));
    await fs.writeFile(destPath, content);
    console.log(`   ✅ ${file}`);
  }

  console.log('\n✨ Documentation indexing complete!\n');
  console.log('Summary:');
  console.log(`   📁 Source: ${DOCS_SOURCE}`);
  console.log(`   📁 Output: ${SERVER_DOCS_DIR}`);
  console.log(`   📄 Files: ${files.length}`);
  console.log(`   🗂️  Categories: ${routes.categories.length}`);
  console.log(`   🔍 Search entries: ${searchIndex.documents.length}`);
}

main().catch(console.error);
