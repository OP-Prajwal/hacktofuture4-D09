/**
 * dump_gitnexus.js — Extract graph data from GitNexus's LadybugDB
 *
 * Usage:  node dump_gitnexus.js <repo_path>
 *
 * Reads the LadybugDB database that GitNexus creates at <repo>/.gitnexus/lbug
 * and dumps ALL nodes and edges as JSON to stdout.
 *
 * The output shape:
 * {
 *   nodes: [ { id, name, filePath, label, startLine, endLine, content, description, ... } ],
 *   edges: [ { source, target, type, confidence, reason } ],
 *   total_nodes: number,
 *   total_edges: number
 * }
 */

const path = require('path');
const fs = require('fs');

// Resolve @ladybugdb/core from GitNexus's own node_modules
const GITNEXUS_ROOT = path.resolve(__dirname, '..', '..', '..', 'GitNexus', 'gitnexus');
const lbug = require(path.join(GITNEXUS_ROOT, 'node_modules', '@ladybugdb', 'core'));

// Node tables that GitNexus uses (mirrors schema.ts NODE_TABLES)
const NODE_TABLES = [
    'File', 'Folder', 'Function', 'Class', 'Interface', 'Method',
    'CodeElement', 'Community', 'Process',
    'Struct', 'Enum', 'Macro', 'Typedef', 'Union', 'Namespace',
    'Trait', 'Impl', 'TypeAlias', 'Const', 'Static', 'Property',
    'Record', 'Delegate', 'Annotation', 'Constructor', 'Template', 'Module',
    'Section', 'Route', 'Tool'
];

// Tables that need backtick escaping in queries
const BACKTICK_TABLES = new Set([
    'Struct', 'Enum', 'Macro', 'Typedef', 'Union', 'Namespace',
    'Trait', 'Impl', 'TypeAlias', 'Const', 'Static', 'Property',
    'Record', 'Delegate', 'Annotation', 'Constructor', 'Template', 'Module'
]);

function escapeTable(t) {
    return BACKTICK_TABLES.has(t) ? `\`${t}\`` : t;
}

async function dumpDatabase(repoPath) {
    // GitNexus stores its DB at <repo>/.gitnexus/lbug
    const lbugPath = path.join(repoPath, '.gitnexus', 'lbug');

    if (!fs.existsSync(lbugPath)) {
        console.error(JSON.stringify({ error: `LadybugDB not found at ${lbugPath}` }));
        process.exit(1);
    }

    let db, conn;
    try {
        db = new lbug.Database(lbugPath);
        conn = new lbug.Connection(db);

        const nodes = [];

        // Extract nodes from every table
        for (const table of NODE_TABLES) {
            try {
                const t = escapeTable(table);
                const queryResult = await conn.query(
                    `MATCH (n:${t}) RETURN n`
                );
                const result = Array.isArray(queryResult) ? queryResult[0] : queryResult;
                const rows = await result.getAll();

                for (const row of rows) {
                    const n = row.n || row[0] || row;
                    // Flatten properties out of the node object
                    const node = typeof n === 'object' ? { ...n } : { id: String(n) };
                    node.label = table;
                    // Remove large content fields to keep JSON manageable
                    if (node.content && node.content.length > 500) {
                        node.content = node.content.substring(0, 500) + '...';
                    }
                    nodes.push(node);
                }
            } catch (err) {
                // Table might not exist or be empty — skip
            }
        }

        // Extract all relationships
        const edges = [];
        try {
            const edgeQuery = await conn.query(
                'MATCH (a)-[r:CodeRelation]->(b) RETURN a.id as source, r.type as type, b.id as target, r.confidence as confidence, r.reason as reason'
            );
            const edgeResult = Array.isArray(edgeQuery) ? edgeQuery[0] : edgeQuery;
            const edgeRows = await edgeResult.getAll();

            for (const row of edgeRows) {
                edges.push({
                    source: row.source || row[0],
                    type: row.type || row[1],
                    target: row.target || row[2],
                    confidence: row.confidence || row[3] || 1.0,
                    reason: row.reason || row[4] || ''
                });
            }
        } catch (err) {
            // CodeRelation table might not exist
            console.error(`Edge extraction warning: ${err.message}`);
        }

        // Output the full graph as a single JSON blob to stdout
        const output = JSON.stringify({
            nodes,
            edges,
            total_nodes: nodes.length,
            total_edges: edges.length
        });

        console.log(output);

    } catch (err) {
        console.error(JSON.stringify({ error: err.message }));
        process.exit(1);
    } finally {
        if (conn) try { await conn.close(); } catch {}
        if (db) try { await db.close(); } catch {}
    }
}

const targetPath = process.argv[2] || process.cwd();
dumpDatabase(targetPath).catch(e => {
    console.error(JSON.stringify({ error: e.message }));
    process.exit(1);
});
